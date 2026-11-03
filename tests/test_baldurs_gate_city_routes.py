# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Route-planning and assertion regressions; these doubles are not native MCP gameplay evidence."""

import ast
from collections import Counter
import json
from pathlib import Path
import unittest

from scripts.build_baldurs_gate_city import decodeCityData
from tests import gameplay_routes_baldurs_gate as routes
from tests.gameplay_branch_types import PLAYER_CLASSES

ROOT = Path(__file__).resolve().parents[1]


class BaldursGateCityRoutesTest(unittest.TestCase):
    def testInterludeMappingsSeparateUnavailableOffersFromSuccessfulReturn(self):
        prefix = "res/maps/baldursGate/script.py:BaldursGateDialog."
        for predicate in ("canCityInterlude", "canReturnFromInterlude"):
            self.assertEqual(
                ("baldursGate.interlude.earlyReturnRefused",), routes.SOURCE_BRANCHES.get(prefix + predicate)
            )
        for action in ("cityInterlude", "returnFromInterlude"):
            self.assertEqual(
                ("baldursGate.quest.cythandriaDiary.complete",), routes.SOURCE_BRANCHES.get(prefix + action)
            )
        positive = [case for case in routes.CASES if "baldursGate.quest.cythandriaDiary.complete" in case.branches]
        self.assertEqual(1, len(positive), "Successful return needs its existing positive registered quest plan")
        quest = next(row for row in routes.documents()["quests"] if row["id"] == "cythandriaDiary")
        self.assertEqual(7, quest["phase"], "The positive plan must actually request the later city visit")
        history = {
            case.id: case
            for case in routes.CASES
            if case.id in {"baldurs-gate-history-helped", "baldurs-gate-history-killed"}
        }
        self.assertEqual(2, len(history))
        self.assertTrue(all(case.isolated_gui for case in history.values()))
        self.assertTrue(all("baldursGate.interlude.earlyReturnRefused" in case.branches for case in history.values()))

    def testPositiveInterludePlanSettlesPrerequisitesThenChoosesBothAuthoredActions(self):
        from types import SimpleNamespace

        events = []
        phase = [5]

        def choose(dialog, action):
            events.append(("choose", dialog, action))
            if action == "returnFromInterlude":
                phase[0] = 7

        planner = routes.QuestRoute.__new__(routes.QuestRoute)
        planner.d = SimpleNamespace(test=self, number=lambda _key: phase[0], choose=choose)
        planner.settle = lambda key, choice: events.append(("settle", key, choice))
        planner.contact = lambda actor: events.append(("contact", actor))
        planner.ensurePhase(7)
        self.assertEqual(
            [
                ("settle", "eltanIronThrone", "complete"),
                ("contact", "cityStart"),
                ("choose", "cityStartDialog", "cityInterlude"),
                ("choose", "cityStartDialog", "returnFromInterlude"),
            ],
            events,
        )
        self.assertEqual(7, phase[0])
        planner.ensurePhase(7)
        self.assertEqual(4, len(events), "An existing later visit must not replay departure")

    def historyUiDriver(self, mutation=None):
        """A paged native-API double; this is source regression evidence only."""
        from tempfile import TemporaryDirectory

        home = TemporaryDirectory()
        self.addCleanup(home.cleanup)
        test = self

        class Driver:
            game, game_map, player = "game", "map", "player"
            trace_path = Path(home.name) / "native.jsonl"
            _combat_trace_seq = 0
            position = (207, 85, 0)
            history = None
            frozen = False
            panel_open = False
            focused = -1
            page = 0

            def __init__(self):
                self.test = test
                self.history, self.records, self.choices, self.moves, self.saves = {}, [], [], [], []
                self.trace_path.write_text("", encoding="utf-8")
                actions = [
                    "historyAldethHelped",
                    "historyAldethKilled",
                    "historyTenyaHelped",
                    "historyTenyaKilled",
                    "cityInterlude",
                    "returnFromInterlude",
                    "historyEldothAbsent",
                    "finishHistoryChoices",
                    "",
                ]
                self.rows = []
                for number, action in enumerate(actions):
                    row = {"number": number, "action": action, "text": "Reply " + (action or "Leave")}
                    condition = {
                        "cityInterlude": "canCityInterlude",
                        "returnFromInterlude": "canReturnFromInterlude",
                        "finishHistoryChoices": "canFinishHistoryChoices",
                    }.get(action)
                    if condition:
                        row["condition"] = condition
                    self.rows.append(row)

            def available(self):
                return [
                    row
                    for row in self.rows
                    if not row.get("condition") or self.condition("cityStartDialog", row["condition"])
                ]

            def condition(self, _dialog_id, method):
                if method == "canFinishHistoryChoices":
                    return not self.frozen
                return mutation == "unearnedOffer" and method == "canCityInterlude"

            def apply(self, action):
                self.choices.append(action)
                if action.startswith("history"):
                    key = next(key for key in ("aldeth", "tenya", "eldoth") if key in action.lower())
                    if not self.frozen and key not in self.history:
                        self.history[key] = next(
                            value for value in ("helped", "killed", "absent") if value in action.lower()
                        )
                elif action == "finishHistoryChoices":
                    self.frozen = True
                    for key in ("aldeth", "tenya", "eldoth"):
                        self.history.setdefault(key, "unspecified")

            def call(self, owner, method, *args):
                if method == "createObject":
                    return "dialog"
                if method == "invokeCondition":
                    return self.condition("cityStartDialog", args[0])
                if method == "getGuiHandler":
                    return "handler"
                if method == "openDialog":
                    self.panel_open, self.focused, self.page = True, -1, 0
                    return "panel"
                if method == "getObjectProperty":
                    return "dialog"
                if method == "getTypeId":
                    return "cityStartDialog"
                if method == "getChildren":
                    indexes = list(range(self.page, min(self.page + 2, len(self.available()))))
                    if mutation == "missingPage":
                        indexes = [index for index in indexes if index != len(self.available()) - 1]
                    if mutation == "foreignButton":
                        indexes.append(len(self.available()))
                    return indexes
                if method == "getType":
                    return "CButton"
                if method == "getParent":
                    return "gui" if self.panel_open else None
                if method == "getStringProperty" and isinstance(owner, int):
                    if args[0] == "click":
                        return "chooseReply" + str(owner)
                    row = self.available()[owner]
                    return str(owner + 1) + "  " + ("wrong native text" if mutation == "wrongText" else row["text"])
                if method == "keyboardEvent":
                    key = args[-1]
                    if key == 1073741905:
                        self.focused = min(self.focused + 1, len(self.available()) - 1)
                        if not self.page <= self.focused < self.page + 2:
                            self.page = self.focused
                    elif key == 13:
                        row = self.available()[self.focused]
                        record = {
                            "seq": len(self.choices) + 1,
                            "event": "dialog_option_selected",
                            "dialog": {"typeId": "cityStartDialog"},
                            "stateId": "ENTRY",
                            "action": row["action"],
                            "optionNumber": row["number"],
                        }
                        if mutation == "wrongNumber":
                            record["optionNumber"] += 1
                        if mutation != "missingTrace":
                            with self.trace_path.open("a", encoding="utf-8") as stream:
                                stream.write(json.dumps(record) + "\n")
                        self.apply(row["action"])
                    elif key == 27:
                        self.panel_open = False
                    return True
                if method == "getItems":
                    return []
                if method == "getNumericProperty":
                    return 10000
                if method == "getStringProperty":
                    data = self.history if args[0] == "plugin_cityHistory" else {"history": self.history}
                    return json.dumps(data)
                raise AssertionError((owner, method, args))

            def _dialogStates(self, _dialog_id):
                return {"ENTRY": {"options": [{"properties": row} for row in self.rows]}}

            def enableIsolatedGui(self):
                return "gui"

            def nativePanel(self, _type_name, *, required=True):
                panel = "panel" if self.panel_open else None
                if required:
                    test.assertIsNotNone(panel)
                return panel

            def assertNativeCombatOutcomes(self):
                if self.trace_path.read_text():
                    self._combat_trace_seq = json.loads(self.trace_path.read_text().splitlines()[-1])["seq"]

            def pump(self):
                pass

            def record(self, record, **_kwargs):
                self.records.append(record)

            def startMap(self, _name):
                pass

            def flag(self, key):
                return self.frozen if key == "plugin_cityHistoryFrozen" else key == "plugin_cityInitialized"

            def number(self, key):
                return {
                    "plugin_cityStartingGoldGrant": 1000,
                    "plugin_cityStartingExpGrant": 10000,
                    "plugin_cityPhase": 5,
                }[key]

            def coords(self):
                return self.position

            def navigateTo(self, _name):
                self.position = (207, 85, 0)
                self.moves.append(self.position)

            def canStep(self, _point):
                return True

            def navigateCoords(self, point, *, limit):
                self.position = point
                self.moves.append(point)

            def gold(self):
                return 1000

            def choose(self, _dialog_id, action):
                test.assertNotIn(action, ("cityInterlude", "returnFromInterlude"), "Cannot select an unoffered reply")
                self.apply(action)

            def saveAndReload(self, label):
                self.saves.append((label, dict(self.history), self.frozen))

            def check(self, branch, condition, **evidence):
                test.assertTrue(condition)
                self.records.append({"branch": branch, **evidence})

        return Driver()

    def requireHistoryUiHelper(self):
        helper = getattr(routes, "historyDialogUi", None)
        self.assertTrue(callable(helper), "History routes must inspect the actual native filtered replies")
        return helper

    def testHistoryNativeInspectionVisitsAllFilteredPagesWithoutSelectingHiddenOffers(self):
        driver = self.historyUiDriver()
        witness = self.requireHistoryUiHelper()(driver)
        self.assertEqual("nativeUnofferedHistoryInspection", witness["kind"])
        self.assertEqual(7, len(witness["replies"]))
        self.assertEqual([], driver.choices)
        self.assertFalse(driver.panel_open)
        self.assertFalse({"cityInterlude", "returnFromInterlude"} & {row["action"] for row in witness["replies"]})

    def testHistoryNativeSelectionUsesFilteredIndexButOriginalResourceNumber(self):
        driver = self.historyUiDriver()
        witness = self.requireHistoryUiHelper()(driver, "finishHistoryChoices")
        self.assertEqual(["finishHistoryChoices"], driver.choices)
        self.assertEqual(1, witness["nativeOptionSeq"])
        self.assertEqual({"aldeth": "unspecified", "tenya": "unspecified", "eldoth": "unspecified"}, driver.history)
        self.assertFalse(driver.panel_open)

    def testHistoryNativeInspectionRejectsForeignRepliesWrongTextAndMissingPages(self):
        helper = self.requireHistoryUiHelper()
        for mutation in ("foreignButton", "wrongText", "missingPage", "unearnedOffer"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                helper(self.historyUiDriver(mutation))

    def testHistoryNativeChoiceRequiresTheExactActualInputReceipt(self):
        helper = self.requireHistoryUiHelper()
        for mutation in ("missingTrace", "wrongNumber"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                helper(self.historyUiDriver(mutation), "finishHistoryChoices")

    def testHistoryRoutePreservesFreezeDefaultsAndUsesNativeChoicesAfterRealMovement(self):
        from unittest.mock import patch

        for outcome in ("Helped", "Killed"):
            with self.subTest(outcome=outcome):
                driver = self.historyUiDriver()
                with patch.object(routes, "cityMovementCells", return_value=(frozenset({(208, 85, 0)}), frozenset())):
                    routes.history(driver, outcome)
                expected = {"aldeth": outcome.lower(), "tenya": outcome.lower(), "eldoth": "unspecified"}
                self.assertEqual(expected, driver.history)
                self.assertEqual(expected, driver.saves[0][1])
                self.assertTrue(driver.saves[0][2])
                self.assertIn((208, 85, 0), driver.moves)
                self.assertEqual((207, 85, 0), driver.moves[-1])
                selected = [
                    row["nativeHistoryUi"]
                    for row in driver.records
                    if row.get("nativeHistoryUi", {}).get("kind") == "nativeHistoryChoice"
                ]
                self.assertEqual(6, len(selected), "Every history choice needs its actual native callback receipt")
                early_return = next(
                    row for row in driver.records if row.get("branch") == "baldursGate.interlude.earlyReturnRefused"
                )
                self.assertEqual("unavailable-unoffered", early_return["outcome"])
                self.assertTrue(early_return["nativeInspection"])

    def testHistoryRoutesDeclareIsolatedGuiPreserveClassesAndBudgets(self):
        selected = {case.id: case for case in routes.CASES if case.id.startswith("baldurs-gate-history-")}
        self.assertEqual({"baldurs-gate-history-helped", "baldurs-gate-history-killed"}, set(selected))
        for identity, class_id in (
            ("baldurs-gate-history-helped", "Wayfarer"),
            ("baldurs-gate-history-killed", "Inquisitor"),
        ):
            with self.subTest(route=identity):
                case = selected[identity]
                self.assertTrue(case.isolated_gui, "Native history panels require the declared isolated GUI route")
                self.assertEqual((class_id,), case.classes)
                self.assertEqual(90, case.duration_seconds)
                self.assertIn("baldursGate.interlude.earlyReturnRefused", case.branches)

    def testNortheastArrivalCannotReachItsWestExitEvenWithOtherPortalCellsAllowed(self):
        walkable, portals = routes.cityMovementCells()
        bounds = routes.documents()["geometry"]["atlas"]["AR0300"]["bounds"]
        origin, target = (186, 51, 0), (157, 35, 0)
        self.assertIn(origin, walkable)
        self.assertIn(target, walkable)
        for forbidden in (portals, frozenset()):
            with self.subTest(portal_safety=bool(forbidden)), self.assertRaisesRegex(
                AssertionError, "No portal-safe city approach"
            ):
                routes.cityApproachPath(origin, target, bounds, walkable, forbidden)

    def testCityTravelFromActualNortheastArrivalUsesReachableSourceBoundaries(self):
        driver, _optional_path = self.boundaryTravelDriver()
        driver.position = (186, 51, 0)
        geometry = routes.documents()["geometry"]
        old_route = routes.pathBetween("AR0300", "AR0200", geometry["connections"], lambda _link: True)
        self.assertEqual(["cityAr0300Boundary6"], [row["object"] for row in old_route])
        traversed = routes.travel(driver, "AR0200")
        self.assertEqual("cityAr0300Boundary7", driver.transitions[0])
        self.assertEqual("AR0200", routes.currentArea(driver))
        self.assertEqual(len(driver.transitions), len(traversed))
        self.assertGreater(len(driver.transitions), 1)
        self.assertTrue(all(name.startswith("cityAr") for name in driver.transitions))
        for name in driver.transitions:
            self.assertIn(name, {row["object"] for row in geometry["connections"]})

    def testComponentRouteCanReturnToAnotherStreetComponentButCannotInventAccessOrArrival(self):
        atlas = {
            "A": {"bounds": [0, 0, 0, 4, 2]},
            "B": {"bounds": [6, 0, 0, 2, 1]},
            "C": {"bounds": [10, 0, 0, 2, 1]},
        }
        walkable = frozenset({(0, 0, 0), (1, 0, 0), (3, 0, 0), (3, 1, 0), (6, 0, 0), (7, 0, 0), (10, 0, 0)})
        portals = frozenset({(1, 0, 0), (7, 0, 0), (3, 0, 0)})
        links = [
            {"object": "aToC", "from": "A", "to": "C", "origin": [3, 0, 0], "target": [10, 0, 0]},
            {"object": "aToB", "from": "A", "to": "B", "origin": [1, 0, 0], "target": [6, 0, 0]},
            {"object": "bToA", "from": "B", "to": "A", "origin": [7, 0, 0], "target": [3, 1, 0]},
        ]
        route = routes.cityTravelPath((0, 0, 0), "A", "C", links, lambda _link: True, atlas, walkable, portals)
        self.assertEqual(["aToB", "bToA", "aToC"], [row["object"] for row in route])
        for denied in ("aToB", "bToA", "aToC"):
            with self.subTest(denied=denied), self.assertRaisesRegex(
                AssertionError, "No currently permitted source route"
            ):
                routes.cityTravelPath(
                    (0, 0, 0), "A", "C", links, lambda link: link["object"] != denied, atlas, walkable, portals
                )
        wrong_arrival = [dict(row, target=[0, 0, 0]) if row["object"] == "bToA" else row for row in links]
        with self.assertRaisesRegex(AssertionError, "No currently permitted source route"):
            routes.cityTravelPath((0, 0, 0), "A", "C", wrong_arrival, lambda _link: True, atlas, walkable, portals)

    def testTravelRejectsChangedActualPortalDestinationsAndWrongArrivalCoordinates(self):
        for mutation in ("destination", "arrival"):
            with self.subTest(mutation=mutation):
                driver, _ = self.boundaryTravelDriver()
                if mutation == "destination":
                    original_call = driver.call
                    driver.call = lambda owner, method, key: original_call(owner, method, key) + int(key == "targetX")
                else:
                    original_move = driver.navigateCoords

                    def move(point, *, limit):
                        before = len(driver.transitions)
                        original_move(point, limit=limit)
                        if len(driver.transitions) > before:
                            driver.position = (driver.position[0] + 1, driver.position[1], driver.position[2])

                    driver.navigateCoords = move
                with self.assertRaisesRegex(
                    AssertionError, "Actual source destination|Actual source arrival coordinates"
                ):
                    routes.travel(driver, "AR0100")
                if mutation == "destination":
                    self.assertEqual([], driver.moves)

    def testNineWardTravelUsesRealArrivalComponentsAndCompulsoryPortalEntries(self):
        driver, _ = self.boundaryTravelDriver()
        driver.position = (186, 66, 0)
        for area_id in routes.WARDS:
            with self.subTest(destination=area_id):
                before = len(driver.transitions)
                traversed = routes.travel(driver, area_id)
                self.assertEqual(area_id, routes.currentArea(driver))
                self.assertEqual(len(traversed), len(driver.transitions) - before)
        self.assertLess(driver.turns, 20000)

    def testPortalApproachAvoidsUnselectedForcedEdgesButAllowsItsActualDestination(self):
        walkable, portals = routes.cityMovementCells()
        geometry = routes.documents()["geometry"]
        chosen = next(row for row in geometry["connections"] if row["object"] == "cityAr0200Boundary3")
        east = next(row for row in geometry["connections"] if row["object"] == "cityAr0200Boundary5")
        returning = next(row for row in geometry["connections"] if row["object"] == "cityAr0300Boundary6")
        origin, target = tuple(returning["target"]), tuple(chosen["origin"])
        self.assertEqual((144, 35, 0), origin)
        self.assertEqual((143, 35, 0), tuple(east["origin"]))
        self.assertEqual((80, 30, 0), target)
        path = routes.cityApproachPath(origin, target, geometry["atlas"]["AR0200"]["bounds"], walkable, portals)
        self.assertEqual(target, path[-1], "The selected source entrance remains the actual final step")
        self.assertNotIn(tuple(east["origin"]), path)
        self.assertFalse(set(path[:-1]) & portals)
        self.assertLessEqual(len(path), 404)
        for before, after in zip((origin,) + path, path):
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(before, after)))
            self.assertIn(after, walkable)

    def testPortalApproachAllowsTheSelectedPortalAndRejectsRoutesThroughAnotherOne(self):
        cells = frozenset((x, 0, 0) for x in range(3))
        portals = frozenset({(1, 0, 0), (2, 0, 0)})
        self.assertEqual(((1, 0, 0),), routes.cityApproachPath((0, 0, 0), (1, 0, 0), [0, 0, 0, 3, 1], cells, portals))
        with self.assertRaisesRegex(AssertionError, "No portal-safe city approach"):
            routes.cityApproachPath((0, 0, 0), (2, 0, 0), [0, 0, 0, 3, 1], cells, portals)
        self.assertEqual(((0, 0, 0),), routes.cityApproachPath((1, 0, 0), (0, 0, 0), [0, 0, 0, 3, 1], cells, portals))

    def testOrdinaryCityApproachStaysInsideItsAreaAndFailsClosedWithoutWalkableAccess(self):
        cells = frozenset({(0, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0), (2, 0, 0)})
        path = routes.cityApproachPath((0, 0, 0), (2, 0, 0), [0, 0, 0, 3, 2], cells, frozenset())
        self.assertEqual(((0, 1, 0), (1, 1, 0), (2, 1, 0), (2, 0, 0)), path)
        self.assertEqual((), routes.cityApproachPath((0, 0, 0), (0, 0, 0), [0, 0, 0, 3, 2], cells, frozenset()))
        for target, bounds in (((1, 0, 0), [0, 0, 0, 3, 2]), ((2, 0, 0), [0, 0, 0, 2, 2])):
            with self.subTest(target=target, bounds=bounds), self.assertRaisesRegex(
                AssertionError, "No portal-safe city approach"
            ):
                routes.cityApproachPath((0, 0, 0), target, bounds, cells, frozenset())

    def boundaryTravelDriver(self):
        """Model optional navigation edges plus mandatory portal entry, without native gameplay credit."""
        from collections import defaultdict, deque
        from functools import lru_cache

        test, geometry = self, routes.documents()["geometry"]
        document = json.loads((ROOT / "res/maps/baldursGate/map.json").read_text(encoding="utf-8"))
        ground = next(
            layer
            for layer in document["layers"]
            if layer["type"] == "tilelayer" and layer["properties"]["level"] == "0"
        )
        tile_names = {
            tileset["firstgid"] + int(index): row["type"]
            for tileset in document["tilesets"]
            for index, row in tileset["tileproperties"].items()
        }
        cells = {
            (index % document["width"], index // document["width"], 0)
            for index, gid in enumerate(ground["data"])
            if tile_names[gid] in {"GroundTile", "cityStreetTile"}
        }
        links = {tuple(row["origin"]): row for row in geometry["connections"]}
        optional = defaultdict(list)
        for point, row in links.items():
            optional[point].append(tuple(row["target"]))

        @lru_cache(maxsize=None)
        def optionalPath(origin, target):
            pending, previous = deque([origin]), {origin: None}
            while pending:
                point = pending.popleft()
                if point == target:
                    result = []
                    while previous[point] is not None:
                        result.append(point)
                        point = previous[point]
                    return tuple(reversed(result))
                x, y, z = point
                for candidate in ((x - 1, y, z), (x + 1, y, z), (x, y - 1, z), (x, y + 1, z), *optional[point]):
                    if candidate in cells and candidate not in previous:
                        previous[candidate] = point
                        pending.append(candidate)
            raise AssertionError(("No modeled native route", origin, target))

        class Driver:
            def __init__(self):
                self.test, self.turns, self.position = test, 0, (144, 35, 0)
                self.moves, self.limits, self.transitions = [], [], []

            def coords(self, owner=None):
                if owner is None:
                    return self.position
                return tuple(next(row["origin"] for row in geometry["connections"] if row["object"] == owner))

            def object(self, name):
                return name

            def call(self, owner, method, key):
                if method == "getNumericProperty" and key in ("targetX", "targetY", "targetZ"):
                    link = next(row for row in geometry["connections"] if row["object"] == owner)
                    return link["target"]["XYZ".index(key[-1])]
                if method == "getBoolProperty" and key == "locked":
                    return False
                raise AssertionError((owner, method, key))

            def number(self, _key):
                return 5

            def flag(self, _key):
                return False

            def string(self, _key):
                return routes.currentArea(self)

            def canStep(self, point):
                return tuple(point) in cells

            def navigateCoords(self, point, *, limit=None):
                point = tuple(point)
                test.assertGreater(limit, 0)
                test.assertEqual(1, sum(abs(a - b) for a, b in zip(self.position, point)))
                test.assertIn(point, cells)
                self.moves.append((self.position, point))
                self.limits.append(limit)
                self.position, self.turns = point, self.turns + 1
                if point in links:
                    self.transitions.append(links[point]["object"])
                    self.position = tuple(links[point]["target"])

            def navigateTo(self, name):
                target = self.coords(name)
                budget = max(128, 4 * sum(abs(a - b) for a, b in zip(self.position, target)) + 128)
                for _ in range(budget):
                    if self.position == target:
                        return
                    self.navigateCoords(optionalPath(self.position, target)[0], limit=budget)
                    if self.transitions and self.transitions[-1] == name:
                        return
                raise AssertionError(("Authored route budget exhausted", name, budget, self.position))

        return Driver(), optionalPath

    def testCityTravelAvoidsTheActualEastBoundaryOscillationWithAdjacentNativeTargets(self):
        driver, optional_path = self.boundaryTravelDriver()
        self.assertEqual((143, 35, 0), optional_path((144, 35, 0), (80, 30, 0))[0])
        self.assertEqual((157, 35, 0), optional_path((156, 35, 0), (80, 30, 0))[0])
        traversed = routes.travel(driver, "AR0100")
        self.assertEqual(["WORLDMAP.WMP#cityLink3"], traversed)
        self.assertEqual(["cityAr0200Boundary3"], driver.transitions)
        self.assertEqual((67, 31, 0), driver.coords())
        self.assertEqual("AR0100", routes.currentArea(driver))
        self.assertLessEqual(driver.turns, 404)
        self.assertEqual(list(range(404, 404 - driver.turns, -1)), driver.limits)

    def testOrdinaryCityApproachRequiresActualArrivalsAndKeepsTheOriginalTurnBudget(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        cells = frozenset({(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0)})
        for mutation in (None, "intermediateArrival", "finalArrival", "budget"):
            with self.subTest(mutation=mutation):
                driver = SimpleNamespace(test=self, turns=0, position=(0, 0, 0), limits=[])
                driver.coords = lambda owner=None: (2, 0, 0) if owner else driver.position
                driver.object = lambda name: name

                def navigate(point, *, limit):
                    self.assertEqual(1, sum(abs(a - b) for a, b in zip(driver.position, point)))
                    driver.limits.append(limit)
                    driver.position = tuple(point)
                    driver.turns += 137 if mutation == "budget" else 1
                    if mutation == "intermediateArrival" or (mutation == "finalArrival" and point == (2, 0, 0)):
                        driver.position = (0, 1, 0)

                driver.navigateCoords = navigate
                with patch.object(routes, "cityMovementCells", return_value=(cells, frozenset())), patch.object(
                    routes, "documents", return_value={"geometry": {"atlas": {"A": {"bounds": [0, 0, 0, 3, 2]}}}}
                ):
                    if mutation:
                        with self.assertRaisesRegex(AssertionError, "City waypoint|City approach turn budget"):
                            routes.approachCityObject(driver, "ordinary")
                    else:
                        routes.approachCityObject(driver, "ordinary")
                        self.assertEqual((2, 0, 0), driver.position)
                        self.assertEqual([136, 135], driver.limits)
                        self.assertEqual(2, driver.turns)

    def testAuthoredEastToNortheastPortalRunsWithExactNativePluginBuiltins(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        from tests.test_baldurs_gate_city_content import CityModel

        model = CityModel()
        self.assertNotIn("next", model.namespace["__builtins__"])
        link = next(
            row for row in routes.documents()["geometry"]["connections"] if row["object"] == "cityAr0800Boundary15"
        )
        self.assertEqual(("AR0800", "AR0300"), (link["from"], link["to"]))
        portal = model.createObject("BaldursGatePortal")
        portal.setStringProperty("name", link["object"])
        portal.properties.update(routes.documents()["config"][link["object"]]["properties"])
        portal.moveTo(*link["origin"])
        model.game_map.addObject(portal)
        model.player.moveTo(*link["origin"])
        model.game_map.setStringProperty("activeSimulationRegion", link["from"])
        model.clock.applySchedules = Mock()
        self.assertTrue(portal.usable())
        self.assertEqual(tuple(link["target"]), tuple(vars(portal.target()).values()))
        portal.onEnter(SimpleNamespace(getCause=lambda: model.player))
        self.assertEqual(tuple(link["target"]), tuple(vars(model.player.getCoords()).values()))
        self.assertEqual(link["to"], model.game_map.getStringProperty("activeSimulationRegion"))
        self.assertIn(link["to"], routes.decodeCityData(model.game_map.getStringProperty("plugin_cityVisitedAreas")))
        self.assertEqual("", model.player.getStringProperty("plugin_cityPortalGuard"))
        model.clock.applySchedules.assert_called_once_with()

    def testNativeTradePlanRejectsWrongGoldAndDuplicatedSoldInstances(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        for mutation in (None, "wrongGold", "duplicate"):
            with self.subTest(mutation=mutation):
                state = {
                    "gold": 1000,
                    "hero": {},
                    "shop": {},
                    "checks": [],
                    "saves": [],
                    "selections": [],
                }
                item = {
                    "name": "source-dart-instance",
                    "plugin_citySourceItem": "DART02",
                    "plugin_cityQuantity": 5,
                    "plugin_cityValue": 8,
                    "plugin_citySoldToStore": False,
                }
                driver = SimpleNamespace(
                    test=self,
                    player="hero",
                    gold=lambda: state["gold"],
                    object=lambda name: "clock" if name == "cityClock" else "shop",
                    saveAndReload=lambda label: state["saves"].append(label),
                    check=lambda branch, condition, **evidence: state["checks"].append(branch),
                )

                def call(owner, method, *args):
                    if method == "getItems":
                        return list(state[owner].values())
                    if method == "getName":
                        return owner["name"]
                    if method == "getNumericProperty":
                        return 10000 if owner == "hero" else owner.get(args[0], 0)
                    if method == "getBoolProperty":
                        return owner.get(args[0], False)
                    if method == "getStringProperty":
                        if owner == "clock":
                            return json.dumps({"STOBLACK": {"buy_markup": 50, "sell_markup": 200}})
                        return owner.get(args[0], "")
                    raise AssertionError((owner, method, args))

                def buy(_dialog, action):
                    self.assertEqual("buyStoreStoblack1", action)
                    state["gold"] -= 80
                    state["hero"][item["name"]] = item

                def choose(_dialog, action, *, selected_id):
                    self.assertEqual(item["name"], selected_id)
                    state["selections"].append(action)
                    if action == "sell":
                        state["shop"][selected_id] = state["hero"].pop(selected_id)
                        item["plugin_citySoldToStore"] = True
                        state["gold"] += 21 if mutation == "wrongGold" else 20
                    else:
                        self.assertEqual("buyBack", action)
                        state["hero"][selected_id] = state["shop"][selected_id]
                        if mutation != "duplicate":
                            del state["shop"][selected_id]
                        item["plugin_citySoldToStore"] = False
                        state["gold"] -= 80
                    return {"kind": "sourceModelOnly"}

                driver.call, driver.choose, driver.chooseUi = call, buy, choose
                with patch.object(routes, "start"), patch.object(
                    routes, "QuestRoute", return_value=SimpleNamespace(contact=Mock())
                ):
                    if mutation:
                        with self.assertRaises(AssertionError):
                            routes.tradeUi(driver)
                    else:
                        routes.tradeUi(driver)
                        self.assertEqual(["sell", "buyBack"], state["selections"])
                        self.assertEqual(3, len(state["saves"]))
                        self.assertEqual(
                            ["baldursGate.trade.nativeSell", "baldursGate.trade.nativeBuyBack"], state["checks"]
                        )

    def testInventorySelectionCallbacksHaveExplicitIsolatedNativePlans(self):
        cases = {case.id: case for case in routes.CASES if case.isolated_gui}
        self.assertEqual(
            {
                "baldurs-gate-native-inventory",
                "baldurs-gate-native-failed-theft",
                "baldurs-gate-native-trading",
                "baldurs-gate-native-companion-inventory",
                "baldurs-gate-native-custody",
                "baldurs-gate-history-helped",
                "baldurs-gate-history-killed",
            },
            set(cases),
        )
        covered = {branch for case in cases.values() for branch in case.branches}
        for callback in ("showInventory", "pickPocket", "sell", "buyBack", "inspectCompanion", "takeCompanionItem"):
            identity = "res/maps/baldursGate/script.py:BaldursGateDialog." + callback
            self.assertTrue(set(routes.SOURCE_BRANCHES[identity]) <= covered)
        tree = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        for method in ("inventoryUi", "tradeUi", "companionInventoryUi"):
            source = ast.unparse(
                next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == method)
            )
            self.assertIn("d.chooseUi", source)
            self.assertIn("saveAndReload", source)
            self.assertIn("itemInstances", source)
        self.assertFalse(any(case.isolated_gui for case in routes.generatedQuestCases()))

    def testCityHasNaturalRoutePlansForAllFiveExistingHeroClasses(self):
        self.assertEqual(set(PLAYER_CLASSES), {hero for case in routes.CASES for hero in case.classes})
        self.assertTrue(all(case.group == "baldursGate" and case.maps == ("baldursGate",) for case in routes.CASES))
        identifiers = [case.id for case in routes.CASES]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(case.initial_reputation is None for case in routes.CASES))
        self.assertTrue(all(case.duration_seconds <= 1200 for case in routes.CASES))

    def testSourceDistrictsInteriorsSaveHistoryAndLockAlternativesRemainExplicit(self):
        declared = {branch for case in routes.CASES for branch in case.branches}
        self.assertTrue({"baldursGate.travel." + area for area in routes.WARDS} <= declared)
        self.assertTrue(
            {
                "baldursGate.history.helped",
                "baldursGate.history.killed",
                "baldursGate.interlude.earlyReturnRefused",
                "baldursGate.ownership.exactLootAndReload",
                "baldursGate.locks.picked",
                "baldursGate.locks.forced",
                "baldursGate.locks.refused",
                "baldursGate.travel.revisitAndReload",
            }
            <= declared
        )
        for identity, witnesses in routes.SOURCE_BRANCHES.items():
            path, method = identity.split(":")
            self.assertTrue((ROOT / path).is_file())
            self.assertTrue(set(witnesses) <= declared, method)

    def testDirectedSourceNavigationHonorsBlockedBranchesAndCannotInventReverseEdges(self):
        links = [
            {"object": "ab", "from": "A", "to": "B"},
            {"object": "ac", "from": "A", "to": "C"},
            {"object": "cb", "from": "C", "to": "B"},
        ]
        chosen = routes.pathBetween("A", "B", links, lambda edge: edge["object"] != "ab")
        self.assertEqual(["ac", "cb"], [edge["object"] for edge in chosen])
        self.assertEqual((), routes.pathBetween("A", "A", links, lambda edge: True))
        with self.assertRaisesRegex(AssertionError, "No currently permitted source route"):
            routes.pathBetween("B", "A", links, lambda edge: True)

    def testEveryUnresolvedSourceObligationRemainsPendingWithoutCatalogAcceptanceCredit(self):
        ledger = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_ledger.json").read_text(encoding="utf-8"))
        expected = {entry["id"] for entry in ledger["entries"] if entry["implementation"]["status"] != "excluded"}
        actual = {entry["sourceId"] for entry in routes.PENDING_GAMEPLAY_OBLIGATIONS.values()}
        self.assertEqual(expected, actual)
        self.assertTrue(all("pending" in entry["reason"] for entry in routes.PENDING_GAMEPLAY_OBLIGATIONS.values()))
        self.assertFalse(ledger["acceptanceReady"])
        self.assertFalse(ledger["originalParityEstablished"])

    def testRouteCodeCannotSetProgressMoveActorsDirectlyOrAnswerNativeChoiceByFixture(self):
        tree = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        forbidden = {
            "setBoolProperty",
            "setStringProperty",
            "setNumericProperty",
            "setObjectProperty",
            "moveTo",
            "setCoords",
            "addItem",
            "addGold",
            "addExp",
            "heal",
            "hurt",
            "removeObject",
            "addObject",
            "invokeAction",
            "chooseMock",
            "setFightController",
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden)
                if node.func.attr == "call" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    self.assertNotIn(node.args[1].value, forbidden)
        self.assertIn("d.startMap(MAP)", ast.unparse(tree))
        self.assertIn("d.navigateTo", ast.unparse(tree))
        self.assertIn("d.choose", ast.unparse(tree))

    def containerApproachModel(self, mutation=None):
        from contextlib import ExitStack
        from unittest.mock import patch

        name = "cityAr0145Container3"
        driver = self.ownershipDriver(duplicate=mutation == "duplicate", wrong_gold=mutation == "wrongGold")
        driver.position, driver.target_position, driver.turns = (85, 40, 2), (88, 40, 2), 0
        driver.waypoints, driver.moves, driver.limits = [], [], []
        driver.identity = {"__handle__": "chest"}
        original_call = driver.call
        driver.call = lambda owner, method, *args: original_call(
            "chest" if isinstance(owner, dict) else owner, method, *args
        )
        self._lastContainerApproachDriver = driver
        portal = (86, 40, 2)
        cells = frozenset((x, y, 2) for x in range(85, 89) for y in (39, 40))
        if mutation == "blocked":
            cells = frozenset(point for point in cells if point[1] == 40)

        def objectByName(actual, required=True):
            self.assertEqual(name, actual)
            return driver.identity

        def coords(owner=None):
            return driver.target_position if owner else driver.position

        def area(owner, actor=None):
            point = coords(actor)
            return "AR0145" if 83 <= point[0] < 98 and 33 <= point[1] < 45 and point[2] == 2 else "outside"

        def navigate(point, *, limit):
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(driver.position, point)))
            self.assertIn(tuple(point), cells)
            driver.waypoints.append(tuple(point))
            driver.limits.append(limit)
            driver.moves.append((driver.position, tuple(point)))
            driver.position = tuple(point)
            driver.turns += 141 if mutation == "budget" else 1
            if mutation == "areaHop":
                driver.position = (69, 40, 2)
            elif mutation == "replacement":
                driver.identity = {"__handle__": "replacement"}
            elif mutation == "missing":
                driver.identity = None

        def visit(actual, *, after_tick=None):
            self.assertEqual(name, actual)
            driver.actions.append(("navigate", actual))
            budget = max(128, 4 * sum(abs(a - b) for a, b in zip(driver.position, driver.target_position)) + 128)
            for _ in range(budget):
                if driver.position == driver.target_position:
                    return
                x, y, z = driver.position
                tx, ty, _ = driver.target_position
                point = (x + (tx > x) - (tx < x), y, z) if x != tx else (x, y + (ty > y) - (ty < y), z)
                driver.moves.append((driver.position, point))
                # The transport model exposes a compulsory portal, not a native route replay.
                if point == portal:
                    driver.position = (69, 40, 2)
                elif x < 83:
                    driver.position = (85, 40, 2)
                else:
                    self.assertIn(point, cells)
                    driver.position = point
                driver.turns += 1
                if after_tick:
                    after_tick()
            raise AssertionError(("Authored route budget exhausted", actual, budget, driver.position))

        driver.object, driver.coords = objectByName, coords
        driver.navigateCoords, driver.navigateTo = navigate, visit
        data = {
            "config": {name: {"properties": {"sourceArea": "AR0145"}}},
            "geometry": {"atlas": {"AR0145": {"bounds": [83, 33, 2, 15, 12]}}},
            "source": {"items": {}},
        }
        with ExitStack() as stack:
            travel = stack.enter_context(patch.object(routes, "travel"))
            stack.enter_context(patch.object(routes, "documents", return_value=data))
            stack.enter_context(patch.object(routes, "currentArea", side_effect=area))
            stack.enter_context(patch.object(routes, "cityMovementCells", return_value=(cells, frozenset({portal}))))
            result = routes.openContainer(driver, name)
            travel.assert_called_once_with(driver, "AR0145")
        return driver, result

    def testContainerContactAvoidsCompulsoryPortalsWithoutChangingRewardsOrBudget(self):
        driver, result = self.containerApproachModel()
        self.assertEqual((88, 40, 2), driver.position)
        self.assertEqual((1017, 10000, Counter({"RING10": 2})), result)
        self.assertEqual(140, max(128, 4 * 3 + 128), "The original three-cell approach budget is unchanged")
        self.assertLessEqual(driver.turns, 140)
        self.assertTrue(driver.waypoints)
        self.assertNotIn((86, 40, 2), driver.waypoints)
        self.assertTrue(all(sum(abs(a - b) for a, b in zip(before, after)) == 1 for before, after in driver.moves))
        self.assertEqual(2, sum(action[0] == "choice" for action in driver.actions))
        self.assertTrue(driver.looted)
        self.assertEqual([], driver.contents)

    def testContainerContactRejectsStaleIdentityAreaBudgetAndIncompleteAccessBeforeOpening(self):
        for mutation in ("replacement", "missing", "areaHop", "budget", "blocked"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.containerApproachModel(mutation)
            driver = self._lastContainerApproachDriver
            self.assertFalse(any(action[0] == "choice" for action in driver.actions))
            self.assertEqual(1000, driver.gold_value)
            self.assertEqual({}, driver.items)
            self.assertFalse(driver.looted)
        for mutation in ("wrongGold", "duplicate"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.containerApproachModel(mutation)

    def ownershipDriver(self, *, duplicate=False, wrong_gold=False):
        test = self

        class Driver:
            def __init__(self):
                self.test, self.player, self.game_map = test, "hero", "map"
                self.class_id = "Wayfarer"
                self.gold_value, self.exp = 1000, 10000
                self.items, self.looted = {}, False
                self.contents = [{"item": "RING10", "quantity": 2}, {"item": "MISC07", "charges": [17, 0, 0]}]
                self.actions = []

            def call(self, owner, method, *args):
                if method == "getStringProperty":
                    return json.dumps(self.contents) if owner == "chest" else self.items[owner][args[0]]
                if method == "getNumericProperty":
                    return self.exp if owner == "hero" else self.items[owner][args[0]]
                if method == "getBoolProperty":
                    return self.looted if args[0] == "looted" else False
                if method == "getItems":
                    return list(self.items)
                raise AssertionError((owner, method, args))

            def gold(self):
                return self.gold_value

            def object(self, name):
                return "chest"

            def navigateTo(self, name):
                self.actions.append(("navigate", name))

            def condition(self, *_args):
                return False

            def choose(self, dialog, action):
                self.actions.append(("choice", dialog, action))
                if action == "open" and (not self.looted or duplicate):
                    self.gold_value += 18 if wrong_gold else 17
                    self.items["ring" + str(len(self.items))] = {
                        "plugin_citySourceItem": "RING10",
                        "plugin_cityQuantity": 2,
                    }
                    self.looted, self.contents = True, []

        return Driver()

    def testOwnershipRouteRequiresNaturalContactExactDeltasAndAnInertRepeatedOpen(self):
        from unittest.mock import patch

        driver = self.ownershipDriver()
        with patch.object(routes, "travel") as travel, patch.object(
            routes, "contactCityObject", side_effect=lambda owner, name: owner.navigateTo(name)
        ) as contact:
            after = routes.openContainer(driver, "cityAr0800Container1")
        travel.assert_called_once_with(driver, "AR0800")
        contact.assert_called_once_with(driver, "cityAr0800Container1")
        self.assertEqual((1017, 10000, Counter({"RING10": 2})), after)
        self.assertEqual(("navigate", "cityAr0800Container1"), driver.actions[0])
        self.assertEqual(2, sum(action[0] == "choice" for action in driver.actions))
        for mutations in ({"duplicate": True}, {"wrong_gold": True}):
            with self.subTest(mutations=mutations), patch.object(routes, "travel"), patch.object(
                routes, "contactCityObject", side_effect=lambda owner, name: owner.navigateTo(name)
            ):
                with self.assertRaises(AssertionError):
                    routes.openContainer(self.ownershipDriver(**mutations), "cityAr0800Container1")

    def testEveryAuthoredQuestOutcomeHasAnIndividualSourceNamedNaturalRoutePlan(self):
        declared = {branch for case in routes.CASES for branch in case.branches}
        for quest in routes.documents()["quests"]:
            for outcome in quest["outcomes"]:
                branch = "baldursGate.quest." + quest["id"] + "." + outcome["id"]
                self.assertIn(branch, declared)
                action = "quest" + routes.upperFirst(quest["id"]) + routes.upperFirst(outcome["id"])
                callback = "res/maps/baldursGate/script.py:BaldursGateDialog." + action
                self.assertIn(branch, routes.SOURCE_BRANCHES[callback])

    def testOnlyActualStoreOwnersReceiveConcreteRowPlansAndOutsideClosureStoresRemainPending(self):
        from scripts.build_baldurs_gate_city_dialogs import storeDialogRows

        config = routes.documents()["config"]
        stores = decodeCityData(config["cityClock"]["properties"]["storeDefinitions"])
        owners = {
            entry["properties"]["sourceStore"]
            for entry in config.values()
            if entry.get("class") in routes.ACTOR_CLASSES and entry["properties"].get("sourceStore")
        }
        cases = routes.generatedStoreCases()
        self.assertEqual(owners, {case.id.removeprefix("baldurs-gate-store-") for case in cases})
        for case in cases:
            store_id = case.id.removeprefix("baldurs-gate-store-")
            expected = {
                "baldursGate.store." + store_id + "." + row["action"]
                for row in storeDialogRows(store_id, stores[store_id])
            }
            self.assertEqual(expected, set(case.branches))
        self.assertNotIn("TEM2601", owners, "Candlekeep's source store has no city owner")

    def testContainerQuantityExpectationsDistinguishActualAmmoStacksFromWandCharges(self):
        self.assertEqual(10, routes.sourceQuantity({"item": "BULL02", "charges": [10, 0, 0]}))
        self.assertEqual(1, routes.sourceQuantity({"item": "WAND05", "charges": [20, 20, 0]}))
        self.assertEqual(17, routes.sourceQuantity({"item": "MISC07", "charges": [17, 0, 0]}))
        self.assertEqual(3, routes.sourceQuantity({"item": "BULL02", "quantity": 3, "charges": [20, 0, 0]}))

    def vailAcceptanceModel(self, *, gold=1000, owned_scroll=False, restored=False, broken_restore=False):
        from types import SimpleNamespace
        from tests.test_baldurs_gate_city_content import CityModel

        model = CityModel()
        model.player.addGold(gold - model.player.getGold())
        config = routes.documents()["config"]
        stores = decodeCityData(config["cityClock"]["properties"]["storeDefinitions"])
        model.clock.setStringProperty("storeDefinitions", json.dumps(stores))
        owner_name = next(
            name
            for name, entry in config.items()
            if entry.get("class") in routes.ACTOR_CLASSES and entry["properties"].get("sourceStore") == "TEM0002"
        )
        vail_name = "cityAr0719Actor2"
        for index, name in enumerate((vail_name, owner_name)):
            model.resources[name] = config[name]
            actor = model.createObject(name)
            actor.setNumericProperty("posx", 10 + index * 10)
            actor.setNumericProperty("posy", 10 + index * 10)
            model.game_map.addObject(actor)
            model.clock.initializeActor(actor)
        vail = model.game_map.getObjectByName(vail_name)
        dialogs = {**json.loads((ROOT / "res/maps/baldursGate/dialog.json").read_text(encoding="utf-8")), **config}
        actions, contacts = [], []
        driver = SimpleNamespace(
            test=self,
            player=model.player,
            class_id="Warrior",
            object=lambda name, required=False: model.game_map.getObjectByName(name),
            call=lambda owner, method, *args: getattr(owner, method)(*args),
            gold=model.player.getGold,
            number=model.game_map.getNumericProperty,
            string=model.game_map.getStringProperty,
            questNames=lambda completed=False: [
                quest.getName()
                for quest in (model.player.getCompletedQuests() if completed else model.player.getQuests())
            ],
        )

        def contact(name):
            actor = driver.object(name)
            self.assertIsNotNone(actor)
            point = actor.getCoords()
            model.player.moveTo(point.x, point.y, point.z)
            contacts.append(name)

        def choose(dialog_id, action):
            actor_name = dialog_id.removesuffix("Dialog")
            self.assertEqual(actor_name, contacts[-1], "Acquisition must return to the original speaker")
            dialog = model.createObject("BaldursGateDialog")
            dialog.setStringProperty("actorId", actor_name)
            option = next(
                option["properties"]
                for state in dialogs[dialog_id]["properties"]["states"]
                for option in state["properties"]["options"]
                if option["properties"].get("action") == action
            )
            condition = option.get("condition")
            self.assertTrue(not condition or getattr(dialog, condition)(), ("Authored option is unavailable", action))
            actions.append((actor_name, action))
            if action == "restoreStatue" and broken_restore:
                return
            result = getattr(dialog, action)()
            self.assertIsNot(result, False, ("Authored action rejected", action))

        driver.choose = choose
        planner = routes.QuestRoute(driver)
        planner.contact = contact
        if owned_scroll or restored:
            model.item("SCRLPET")
        if restored:
            contact(vail_name)
            dialog = model.createObject("BaldursGateDialog")
            dialog.setStringProperty("actorId", vail_name)
            self.assertTrue(dialog.restoreStatue())
        return model, planner, vail, owner_name, actions

    def testVailQuestAcceptanceRestoresItsGiverUsingActualOwnedOrPurchasedScroll(self):
        for owned, restored in ((False, False), (True, False), (False, True)):
            with self.subTest(owned_scroll=owned, already_restored=restored):
                model, planner, vail, merchant, actions = self.vailAcceptanceModel(
                    owned_scroll=owned, restored=restored
                )
                self.assertEqual(restored, not vail.getBoolProperty("plugin_cityPetrified"))
                clue = next(
                    item for item in vail.getItems() if item.getStringProperty("plugin_citySourceItem") == "SCRLVAIL"
                )
                planner.accept("vailClue")
                self.assertFalse(vail.getBoolProperty("plugin_cityPetrified"))
                self.assertEqual("active", routes.state(planner.d, "vailClue"))
                self.assertEqual(["cityVailClueQuest"], planner.d.questNames())
                self.assertEqual(1000 if owned or restored else 775, model.player.getGold())
                self.assertEqual(0 if owned or restored else 1, planner.d.number("plugin_cityStockSold_TEM0002_2"))
                expected = []
                if not owned and not restored:
                    expected.append((merchant, "buyStoreTem00022"))
                if not restored:
                    expected.append((vail.getName(), "restoreStatue"))
                expected.append((vail.getName(), "acceptVailClue"))
                self.assertEqual(expected, actions)
                self.assertNotIn("SCRLPET", routes.resources(planner.d)[2])
                self.assertIs(clue, next(item for item in vail.getItems() if item is clue))
                dialog = model.createObject("BaldursGateDialog")
                dialog.setStringProperty("actorId", vail.getName())
                self.assertTrue(dialog.questVailClueHear())
                self.assertEqual(500, model.player.getNumericProperty("exp"))
                self.assertIn(clue, model.player.getItems())
                self.assertNotIn(clue, vail.getItems())
                self.assertFalse(dialog.questVailClueHear())
                before = (routes.resources(planner.d), list(actions))
                planner.accept("vailClue")
                self.assertEqual(before, (routes.resources(planner.d), actions))

    def testVailQuestAcceptanceCannotBypassFailedStatueRestoration(self):
        model, planner, vail, _merchant, actions = self.vailAcceptanceModel(broken_restore=True)
        with self.assertRaises(AssertionError):
            planner.accept("vailClue")
        self.assertTrue(vail.getBoolProperty("plugin_cityPetrified"))
        self.assertEqual("notStarted", routes.state(planner.d, "vailClue"))
        self.assertEqual([], planner.d.questNames())
        self.assertNotIn("acceptVailClue", [action for _actor, action in actions])

    def testActiveQuestDependenciesDoNotCompleteThePoisonQuestBeforeItsSubquests(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        driver = SimpleNamespace(
            test=self,
            player="hero",
            number=lambda key: 10,
            call=lambda owner, method, *args: "stats" if method == "getStats" else 20,
        )
        planner = routes.QuestRoute(driver)
        planner.accept, planner.settle = Mock(), Mock()
        planner.conditions({"questStages": {"marekPoison": "active", "scarSevenSuns": "completed"}})
        planner.accept.assert_called_once_with("marekPoison")
        planner.settle.assert_called_once_with("scarSevenSuns")

    def testIdentificationRouteRequiresOneActualFlagChangeEvenWhenTheSourceServiceIsFree(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        def exercise(price, mutation):
            state = {"gold": 1000, "unknown": {"sourceStaff", "sourcePotion"}, "count": 0}

            def choose(dialog, action):
                self.assertEqual(("sourceOwnerDialog", "identifyStoreSource"), (dialog, action))
                if mutation != "noIdentification":
                    state["unknown"].remove("sourceStaff")
                    state["count"] += 1
                if mutation == "twoItems":
                    state["unknown"].clear()
                state["gold"] -= price + int(mutation == "wrongGold")

            driver = SimpleNamespace(
                test=self,
                object=lambda name: name,
                number=lambda key: state["count"] if key == "plugin_cityIdentifications" else 0,
                choose=choose,
                check=Mock(),
                saveAndReload=Mock(),
            )
            store = {"flags": 4, "identify_price": price}
            with (
                patch.object(routes, "start"),
                patch.object(routes, "QuestRoute"),
                patch.object(routes, "prepareIdentification"),
                patch.object(routes, "read", return_value={"SOURCE": store}),
                patch.object(routes, "resources", side_effect=lambda unused: (state["gold"], 10000, {"STAF25": 1})),
                patch.object(routes, "unknownPossessions", side_effect=lambda unused: state["unknown"].copy()),
            ):
                routes.storeRequests(driver, "SOURCE", "sourceOwner")
            driver.check.assert_called_once()

        for price in (0, 100):
            with self.subTest(price=price, mutation="none"):
                exercise(price, "none")
            for mutation in ("noIdentification", "twoItems", "wrongGold"):
                with self.subTest(price=price, mutation=mutation):
                    with self.assertRaises(AssertionError):
                        exercise(price, mutation)

    def testNarlenWarningWaitsForActualSourceOfficerAfterBeginningTheNightLookout(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        def exercise(spawn_fact):
            state = {"plugin_cityTicks": 0, "plugin_cityNarlenOfficerAt": 0}
            flags, choices = set(), []

            def waitTurns(limit, predicate):
                for _ in range(limit):
                    if predicate():
                        return
                    state["plugin_cityTicks"] += 1
                    if "plugin_cityFlag_narlenLookoutStarted" in flags:
                        if state["plugin_cityTicks"] >= state["plugin_cityNarlenOfficerAt"]:
                            flags.add("plugin_cityFlag_narlenOfficerDue")
                self.assertTrue(predicate())

            def choose(dialog, action):
                self.assertEqual("actualNarlenDialog", dialog)
                choices.append((action, state["plugin_cityTicks"]))
                if action == "beginNarlenLookout":
                    flags.add("plugin_cityFlag_narlenLookoutStarted")
                    state["plugin_cityNarlenOfficerAt"] = state["plugin_cityTicks"] + 20
                elif action == "warnNarlen":
                    self.assertIn("plugin_cityFlag_narlenOfficerDue", flags)
                    flags.add("plugin_cityFlag_narlenWarning")

            driver = SimpleNamespace(
                test=self,
                number=lambda key: state.get(key, 0),
                flag=lambda key: key in flags,
                condition=lambda dialog, method: method == "canBeginNarlenLookout",
                object=lambda name: name,
                call=lambda owner, method, *args: True if method == "isAlive" else spawn_fact,
                waitTurns=waitTurns,
                choose=choose,
            )
            planner = routes.QuestRoute(driver)
            planner.accept, planner.contact = Mock(), Mock()
            planner.actorName = lambda selectors: (
                "actualNarlen" if selectors[0]["creature"] == "NARLEN" else "actualOfficer"
            )
            with patch.object(routes, "travel") as travel:
                planner.narlenLookout(warn=True)
            travel.assert_called_once_with(driver, "AR0300")
            self.assertEqual([("beginNarlenLookout", 700), ("warnNarlen", 720)], choices)

        exercise("AR0300.BCS#spawn7")
        with self.assertRaises(AssertionError):
            exercise("inventedOfficer")

    def testCanonicalRelocatedActorMatchesLaterAreaAlternativeWithoutCreatingAnotherActor(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        properties = {"sourceArea": "AR0123", "sourceCreature": "TAMOKO", "label": "Tamoko"}
        driver = SimpleNamespace(
            test=self,
            object=lambda name, required=False: "actualTamoko",
            call=lambda actor, method, key: properties[key] if method == "getStringProperty" else False,
        )
        data = {
            "config": {"canonicalTamoko": {"class": "CCreature", "properties": dict(properties, sourceArea="AR0800")}},
            "quests": [],
        }
        with patch.object(routes, "documents", return_value=data):
            planner = routes.QuestRoute(driver)
            selected = planner.actorName(
                [{"creature": "TAMOKO", "area": "AR1100"}, {"creature": "TAMOKO", "area": "AR0123"}]
            )
        self.assertEqual("canonicalTamoko", selected)

    def testNativeCombatWitnessBeginsBeforeTravelAndRetainsAnOpponentKilledDuringArrival(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        events = []
        alive = [True]
        driver = SimpleNamespace(
            test=self,
            _combat_trace_seq=41,
            combats=0,
            object=lambda name, required=True: "foe" if alive[0] else None,
            assertNativeCombatOutcomes=lambda: events.append("trace"),
            call=lambda owner, method, *args: alive[0] if method == "isAlive" else False,
            navigateTo=lambda name: self.fail("A resolved arrival fight must not move toward the removed actor"),
            playerVictoryAgainst=lambda map_name, name, after_seq: {"seq": 42} if after_seq == 41 else None,
        )

        def arrive(*_args):
            events.append("travel")
            alive[0] = False

        with patch.object(routes, "travel", side_effect=arrive), patch.object(
            routes, "currentArea", return_value="AR0224"
        ), patch.object(
            routes, "documents", return_value={"config": {"opponent": {"properties": {"sourceArea": "AR0224"}}}}
        ):
            routes.nativeVictory(driver, "opponent")
        self.assertEqual(["trace", "travel", "trace"], events)
        self.assertEqual(1, driver.combats)

    def testHostileAlreadySharingHeroCellRequiresFreshNativeDepartureAndCombatEntry(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        alive, revisits = [True], []

        def revisit(name):
            revisits.append(name)
            alive[0] = False

        driver = SimpleNamespace(
            test=self,
            _combat_trace_seq=10,
            combats=0,
            object=lambda name, required=True: "foe" if alive[0] else None,
            assertNativeCombatOutcomes=lambda: None,
            call=lambda owner, method, *args: alive[0] if method == "isAlive" else False,
            coords=lambda owner=None: (3, 4, 0),
            revisit=revisit,
            navigateTo=lambda name: self.fail("An overlapping hostile cannot count as a completed ordinary visit"),
            playerVictoryAgainst=lambda *_args, **_kwargs: {"seq": 11},
        )
        with patch.object(routes, "travel"), patch.object(routes, "currentArea", return_value="AR0123"):
            routes.nativeVictory(driver, "opponent")
        self.assertEqual(["opponent"], revisits)
        self.assertEqual(1, driver.combats)

    def cityContactModel(self, mutation=None):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from unittest.mock import patch

        from tests.gameplay_branch_driver import GameplayBranchDriver

        target_name = "cityCampaignNpc19"
        origin, target = (69, 143, 0), (26, 151, 0)
        portals = {(68, 143, 0): (81, 143, 0), (80, 143, 0): (69, 143, 0)}
        cells = frozenset((x, y, 0) for x in range(26, 82) for y in range(143, 153))
        interior = mutation in {"interior", "interiorMissingArrival"}
        building = mutation in {"lastAllowed", "oneOver"}
        if building:
            target_name = "ordinaryBuilding"
        if interior:
            target_name = "interiorSpeaker"
            origin, target = (33, 40, 2), (26, 44, 2)
            portals = {}
            cells = frozenset((x, y, 2) for x in range(26, 34) for y in range(40, 45))
        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            actor={"__handle__": "tiax"},
            position=target if mutation in {"zeroTick", "zeroTickReplacement"} else origin,
            target_position=target,
            turns=0,
            steps=0,
            map_name="baldursGate",
            trace_path="modeled-native-trace",
            _combat_trace_seq=0,
            entry=None,
            planned=None,
            waypoints=[],
            moves=[],
            final_calls=0,
            contact_acknowledged=False,
            initial_distance=51,
            contact_entries=0,
            travel_calls=[],
        )
        if interior:
            driver.position = (69, 143, 0)
        self._lastCityContactDriver = driver

        def objectByName(name, required=True):
            self.assertEqual(target_name, name)
            if required:
                self.assertIsNotNone(driver.actor)
            return driver.actor

        def coords(owner=None):
            return driver.target_position if owner and owner is not driver.player else driver.position

        def call(owner, method, *args):
            if method == "getBoolProperty":
                self.assertEqual("npc", args[0])
                return not building
            if method == "getController":
                return "controller"
            if method == "getCoords":
                return {"__handle__": "target-coordinates"}
            if method == "setTarget":
                value = args[-1]
                driver.planned = driver.target_position if isinstance(value, dict) else tuple(value)
                return None
            if method == "getNavigationNeighbors":
                point = tuple(args[0])
                return [(point[0] + dx, point[1] + dy, point[2]) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
            self.fail(("Unexpected modeled call", method))

        def tick():
            before = driver.position
            destination = driver.planned
            self.assertIsNotNone(destination)
            x, y, z = before
            # West-first ordinary native planning reproduces the retained two-portal cycle.
            after = (x + (destination[0] > x) - (destination[0] < x), y, z)
            if x == destination[0]:
                after = (x, y + (destination[1] > y) - (destination[1] < y), z)
            self.assertIn(after, cells)
            driver.moves.append((before, after))
            driver.position = portals.get(after, after)
            if building and driver.turns == 0:
                driver.turns += 282
            elif mutation == "oneOver" and before == (26, 150, 0):
                driver.turns += 2
            else:
                driver.turns += 333 if mutation == "budget" else 1
            if mutation == "moving" and driver.turns == 3:
                driver.target_position = (27, 151, 0)
            if mutation == "areaHop" and driver.turns == 1:
                driver.position = (81, 143, 0)
            if mutation == "streetReplacement" and driver.turns == 1:
                driver.actor = {"__handle__": "replacement"}
            if mutation == "missing" and driver.turns == 1:
                driver.actor = None
            if driver.position == driver.target_position:
                if mutation == "finalReplacement":
                    driver.actor = {"__handle__": "replacement"}
                driver.entry = {"seq": driver.turns, "target": driver.actor}

        def remember(actor, identities, entry):
            self.assertIs(actor, driver.actor)
            self.assertEqual(driver.target_position, driver.position)
            self.assertIs(entry, driver.entry)
            driver.contact_acknowledged = True
            driver.contact_entries += 1

        def nativeVisit(name, **kwargs):
            driver.final_calls += 1
            GameplayBranchDriver.navigateTo(driver, name, **kwargs)
            if mutation == "zeroTickReplacement":
                driver.actor = {"__handle__": "replacement"}

        def navigate(point, *, limit):
            driver.waypoints.append((tuple(point), limit))
            if mutation == "falseArrival":
                driver.turns += 1
                return
            GameplayBranchDriver.navigateCoords(driver, point, limit=limit)

        driver.object, driver.coords, driver.call, driver.tick = objectByName, coords, call, tick
        driver.assertNativeCombatOutcomes = lambda: None
        driver._nativeObjectIdentity = lambda owner: {"name": owner["__handle__"]}
        driver._playerEntryForTarget = lambda identities, after_seq: (
            driver.entry
            if driver.entry and driver.entry["target"] and driver.entry["target"]["__handle__"] == identities[0]["name"]
            else None
        )
        driver._continuedNpcContact = lambda actor, identities: mutation in {"zeroTick", "zeroTickReplacement"}
        driver._rememberNpcContact = remember
        driver._coordinateHandle = tuple
        driver._coordinate_values = {}
        driver._traversedTarget = lambda target, arrival: mutation == "areaHop" and arrival == (81, 143, 0)
        driver.snapshot = lambda: {"coords": driver.position, "turn": driver.turns}
        driver.canStep = lambda point: tuple(point) in cells
        driver.navigateCoords, driver.navigateTo = navigate, nativeVisit
        planner = object.__new__(routes.QuestRoute)
        planner.d = driver
        area_id = "AR0162" if interior else "AR1100"
        planner.data = {"config": {target_name: {"properties": {"sourceArea": area_id}}}}

        def area(owner, actor=None):
            if interior:
                return "AR0162" if coords(actor)[2] == 2 else "AR0800"
            return "AR1100" if coords(actor)[0] < 71 else "AR1200"

        def travel(owner, destination):
            self.assertEqual(area_id, destination)
            driver.travel_calls.append((driver.position, destination))
            if interior and mutation != "interiorMissingArrival":
                driver.position = origin

        with ExitStack() as stack:
            stack.enter_context(patch.object(routes, "currentArea", side_effect=area))
            stack.enter_context(patch.object(routes, "travel", side_effect=travel))
            bounds = [26, 40, 2, 8, 5] if interior else [4, 126, 0, 67, 54]
            stack.enter_context(
                patch.object(routes, "documents", return_value={"geometry": {"atlas": {area_id: {"bounds": bounds}}}})
            )
            stack.enter_context(patch.object(routes, "cityMovementCells", return_value=(cells, frozenset(portals))))
            planner.contact(target_name)
            if mutation == "returnVisit":
                driver.position, driver.entry = origin, None
                driver.contact_acknowledged = False
                planner.contact(target_name)
        return driver

    def testCityContactAvoidsTheRetainedCompanionPortalLoopAtTheOriginalBudget(self):
        driver = self.cityContactModel()
        self.assertEqual((26, 151, 0), driver.position)
        self.assertEqual(332, max(128, 4 * driver.initial_distance + 128))
        self.assertLessEqual(driver.turns, 332)
        self.assertTrue(driver.contact_acknowledged, "The ordinary native-entry witness remains required")
        self.assertEqual(1, driver.final_calls)
        self.assertTrue(driver.waypoints)
        self.assertFalse({point for point, _ in driver.waypoints} & {(68, 143, 0), (80, 143, 0)})
        self.assertTrue(all(sum(abs(a - b) for a, b in zip(before, after)) == 1 for before, after in driver.moves))

    def testCityContactKeepsMovingNpcEntryAndZeroTickContinuationSemantics(self):
        moving = self.cityContactModel("moving")
        self.assertEqual((27, 151, 0), moving.position)
        self.assertTrue(moving.contact_acknowledged)
        zero = self.cityContactModel("zeroTick")
        self.assertEqual(0, zero.turns)
        self.assertEqual(1, zero.final_calls, "A zero-length street plan must still call the native contact verifier")

    def testCityContactRejectsUnselectedAreaHopsAndFalseWaypointArrivals(self):
        for mutation, message in (
            ("areaHop", "Unselected city transition"),
            ("falseArrival", "waypoint was not actually reached"),
        ):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, message):
                self.cityContactModel(mutation)

    def testCityContactRejectsIdentityReplacementDuringStreetAndFinalEntry(self):
        for mutation in ("streetReplacement", "finalReplacement"):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                AssertionError, "identity changed|NPC identity changed"
            ):
                self.cityContactModel(mutation)

    def testCityContactRejectsMissingTargetsAndTheOriginalAggregateBudgetOverrun(self):
        allowed = self.cityContactModel("lastAllowed")
        self.assertEqual(332, allowed.turns)
        self.assertEqual((26, 151, 0), allowed.position)
        self.assertEqual(1, allowed.final_calls)
        with self.assertRaisesRegex(AssertionError, "City contact turn budget exhausted"):
            self.cityContactModel("oneOver")
        self.assertEqual(333, self._lastCityContactDriver.turns)
        for mutation, message in (("missing", "target disappeared"), ("budget", "City contact turn budget exhausted")):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, message):
                self.cityContactModel(mutation)
        self.assertEqual(
            333, self._lastCityContactDriver.turns, "Reject the first over-budget arrival without more work"
        )

    def testCityContactRechecksIdentityAfterAnAlreadyCompletedNativeVisit(self):
        with self.assertRaisesRegex(AssertionError, "City contact identity changed"):
            self.cityContactModel("zeroTickReplacement")

    def testCityContactRequiresActualInteriorArrivalBeforePlanningOrNativeVisit(self):
        driver = self.cityContactModel("interior")
        self.assertEqual([((69, 143, 0), "AR0162")], driver.travel_calls)
        self.assertEqual((26, 44, 2), driver.position)
        self.assertTrue(driver.contact_acknowledged)
        with self.assertRaisesRegex(AssertionError, "City contact target left its area"):
            self.cityContactModel("interiorMissingArrival")
        self.assertEqual([], self._lastCityContactDriver.waypoints)
        self.assertEqual(0, self._lastCityContactDriver.final_calls)

    def testCityContactRequiresAnotherActualEntryAfterReturningToASpeaker(self):
        driver = self.cityContactModel("returnVisit")
        self.assertEqual(2, driver.contact_entries)
        self.assertEqual(2, driver.final_calls)
        self.assertEqual(2, len(driver.travel_calls))
        self.assertTrue(driver.contact_acknowledged)
        self.assertEqual((26, 151, 0), driver.position)

    def alatosBetrayalRouteModel(self, mutation=None):
        from contextlib import ExitStack
        from unittest.mock import patch
        from tests.gameplay_branch_driver import GameplayBranchDriver

        case = self
        codes = ("WAND04", "STAF01", "CLCK14", "SCRL1W")

        class Driver:
            test = case
            _combat_trace_seq = 41
            combats = 0
            trace_path = "source-only-api-trace"
            playerVictoryAgainst = GameplayBranchDriver.playerVictoryAgainst

            def __init__(self):
                self.events, self.checks = [], []
                self.registry, self.transfers = {}, []
                self.player = {"__handle__": "hero"}
                self.alatos = {"__handle__": "alatos"}
                self.resar = {"__handle__": "resar"}
                self.stage, self.exp, self.coins = "active", 10000, 1614
                self.alive, self.present, self.npc = True, True, True
                self.hero_items = [self.item(code, "quest-" + code) for code in ("MISC69", "MISC70", "MISC71")]
                self.resar_items = [self.item(code, "resar-" + code) for code in codes]
                self.captured_handles = {item["__handle__"] for item in self.resar_items}
                self.victory = None
                self._player_victory_history = []

            def item(self, code, name, suffix=""):
                handle = {"__handle__": name + suffix}
                self.registry[handle["__handle__"]] = {"name": name, "code": code, "quantity": 1}
                return handle

            def startMap(self, name):
                case.assertEqual("baldursGate", name)
                self.events.append("start")

            def flag(self, key):
                return key == "plugin_cityInitialized"

            def number(self, key):
                return {
                    "plugin_cityStartingGoldGrant": 1000,
                    "plugin_cityStartingExpGrant": 10000,
                    "plugin_cityPhase": 5,
                    "plugin_cityStanding": 0,
                    "plugin_cityReputation": 10,
                }.get(key, 0)

            def string(self, key):
                return self.stage if key == "plugin_cityQuest_alatosTheft" else ""

            def gold(self):
                return self.coins

            def questNames(self, completed=False):
                return ["cityAlatosTheftQuest"] if completed and self.stage == "completed" else []

            def object(self, name, required=True):
                value = self.resar if name == "resar" and self.present else self.alatos if name == "alatos" else None
                if required:
                    case.assertIsNotNone(value, name)
                return value

            def call(self, owner, method, *args):
                if owner["__handle__"] in self.registry:
                    item = self.registry[owner["__handle__"]]
                    if method == "getName":
                        return item["name"]
                    if method == "getStringProperty":
                        return item["code"] if args[0] == "plugin_citySourceItem" else ""
                    if method == "getNumericProperty":
                        return item["quantity"] if args[0] == "plugin_cityQuantity" else 0
                    if method == "getBoolProperty":
                        return False
                if owner == self.player:
                    if method == "getName":
                        return "player"
                    if method == "getItems":
                        return list(self.hero_items)
                    if method == "getEquipped":
                        return {}
                    if method == "getNumericProperty":
                        return self.exp if args[0] == "exp" else 1
                    if method == "getStats":
                        return {"__handle__": "stats"}
                if owner["__handle__"] == "stats" and method == "getNumericProperty":
                    return 6
                if owner == self.resar or owner == self.alatos:
                    if method == "getItems":
                        return list(self.resar_items[:2]) if owner == self.resar else []
                    if method == "getEquipped":
                        return (
                            {str(index): item for index, item in enumerate(self.resar_items[2:])}
                            if owner == self.resar
                            else {}
                        )
                    if method == "isAlive":
                        return self.alive if owner == self.resar else True
                    if method == "isNpc":
                        return self.npc if owner == self.resar else True
                    if method == "getBoolProperty":
                        return False
                    if method == "getStringProperty":
                        if args[0] == "sourceInventory":
                            return "city-json:" + json.dumps([{"item": code, "charges": [0, 0, 0]} for code in codes])
                        return {
                            "sourceArea": "AR0153",
                            "sourceCreature": "RESAR" if owner == self.resar else "ALATOS",
                            "label": "Resar" if owner == self.resar else "Alatos",
                        }[args[0]]
                case.fail(("Unexpected actual-route API call", owner, method, args))

            def resolve(self):
                if not self.present:
                    return
                self.events.append("native-death")
                self.alive = mutation == "removedAlive"
                self.present = False
                for item in self.resar_items:
                    self.transfers.append(item["__handle__"])
                    transferred = item
                    if mutation == "clonedLoot":
                        row = self.registry[item["__handle__"]]
                        transferred = self.item(row["code"], row["name"], "-clone")
                    self.hero_items.append(transferred)
                self.resar_items.clear()
                if mutation == "changedQuantity":
                    self.registry[self.hero_items[0]["__handle__"]]["quantity"] += 1
                self.victory = {
                    "seq": 41 if mutation == "staleReceipt" else 42,
                    "map": "baldursGate",
                    "survivor": {"name": "player"},
                    "attacker": {"isPlayer": False, "name": "anotherActor" if mutation == "wrongOpponent" else "resar"},
                }
                self._player_victory_history = [] if mutation == "missingReceipt" else [self.victory]

            def choose(self, dialog, action):
                case.assertEqual("alatosDialog", dialog)
                self.events.append(action)
                if action == "questAlatosTheftComplete":
                    self.stage, self.exp, self.npc = "completed", 14000, False
                    self.hero_items.clear()
                    if mutation in {
                        "alreadyWon",
                        "missingReceipt",
                        "staleReceipt",
                        "wrongOpponent",
                        "removedAlive",
                        "earlyXp",
                    }:
                        self.resolve()
                        if mutation == "earlyXp":
                            self.exp += 73
                elif action == "talk":
                    if mutation == "repeatReward":
                        self.coins += 1
                else:
                    case.fail(action)

            def contact(self, name):
                case.assertEqual("alatos", name)
                self.events.append("contact")
                # Reproduce the hosted race: the first post-reload approach finishes pending betrayal.
                if self.stage == "completed" and "save-reload" in self.events:
                    self.resolve()

            def condition(self, *args):
                return False

            def navigateTo(self, name):
                case.assertEqual("resar", name)
                self.events.append("native-approach")
                self.resolve()

            def revisit(self, name):
                self.navigateTo(name)

            def coords(self, owner=None):
                return (2, 1, 0) if owner == self.resar else (1, 1, 0)

            def assertNativeCombatOutcomes(self):
                if self.victory:
                    self._combat_trace_seq = self.victory["seq"]

            def saveAndReload(self, label):
                case.assertEqual("city-quest-alatosTheft-complete", label)
                self.events.append("save-reload")
                # A real reload changes protocol handles; only persisted names/properties can be compared afterward.
                self.player = {"__handle__": "restoredHero"}
                rebound = []
                for item in self.hero_items:
                    row = self.registry[item["__handle__"]]
                    fresh = self.item(row["code"], row["name"], "-restored")
                    self.registry[fresh["__handle__"]]["quantity"] = row["quantity"]
                    rebound.append(fresh)
                self.hero_items = rebound

            def check(self, key, condition, **evidence):
                case.assertTrue(condition)
                self.checks.append((key, evidence))

        data = {
            "config": {
                "alatos": {"class": "CCreature", "properties": {"label": "Alatos", "sourceArea": "AR0153"}},
                "resar": {"class": "CCreature", "properties": {"label": "Resar", "sourceArea": "AR0153"}},
            },
            "source": {"items": {code: {"stack_size": 1} for code in codes}},
            "quests": [
                {
                    "id": "alatosTheft",
                    "givers": [{"label": "Alatos"}],
                    "outcomes": [
                        {
                            "id": "complete",
                            "conditions": {
                                "items": [{"anyOf": [code], "count": 1} for code in ("MISC69", "MISC70", "MISC71")]
                            },
                            "effects": {"xp": 4000, "hostile": [{"label": "Resar"}]},
                            "terminal": True,
                        }
                    ],
                }
            ],
        }
        driver = Driver()
        with ExitStack() as stack:
            stack.enter_context(patch.object(routes, "documents", return_value=data))
            stack.enter_context(patch.object(routes, "currentArea", return_value="AR0153"))
            stack.enter_context(patch.object(routes, "travel", side_effect=lambda *_args: None))
            stack.enter_context(
                patch.object(routes, "contactCityObject", side_effect=lambda _driver, name: driver.contact(name))
            )
            routes.questRoute(driver, "alatosTheft", "complete")
        return driver

    def testAlatosCompletesTheDelayedNativeBetrayalBeforeTheUnchangedRepeatBaseline(self):
        driver = self.alatosBetrayalRouteModel()
        self.assertLess(driver.events.index("native-death"), driver.events.index("save-reload"))
        self.assertEqual(driver.captured_handles, set(driver.transfers))
        self.assertEqual(4, len(driver.transfers))
        self.assertEqual(1, driver.combats)
        self.assertEqual((1614, 14000), (driver.coins, driver.exp))
        self.assertEqual(42, driver.checks[0][1]["resarNativeVictorySeq"])
        self.assertEqual(4, len(driver.checks[0][1]["resarSourcePossessions"]))

    def testAlatosCreditsAnEarlierNativeVictoryOnlyWithActualDeathAndFreshReceipt(self):
        driver = self.alatosBetrayalRouteModel("alreadyWon")
        self.assertNotIn("native-approach", driver.events)
        self.assertEqual(1, driver.combats)
        for mutation, message in [
            ("missingReceipt", "Missing fresh native Resar victory"),
            ("staleReceipt", "Missing fresh native Resar victory"),
            ("wrongOpponent", "Missing fresh native Resar victory"),
            ("removedAlive", "removed living actor"),
        ]:
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, message):
                self.alatosBetrayalRouteModel(mutation)

    def testAlatosRejectsClonedLootAndChangedSourceQuantities(self):
        for mutation, message in [("clonedLoot", "new item replaced owned Resar loot"), ("changedQuantity", "1 != 2")]:
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, message):
                self.alatosBetrayalRouteModel(mutation)

    def testAlatosDoesNotHideAnEarlyCombatXpDeltaOrASecondQuestReward(self):
        for mutation, message in [
            ("earlyXp", "14000 != 14073"),
            ("repeatReward", "Returning after a quest reward paid twice"),
        ]:
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, message):
                self.alatosBetrayalRouteModel(mutation)


if __name__ == "__main__":
    unittest.main()
