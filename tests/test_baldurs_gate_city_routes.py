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
        with patch.object(routes, "travel") as travel:
            after = routes.openContainer(driver, "cityAr0800Container1")
        travel.assert_called_once_with(driver, "AR0800")
        self.assertEqual((1017, 10000, Counter({"RING10": 2})), after)
        self.assertEqual(("navigate", "cityAr0800Container1"), driver.actions[0])
        self.assertEqual(2, sum(action[0] == "choice" for action in driver.actions))
        for mutations in ({"duplicate": True}, {"wrong_gold": True}):
            with self.subTest(mutations=mutations), patch.object(routes, "travel"):
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


if __name__ == "__main__":
    unittest.main()
