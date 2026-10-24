# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure Nouraajd service sequencing and finite earned-funding regressions."""

import ast
from collections import deque
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import gameplay_routes_nouraajd as nouraajd
from tests.test_gameplay_route_dialogs import authoredFunction
from tests.hook_flow_support import installHookFlows


class GameplayNouraajdServiceRoutesTest(unittest.TestCase):
    def testAmuletHandInSettlesTheNativeJournalBeforeItsRewardReceipt(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "res/maps/nouraajd/script.py").read_text(encoding="utf-8")
        )
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        selected = []
        for class_id, method_name in (
            ("QuestReturnDialog", "complete_amulet_quest"),
            ("QuestSystem", "finish_amulet"),
            ("QuestSystem", "is_amulet_returned"),
            ("AmuletQuest", "isCompleted"),
        ):
            method = next(
                node
                for node in classes[class_id].body
                if isinstance(node, ast.FunctionDef) and node.name == method_name
            )
            method.decorator_list = []
            selected.append(method)
        state = SimpleNamespace(
            stage="active", gold=200, claimed=False, requests=[], actors={"amuletGoblin", "oldWoman"}
        )
        amulet = SimpleNamespace(getName=lambda: "preciousAmulet")
        other = SimpleNamespace(getName=lambda: "otherItem")
        items = [amulet, other]
        player = SimpleNamespace(
            hasItem=lambda predicate: any(predicate(item) for item in items),
            removeItem=lambda predicate, quest: items.remove(next(item for item in items if predicate(item))),
            addGold=lambda amount: setattr(state, "gold", state.gold + amount),
        )
        game_map = SimpleNamespace(getPlayer=lambda: player)
        game = SimpleNamespace(getMap=lambda: game_map)
        dialog = SimpleNamespace(getGame=lambda: game)
        quest = SimpleNamespace()
        active, completed = [quest], []
        quest_system = SimpleNamespace(
            get_state=lambda name: state.stage,
            set_state=lambda name, value: setattr(state, "stage", value),
        )

        def claim(owner, key):
            self.assertIs(game_map, owner)
            self.assertEqual("AMULET_REWARD_CLAIMED", key)
            if state.claimed:
                return False
            state.claimed = True
            return True

        def removeActors(owner, *, names):
            self.assertIs(game_map, owner)
            self.assertEqual(("amuletGoblin", "oldWoman"), names)
            state.actors.difference_update(names)
            yield from ()

        def receipt(owner, title, before, message):
            self.assertIs(game, owner)
            self.assertEqual("Amulet returned", title)
            self.assertEqual(200, before)
            self.assertIn("50 gold", message)
            yield "receipt", ()

        scope = {
            "flowGame": lambda owner: owner,
            "_quest_system_from": lambda owner: quest_system,
            "claim_once": claim,
            "rewardSnapshot": lambda owner: state.gold,
            "removeRuntimeActorsFlow": removeActors,
            "showRewardReceiptFlow": receipt,
            "uiRequest": lambda operation, *args: (operation, args),
        }
        exec(compile(ast.Module(body=selected, type_ignores=[]), "<selected-amulet-hand-in>", "exec"), scope)
        quest_system.finish_amulet = lambda: scope["finish_amulet"](quest_system)
        quest_system.is_amulet_returned = lambda: scope["is_amulet_returned"](quest_system)
        flow = scope["complete_amulet_quest"](dialog)
        self.addCleanup(flow.close)
        operation, args = next(flow)
        self.assertEqual("gui.checkQuests", operation)
        self.assertEqual((player,), args)
        self.assertTrue(scope["isCompleted"](quest))
        self.assertEqual((250, "returned", True), (state.gold, state.stage, state.claimed))
        self.assertEqual([other], items)
        self.assertEqual(set(), state.actors)
        self.assertEqual([quest], active)
        # Model the existing native checkQuestsAsync membership move after this request is acknowledged.
        active.remove(quest)
        completed.append(quest)
        self.assertEqual(("receipt", ()), flow.send(None))
        self.assertEqual(([quest], []), (completed, active))
        with self.assertRaises(StopIteration):
            flow.send(None)
        self.assertEqual([], list(scope["complete_amulet_quest"](dialog)))
        self.assertEqual((250, [other], [quest]), (state.gold, items, completed))

    def victorScrollFixture(self):
        source = json.loads(
            (Path(__file__).resolve().parents[1] / "res/maps/nouraajd/map.json").read_text(encoding="utf-8")
        )
        original = [
            actor
            for layer in source["layers"]
            if layer["type"] == "objectgroup"
            for actor in layer["objects"]
            if actor["name"] == "townPortalScroll" and actor["type"] == "TownPortalScroll"
        ]
        self.assertEqual(1, len(original))
        entry = tuple(int(source["properties"][axis]) for axis in "xyz")
        state = {
            "position": (49, 99, 0),
            "turn": 300,
            "spawn": 299,
            "inventory": {"original", "extra", "quest"},
            "events": [],
            "records": [],
        }
        identities = {
            "original": (original[0]["name"], original[0]["type"]),
            "extra": ("legitimatelyCraftedOtherScroll", "TownPortalScroll"),
            "quest": ("letterFromRolf", "letterFromRolf"),
        }
        game, game_map, player = ({"__handle__": name} for name in ("game", "map", "player"))
        map_object = SimpleNamespace(getEntryX=lambda: entry[0], getEntryY=lambda: entry[1], getEntryZ=lambda: entry[2])
        player_object = SimpleNamespace(
            getMap=lambda: map_object, moveTo=lambda x, y, z: state.update(position=(x, y, z))
        )
        on_use = authoredFunction("res/plugins/object.py", "onUse", class_id="TownPortalScroll")

        def call(handle, method, *args):
            if method == "getItems":
                return [{"__handle__": name} for name in sorted(state["inventory"])]
            if method in ("getName", "getTypeId"):
                return identities[handle["__handle__"]][int(method == "getTypeId")]
            if method == "useItem":
                name = args[0]["__handle__"]
                self.assertIn(name, state["inventory"])
                state["events"].append(("useItem", name))
                on_use(None, SimpleNamespace(getCause=lambda: player_object))
                state["inventory"].remove(name)
                return
            return {
                "getEntryX": entry[0],
                "getEntryY": entry[1],
                "getEntryZ": entry[2],
                "getTurn": state["turn"],
                "getMap": game_map,
                "getPlayer": player,
                "getStringProperty": "",
                "getHp": 70,
            }[method]

        driver = SimpleNamespace(
            test=self,
            game=game,
            game_map=game_map,
            player=player,
            call=call,
            coords=lambda: state["position"],
            object=lambda name, required=False: None if name == "townPortalScroll" else "leader",
            number=lambda name: state["spawn"],
            string=lambda name: "encounter_active",
            flag=lambda name: False,
            gold=lambda: 200,
            questNames=lambda completed=False: ["rolfQuest"] if completed else ["victorQuest"],
            pump=lambda: state["events"].append(("pump",)),
            record=state["records"].append,
            check=lambda branch, condition, **kwargs: self.assertTrue(condition),
        )
        return driver, state

    def testStandaloneVictorEscapeUsesOnlyTheActualSourceScrollWithoutAdvancingTheDeadline(self):
        driver, state = self.victorScrollFixture()
        nouraajd.retreatVictorWithCollectedScroll(driver)
        self.assertEqual((110, 111, 0), state["position"])
        self.assertEqual({"extra", "quest"}, state["inventory"])
        self.assertEqual([("useItem", "original"), ("pump",)], state["events"])
        self.assertEqual((300, 299), (state["turn"], state["spawn"]))
        self.assertEqual("original", state["records"][0]["earnedVictorEscape"])

    def testStandaloneVictorEscapeRejectsMissingSourceIdentityAndAnyNativeTurnChange(self):
        driver, state = self.victorScrollFixture()
        state["inventory"].remove("original")
        with self.assertRaisesRegex(AssertionError, "original actually collected"):
            nouraajd.retreatVictorWithCollectedScroll(driver)
        self.assertEqual([], state["events"])
        driver, state = self.victorScrollFixture()
        driver.pump = lambda: state.update(turn=state["turn"] + 1)
        with self.assertRaisesRegex(AssertionError, "native deadline"):
            nouraajd.retreatVictorWithCollectedScroll(driver)
        self.assertEqual([], state["records"])

    def testOnlyStandaloneDirectLossEscapesBeforeTheUnchangedTimeoutAndSaveBoundaries(self):
        class ReachedNativeBoundary(Exception):
            pass

        for start_new, direct, saved in (
            (True, True, False),
            (False, True, False),
            (True, False, False),
            (True, True, True),
        ):
            with self.subTest(start_new=start_new, direct=direct, saved=saved):
                driver, state = self.victorScrollFixture()
                actual_call = driver.call
                driver.call = lambda handle, method, *args: (
                    "forceful"
                    if method == "getStringProperty" and args == ("campaign_var_nouraajdVictorConfrontation",)
                    else actual_call(handle, method, *args)
                )
                expected_escape = start_new and direct and not saved

                def stop(driver, elapsed=None):
                    self.assertEqual(expected_escape, "original" not in state["inventory"])
                    self.assertEqual((110, 111, 0) if expected_escape else (49, 99, 0), driver.coords())
                    if not saved:
                        self.assertEqual(74, elapsed)
                    raise ReachedNativeBoundary

                driver.fight = lambda name: stop(driver)
                with (
                    patch.object(nouraajd, "start"),
                    patch.object(nouraajd, "prepareRolf"),
                    patch.object(nouraajd, "meetVictor"),
                    patch.object(nouraajd, "victorCountdownCheckpoint") as checkpoint,
                    patch.object(nouraajd, "fleeCourtyardUntil", side_effect=stop),
                ):
                    with self.assertRaises(ReachedNativeBoundary):
                        nouraajd.victorRoute(driver, "forceful", direct, saved, start_new=start_new)
                    checkpoint.assert_called_once_with(driver, "victor-active-countdown", credit=True)

    def testBothFullCampaignOutcomesUseRecordsAndPreserveTheirEndingAndHistory(self):
        from tests import gameplay_routes_campaigns as campaigns

        for outcome in ("good", "bad"):
            with self.subTest(outcome=outcome):
                saved = outcome == "good"
                approach = "deescalated" if saved else "forceful"
                gate = "cooperative" if saved else "threatened"
                history = (
                    "recovery:completed,cleansing:" + ("good_ending" if saved else "bad_ending") + ",siege:completed"
                )
                state = {"order": [], "properties": {}, "branches": []}
                driver = SimpleNamespace(test=self, player=object(), map_name="nouraajd")

                def start(route_driver, **kwargs):
                    self.assertIs(driver, route_driver)
                    self.assertEqual({"gate": gate, "deed": True}, kwargs)
                    state["order"].append("start")
                    state["properties"]["campaign_var_nouraajdGateApproach"] = gate

                def victor(route_driver, actual_approach, **kwargs):
                    self.assertIs(driver, route_driver)
                    self.assertEqual(approach, actual_approach)
                    self.assertEqual({"direct": False, "saved": saved, "start_new": False}, kwargs)
                    state["order"].append("victor-records")
                    state["properties"].update(
                        campaign_var_nouraajdVictorConfrontation=approach,
                        campaign_var_nouraajdVictorOutcome="rescued" if saved else "lost",
                        nouraajdVictorState="good_end" if saved else "bad_end",
                    )

                def chain(route_driver, order, **kwargs):
                    self.assertEqual((driver, "LRHB", {"start_new": False}), (route_driver, order, kwargs))
                    state["order"].append("LRHB")
                    driver.map_name = "ritual"
                    state["properties"]["campaign_history"] = "recovery:completed"

                def finish(route_driver, actual_outcome, **kwargs):
                    self.assertEqual((driver, outcome), (route_driver, actual_outcome))
                    self.assertEqual({"activation": "anchor" if saved else "threshold"}, kwargs)
                    state["order"].append("ritual-and-siege")
                    driver.map_name = "siege"
                    state["properties"].update(campaign_history=history, campaign_finished=True)

                def check(branch, condition, **evidence):
                    self.assertTrue(condition, (branch, evidence))
                    state["branches"].append(branch)

                driver.hunt = lambda method: state["order"].append(method)
                driver.call = lambda handle, method, name: state["properties"][name]
                driver.check = check
                driver.saveAndReload = Mock()
                with (
                    patch.object(nouraajd, "start", side_effect=start),
                    patch.object(nouraajd, "prepareRolf", side_effect=lambda d: state["order"].append("rolf")),
                    patch.object(nouraajd, "victorRoute", side_effect=victor),
                    patch.object(nouraajd, "chainRoute", side_effect=chain),
                    patch.object(campaigns, "finishRitualAndSiege", side_effect=finish),
                ):
                    nouraajd.campaignRoute(driver, outcome)
                self.assertEqual(
                    ["start", "rolf", "finishOriginalMainQuest", "victor-records", "LRHB", "ritual-and-siege"],
                    state["order"],
                )
                self.assertEqual(
                    ["nouraajd.campaign.toRitual", "nouraajd.campaign." + outcome, "nouraajd.campaign.persisted"],
                    state["branches"],
                )
                driver.saveAndReload.assert_called_once_with("nouraajd-campaign-" + outcome)

    def testCampaignRecordsDeclarationsKeepEveryStandaloneCourtyardOutcomeForAllFiveClasses(self):
        from tests.gameplay_branch_types import PLAYER_CLASSES

        cases = {case.id: case for case in nouraajd.CASES}
        for outcome in ("good", "bad"):
            with self.subTest(campaign=outcome):
                case = cases["nouraajd_campaign_" + outcome]
                self.assertIn("nouraajd.victor.entry.records", case.branches)
                self.assertNotIn("nouraajd.victor.entry.courtyard", case.branches)
                self.assertEqual(PLAYER_CLASSES, case.classes)
        for approach in ("forceful", "deescalated"):
            for saved in (False, True):
                case_id = f"nouraajd_victor_{approach}_courtyard_{'saved' if saved else 'lost'}"
                with self.subTest(standalone=case_id):
                    case = cases[case_id]
                    self.assertEqual(PLAYER_CLASSES, case.classes)
                    self.assertIs(nouraajd.victorRoute, case.run.func)
                    self.assertEqual({"approach": approach, "direct": True, "saved": saved}, case.run.keywords)
                    self.assertIn("nouraajd.victor.entry.courtyard", case.branches)
                    self.assertIn("nouraajd.victor.countdownPersisted", case.branches)
                    self.assertIn("nouraajd.victor.endingPersisted", case.branches)
                    if saved:
                        self.assertIn("nouraajd.victor.rescued", case.branches)
                    else:
                        self.assertIn("nouraajd.victor.activeBeforeDeadline", case.branches)
                        self.assertIn("nouraajd.victor.lostAtDeadline", case.branches)

    def courtyardFleeFixture(self, walkable=None):
        from tests.narrative_walkthrough import authoredRegion

        document = json.loads(
            (Path(__file__).resolve().parents[1] / "res/maps/nouraajd/map.json").read_text(encoding="utf-8")
        )
        walls = {
            (
                int(actor["x"] // document["tilewidth"]),
                int(actor["y"] // document["tileheight"]),
                int(layer["properties"]["level"]),
            )
            for layer in document["layers"]
            if layer["type"] == "objectgroup"
            for actor in layer["objects"]
            if actor["type"] == "brickWall" and not actor["name"]
        }
        if walkable is None:
            walkable = authoredRegion("nouraajd")[1] - walls
        state = {
            "turn": 10,
            "position": (40, 96, 0),
            "enemy": (40, 98, 0),
            "quest": "encounter_active",
            "leader": True,
            "steps": [],
            "probes": {},
            "walls": walls,
            "walkable": walkable,
            "document": document,
        }
        quest = SimpleNamespace(
            get_state=lambda name: state["quest"],
            mark_victor_bad_end=lambda: state.update(quest="bad_end"),
        )
        game_map = SimpleNamespace(
            getNumericProperty=lambda name: 10,
            getTurn=lambda: state["turn"],
            getGame=lambda: None,
            getObjects=lambda: [{"__handle__": "player"}] + ([{"__handle__": "leader"}] if state["leader"] else []),
        )
        hooks = installHookFlows({"showReader": Mock()})

        def clearVictorEncounterFlow(game_map):
            state.update(leader=False)
            yield from ()

        expire_flow = authoredFunction(
            "res/maps/nouraajd/script.py",
            "expireVictorSearchFlow",
            _get_quest_system=lambda game_map: quest,
            clearVictorEncounterFlow=clearVictorEncounterFlow,
            VICTOR_COURTYARD_TIMEOUT_TURNS=75,
            **hooks,
        )
        state["expire"] = lambda: hooks["runUiFlow"](None, expire_flow(game_map))

        def can_step(target):
            state["probes"].setdefault(state["turn"], []).append(target)
            return target in walkable

        def step(target):
            origin = state["position"]
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(target, origin)))
            self.assertIn(target, walkable)
            enemy = state["enemy"]
            neighbors = [
                (enemy[0] + dx, enemy[1] + dy, enemy[2])
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))
                if (enemy[0] + dx, enemy[1] + dy, enemy[2]) in walkable
            ]
            state["enemy"] = min(neighbors, key=lambda point: (sum(abs(a - b) for a, b in zip(point, origin)), point))
            state["position"] = target
            state["steps"].append(target)
            self.assertGreater(sum(abs(a - b) for a, b in zip(target, state["enemy"])), 1)
            state["expire"]()
            state["turn"] += 1

        def call(handle, method, *args):
            if handle is game_map:
                return getattr(handle, method)(*args)
            if method == "getStringProperty":
                self.assertEqual(("affiliation",), args)
                return ""
            return {"getType": "CCreature", "isAlive": True, "isNpc": False}[method]

        driver = SimpleNamespace(
            test=self,
            game_map=game_map,
            player={"__handle__": "player"},
            number=lambda name: 10,
            call=call,
            coords=lambda handle=None: state["enemy"] if handle else state["position"],
            object=lambda name, required=False: "leader" if name == "cultLeaderQuest" and state["leader"] else None,
            canStep=can_step,
            step=step,
            string=lambda name: state["quest"],
        )
        return driver, state

    def testVictorFleeRejectsTheRawUnnamedWallCornerBeforeEnteringIt(self):
        driver, state = self.courtyardFleeFixture()
        self.assertTrue({(39, 95, 0), (38, 96, 0)} <= state["walls"])
        nouraajd.fleeCourtyardUntil(driver, 1)
        self.assertEqual([(41, 96, 0)], state["steps"])
        self.assertNotIn((39, 96, 0), state["steps"], "The old greedy choice is the authored closed corner")

    def testVictorFleeLeavesTheActualWallEnclosureWithOneAdvancingPursuerInThePureModel(self):
        driver, state = self.courtyardFleeFixture()
        door, distances = nouraajd.courtyardExitDistances()
        self.assertIn(state["position"], distances)
        self.assertNotIn((39, 95, 0), distances)
        nouraajd.fleeCourtyardUntil(driver, 76, allow_timeout=True)
        self.assertIn(door, state["steps"])
        self.assertEqual(76, len(state["steps"]))
        self.assertEqual("bad_end", state["quest"])
        for probes in state["probes"].values():
            self.assertLessEqual(len(probes), 64)
            self.assertEqual(len(probes), len(set(probes)))

    def testVictorExitPlannerRejectsAnotherRawWallOpeningInsteadOfAssumingTheDoorIsTheSoleExit(self):
        _driver, state = self.courtyardFleeFixture()
        for layer in state["document"]["layers"]:
            if layer["type"] == "objectgroup":
                layer["objects"] = [
                    actor
                    for actor in layer["objects"]
                    if not (
                        actor["type"] == "brickWall"
                        and int(actor["x"] // state["document"]["tilewidth"]) == 39
                        and int(actor["y"] // state["document"]["tileheight"]) == 95
                    )
                ]
        nouraajd.courtyardExitDistances.cache_clear()
        try:
            with patch.object(nouraajd.json, "loads", return_value=state["document"]):
                with self.assertRaisesRegex(AssertionError, "single authored exit"):
                    nouraajd.courtyardExitDistances()
        finally:
            nouraajd.courtyardExitDistances.cache_clear()

    def testVictorRecordsEscapeKeepsAllFiveAuthoredPursuersBehindInThePureModel(self):
        driver, state = self.courtyardFleeFixture()
        source = ast.parse(
            (Path(__file__).resolve().parents[1] / "res/maps/nouraajd/script.py").read_text(encoding="utf-8")
        )
        values = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in ast.walk(source)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("VICTOR_COURTYARD_SPAWNS", "VICTOR_COURTYARD_LEADER_SPAWN")
        }
        names = ("cultLeaderQuest", *("victorCultist" + str(index) for index in range(1, 5)))
        enemies = dict(zip(names, (values["VICTOR_COURTYARD_LEADER_SPAWN"], *values["VICTOR_COURTYARD_SPAWNS"])))
        town_hall = next(
            (actor, layer)
            for layer in state["document"]["layers"]
            if layer["type"] == "objectgroup"
            for actor in layer["objects"]
            if actor["name"] == "nouraajdTownHall"
        )
        actor, layer = town_hall
        state["position"] = (
            int(actor["x"] // state["document"]["tilewidth"]),
            int(actor["y"] // state["document"]["tileheight"]),
            int(layer["properties"]["level"]),
        )
        driver.object = lambda name, required=False: name if name in enemies and state["leader"] else None
        driver.coords = lambda actor=None: enemies[actor["__handle__"]] if actor else state["position"]
        driver.game_map.getObjects = lambda: [{"__handle__": "player"}] + (
            [{"__handle__": name} for name in enemies] if state["leader"] else []
        )

        def neighbors(point):
            return [(point[0] + dx, point[1] + dy, point[2]) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))]

        def step(target):
            origin = state["position"]
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(target, origin)))
            self.assertIn(target, state["walkable"])
            needed = {point for enemy in enemies.values() for point in neighbors(enemy) if point in state["walkable"]}
            distances = {origin: 0}
            pending = deque([origin])
            while pending and not needed <= distances.keys():
                position = pending.popleft()
                for point in neighbors(position):
                    if point in state["walkable"] and point not in distances:
                        distances[point] = distances[position] + 1
                        pending.append(point)
            for name, enemy in tuple(enemies.items()):
                options = [point for point in neighbors(enemy) if point in distances]
                enemies[name] = min(options, key=lambda point: (distances[point], point))
            self.assertGreater(min(sum(abs(a - b) for a, b in zip(target, enemy)) for enemy in enemies.values()), 1)
            state["position"] = target
            state["steps"].append(target)
            state["expire"]()
            state["turn"] += 1

        driver.step = step
        nouraajd.fleeCourtyardUntil(driver, 76, allow_timeout=True)
        self.assertIn(nouraajd.courtyardExitDistances()[0], state["steps"])
        self.assertEqual(76, len(state["steps"]))
        self.assertEqual("bad_end", state["quest"])
        self.assertEqual(5, len(enemies), "This pure model retains all authored pursuers and models no NPC combat")
        self.assertTrue(
            all(len(probes) <= 64 and len(probes) == len(set(probes)) for probes in state["probes"].values())
        )

    def testVictorFleePreservesTheActualSeventyFourSeventyFiveAndSeventySixTurnBoundary(self):
        driver, state = self.courtyardFleeFixture({(x, 110, 0) for x in range(45, 160)})
        state["position"], state["enemy"] = (60, 110, 0), (45, 110, 0)
        for elapsed, expected in ((74, "encounter_active"), (75, "encounter_active"), (76, "bad_end")):
            nouraajd.fleeCourtyardUntil(driver, elapsed, allow_timeout=elapsed == 76)
            self.assertEqual(10 + elapsed, state["turn"])
            self.assertEqual(elapsed, len(state["steps"]))
            self.assertEqual(expected, state["quest"])
        self.assertFalse(state["leader"])
        for probes in state["probes"].values():
            self.assertLessEqual(len(probes), 64)
            self.assertEqual(len(set(probes)), len(probes), "Every native cell is memoized per decision")

    def testVictorFleeFailsBeforeMovementWhenNativeCellProbeBudgetIsExhausted(self):
        driver, state = self.courtyardFleeFixture()
        state["position"], state["enemy"] = (0, 0, 0), (500, 500, 0)
        # Four induced trees each end after five hops: none can certify the sixth.
        tree = {(0, 0, 0)}
        for sign in (-1, 1):
            tree.update((sign * offset, 0, 0) for offset in range(1, 6))
            tree.update((0, sign * offset, 0) for offset in range(1, 6))
            for branch_sign in (-1, 1):
                tree.update((sign * 3, branch_sign * offset, 0) for offset in (1, 2))
                tree.update((branch_sign * offset, sign * 3, 0) for offset in (1, 2))

        def can_step(target):
            state["probes"].setdefault(state["turn"], []).append(target)
            return target in tree

        driver.canStep = can_step
        driver.step = Mock()
        with self.assertRaisesRegex(AssertionError, "exhausted 64 distinct native cell probes"):
            nouraajd.fleeCourtyardUntil(driver, 1)
        driver.step.assert_not_called()
        self.assertEqual(10, state["turn"])
        self.assertEqual(64, len(state["probes"][10]))
        self.assertEqual(64, len(set(state["probes"][10])))

    def testVictorFleeReportsBoundedRejectionEvidenceWithoutEnteringAnUnsafeCell(self):
        driver, state = self.courtyardFleeFixture()
        state["position"], state["enemy"] = (39, 96, 0), (40, 97, 0)
        driver.step = Mock()
        with self.assertRaisesRegex(AssertionError, "nativeCellProbes") as raised:
            nouraajd.fleeCourtyardUntil(driver, 1)
        self.assertIn("lookaheadHops", str(raised.exception))
        driver.step.assert_not_called()
        self.assertEqual(10, state["turn"])
        self.assertLessEqual(len(state["probes"].get(10, [])), 64)

    def testPaidRaceAidEarnsTheGoobyRewardAfterRolfsUnpaidQuest(self):
        class ReachedUnneededAid(Exception):
            pass

        for race_id in ("outlanderRace", "highlanderRace", "wandererRace"):
            with self.subTest(race=race_id):
                state = {"gold": 0, "completed": [], "claims": set(), "order": []}
                player = SimpleNamespace(
                    getGold=lambda: state["gold"],
                    addGold=lambda amount: state.update(gold=state["gold"] + amount),
                    getHp=lambda: 100,
                    getHpMax=lambda: 100,
                    getMana=lambda: 100,
                    getManaMax=lambda: 100,
                )
                game_map = SimpleNamespace(getPlayer=lambda: player)
                game = SimpleNamespace(getMap=lambda: game_map, getGuiHandler=lambda: SimpleNamespace(notify=Mock()))

                def claim_once(owner, name):
                    if name in state["claims"]:
                        return False
                    state["claims"].add(name)
                    return True

                rolf_complete = authoredFunction("res/maps/nouraajd/script.py", "onComplete", class_id="RolfQuest")
                gooby_complete = authoredFunction(
                    "res/maps/nouraajd/script.py",
                    "onComplete",
                    class_id="MainQuest",
                    claim_once=claim_once,
                    MAIN_QUEST_GOLD_REWARD=200,
                    rewardSnapshot=Mock(return_value={}),
                    showRewardReceipt=Mock(),
                )
                apply_aid = authoredFunction(
                    "res/maps/nouraajd/script.py", "_applyRaceService", class_id="TownHallDialog", showReader=Mock()
                )
                owner = SimpleNamespace(getGame=lambda: game)
                dialog = SimpleNamespace(
                    getGame=lambda: game, _canOfferRaceService=lambda identity: identity == race_id
                )

                def prepare(driver):
                    rolf_complete(owner)
                    state["completed"].append("rolfQuest")
                    state["order"].append("rolf-unpaid")
                    self.assertEqual(0, state["gold"], "Rolf's authored quest completion pays no gold")

                def hunt(method, *args):
                    if method == "finishOriginalMainQuest":
                        gooby_complete(owner)
                        state["completed"].append("mainQuest")
                        state["order"].append("gooby-reward")
                    elif method == "recoverOnRoadPair":
                        state["order"].append("actual-road-recovery")
                    else:
                        self.fail((method, args))

                def check(branch, condition, **evidence):
                    self.assertTrue(condition, (branch, evidence))
                    if branch.endswith(".unneeded"):
                        state["order"].append("funded-unneeded-aid")
                        raise ReachedUnneededAid

                def choose(dialog_id, action, **kwargs):
                    _suffix, _gold, hp, mana = nouraajd.RACES[race_id]
                    self.assertFalse(apply_aid(dialog, race_id, 5, hp, mana, "aid"))

                def call(handle, method, *args):
                    if method == "getBoolProperty":
                        return False
                    return getattr(player, method)()

                driver = SimpleNamespace(
                    test=self,
                    race_id=race_id,
                    player={"__handle__": "player"},
                    gold=player.getGold,
                    navigateTo=Mock(),
                    condition=lambda dialog_id, name: name == "canOffer" + nouraajd.RACES[race_id][0],
                    choose=choose,
                    check=check,
                    call=call,
                    hunt=Mock(side_effect=hunt),
                    questNames=lambda completed=False: list(state["completed"]) if completed else [],
                )
                with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf", side_effect=prepare):
                    with self.assertRaises(ReachedUnneededAid):
                        nouraajd.raceAid(driver)
                self.assertEqual(200, state["gold"])
                self.assertEqual(
                    ["rolf-unpaid", "gooby-reward", "actual-road-recovery", "funded-unneeded-aid"], state["order"]
                )

    def highlanderMutilationFixture(self, *, combat_damage=12):
        state = {
            "gold": 0,
            "hp": 100,
            "mana": 100,
            "claimed": False,
            "kind": "",
            "completed": [],
            "combat": [],
            "choices": [],
            "branches": [],
            "inventory": ("starter", "original-portal", "quest-item"),
        }
        action_config = json.loads(
            (Path(__file__).resolve().parents[1] / "res/config/interactions.json").read_text(encoding="utf-8")
        )["Mutilation"]["properties"]
        mutilate = authoredFunction("res/plugins/interaction.py", "performAction", class_id="Mutilation")
        creatures = {}
        for index in range(1, 5):
            actor_state = {"hp": 20}
            creatures[f"victorCultist{index}"] = SimpleNamespace(
                isAlive=lambda actor_state=actor_state: actor_state["hp"] > 0,
                hurt=lambda damage, actor_state=actor_state: actor_state.update(hp=actor_state["hp"] - damage),
            )
        action = SimpleNamespace(
            getNumericProperty=lambda name: action_config[name],
            getBoolProperty=lambda name: action_config.get(name, False),
        )
        player = SimpleNamespace(
            getGold=lambda: state["gold"],
            addGold=lambda amount: state.update(gold=state["gold"] + amount),
            getHp=lambda: state["hp"],
            getHpMax=lambda: 100,
            getMana=lambda: state["mana"],
            getManaMax=lambda: 100,
            getDmg=lambda: 20,
            heal=lambda amount: state.update(hp=state["hp"] + amount),
            addMana=lambda amount: state.update(mana=state["mana"] + amount),
            getBoolProperty=lambda name: state["claimed"],
            setBoolProperty=lambda name, value: state.update(claimed=value),
            getStringProperty=lambda name: state["kind"],
            setStringProperty=lambda name, value: state.update(kind=value),
            getEffectiveInteractions=lambda: [action],
            getItems=lambda: state["inventory"],
        )
        game = SimpleNamespace(
            getMap=lambda: SimpleNamespace(getPlayer=lambda: player),
            getGuiHandler=lambda: SimpleNamespace(notify=Mock()),
        )
        apply_aid = authoredFunction(
            "res/maps/nouraajd/script.py", "_applyRaceService", class_id="TownHallDialog", showReader=Mock()
        )
        dialog = SimpleNamespace(
            getGame=lambda: game,
            _canOfferRaceService=lambda identity: identity == "highlanderRace" and not state["claimed"],
        )
        gooby_complete = authoredFunction(
            "res/maps/nouraajd/script.py",
            "onComplete",
            class_id="MainQuest",
            claim_once=lambda owner, name: True,
            MAIN_QUEST_GOLD_REWARD=200,
            rewardSnapshot=Mock(return_value={}),
            showRewardReceipt=Mock(),
        )

        def use_action(owned_action, target):
            self.assertIs(action, owned_action)
            self.assertIs(creatures["victorCultist1"], target)
            self.assertGreaterEqual(state["mana"], action_config["manaCost"])
            state["mana"] -= action_config["manaCost"]
            mutilate(None, player, target)

        player.useAction = use_action

        def hunt(method, *args):
            if method == "finishOriginalMainQuest":
                gooby_complete(SimpleNamespace(getGame=lambda: game))
                state["completed"].append("mainQuest")
            elif method == "recoverOnRoadPair":
                state.update(hp=100, mana=100)
            else:
                self.fail((method, args))

        def fight(name):
            self.assertTrue(creatures[name].isAlive(), "The route must not fight an ability-killed registered actor")
            state["combat"].append(name)
            state["hp"] -= combat_damage
            creatures[name].hurt(20)

        def choose(dialog_id, name, **kwargs):
            self.assertEqual(("townHallDialog", "claimHighlanderAid"), (dialog_id, name))
            state["choices"].append(apply_aid(dialog, "highlanderRace", 5, 10, 0, "aid"))

        def check(branch, condition, **evidence):
            self.assertTrue(condition, (branch, evidence))
            state["branches"].append(branch)

        driver = SimpleNamespace(
            test=self,
            race_id="highlanderRace",
            player=player,
            gold=player.getGold,
            navigateTo=Mock(),
            revisit=Mock(),
            condition=lambda dialog_id, name: name == "canOfferHighlanderAid" and not state["claimed"],
            choose=choose,
            check=check,
            call=lambda handle, method, *args: getattr(handle, method)(*args),
            hunt=hunt,
            questNames=lambda completed=False: list(state["completed"]) if completed else [],
            object=lambda name, required=True: creatures.get(name),
            fight=fight,
            pump=Mock(),
            saveAndReload=Mock(),
            recoveryEnabled=True,
        )
        return driver, state, creatures

    def highlanderPreVictorFixture(
        self, *, combat_damage=22, road_healing=4, native_full_heal=False, missing_victory=False
    ):
        driver, state, victor_creatures = self.highlanderMutilationFixture(combat_damage=combat_damage)
        state.update(hp=77, victor=False, route_order=[], records=[], native_proofs=[], registry={})
        player = driver.player
        player.heal = lambda amount: state.update(hp=100 if amount == 0 else min(100, state["hp"] + amount))
        road_step = authoredFunction("res/plugins/tile.py", "onStep", class_id="RoadTile")
        actors = {}
        for index in range(1, 6):
            name = "aidPritz" + str(index)
            actors[name] = {
                "__handle__": name,
                "name": name,
                "typeId": "Pritz",
                "affiliation": "gooby",
                "alive": True,
                "npc": False,
                "coords": (43 + index, 101, 0),
            }
        actors["neutral"] = {
            "__handle__": "neutral",
            "name": "neutral",
            "typeId": "Pritz",
            "affiliation": "cityResidents",
            "alive": True,
            "npc": False,
            "coords": (43, 101, 0),
        }
        actors["dead"] = {
            "__handle__": "dead",
            "name": "dead",
            "typeId": "Pritz",
            "affiliation": "gooby",
            "alive": False,
            "npc": False,
            "coords": (43, 101, 0),
        }
        actors["npc"] = {
            "__handle__": "npc",
            "name": "npc",
            "typeId": "Pritz",
            "affiliation": "gooby",
            "alive": True,
            "npc": True,
            "coords": (43, 101, 0),
        }
        state["registry"].update(actors)
        hall = {"__handle__": "townHall", "coords": (43, 101, 0)}
        original_call, original_hunt, original_fight = driver.call, driver.hunt, driver.fight
        game_map = SimpleNamespace(getObjects=lambda: list(actors.values()))

        def call(handle, method, *args):
            if isinstance(handle, dict):
                if method == "getTypeId":
                    return handle["typeId"]
                if method == "isAlive":
                    return handle["alive"]
                if method == "isNpc":
                    return handle["npc"]
                if method == "getStringProperty":
                    return handle[args[0]]
                if method == "getName":
                    return handle["name"]
            return original_call(handle, method, *args)

        def hunt(method, *args):
            original_hunt(method, *args)
            if method == "finishOriginalMainQuest":
                state["route_order"].append("actual-gooby-reward")
            if method == "recoverOnRoadPair":
                state["route_order"].append("funded-road-recovery")

        def object_by_name(name, required=True):
            if name == "nouraajdTownHall":
                return hall
            if name in victor_creatures:
                return victor_creatures[name]
            return state["registry"].get(name)

        def fight(name):
            if name in victor_creatures:
                original_fight(name)
                player.heal(0)  # Retained CI counterexample: authored Victor reward restores full HP.
                return
            self.assertEqual("Pritz", actors[name]["typeId"])
            self.assertEqual("gooby", actors[name]["affiliation"])
            self.assertTrue(actors[name]["alive"])
            self.assertFalse(actors[name]["npc"], "The model must never fight the authored NPC control")
            state["combat"].append(name)
            state["route_order"].append("native-hostile-victory")
            actors[name]["alive"] = False
            state["registry"].pop(name, None)
            state["hp"] -= combat_damage
            if native_full_heal:
                player.heal(0)
            state["native_proofs"].append(name)

        def navigate(name):
            self.assertEqual("nouraajdTownHall", name)
            if state["native_proofs"]:
                heal = (
                    road_healing[len(state["native_proofs"]) - 1] if isinstance(road_healing, tuple) else road_healing
                )
                for _ in range(heal):
                    road_step(None, player)
                state["route_order"].append("actual-road-healing-return")

        original_check = driver.check

        def check(branch, condition, **evidence):
            original_check(branch, condition, **evidence)
            if branch.endswith(".unneeded"):
                state["route_order"].append("funded-unneeded")
            if branch.endswith(".claimed"):
                state["route_order"].append("paid-claim")

        driver.call, driver.hunt, driver.object, driver.fight = call, hunt, object_by_name, fight
        driver.game_map, driver.coords = game_map, lambda actor: actor["coords"]
        driver.navigateTo = Mock(side_effect=navigate)
        driver.flag = lambda key: (
            state["victor"] if key in ("TALKED_TO_VICTOR", "VICTOR_REWARD_GRANTED") else self.fail(key)
        )
        driver.assertNativeCombatOutcomes = Mock()
        driver._combat_trace_seq = 4
        driver.playerVictoryAgainst = Mock(
            side_effect=lambda world, name, **kwargs: (
                None if missing_victory else ({"seq": 5} if name in state["native_proofs"] else None)
            )
        )
        driver.record = lambda value, **kwargs: state["records"].append(value)
        driver.check = check
        return driver, state, actors

    def testHighlanderAidUsesFundedAuthoredPritzInjuryBeforeVictor(self):
        driver, state, actors = self.highlanderPreVictorFixture()
        with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf"), patch.object(
            nouraajd, "meetVictor", side_effect=lambda *args: state.update(victor=True)
        ) as victor:
            nouraajd.raceAid(driver)
        victor.assert_not_called()
        self.assertEqual(["aidPritz1"], state["combat"])
        self.assertEqual([False, False, True], state["choices"])
        self.assertEqual((195, 92, 100), nouraajd.aidSnapshot(driver))
        self.assertEqual(("starter", "original-portal", "quest-item"), state["inventory"])
        self.assertTrue(actors["neutral"]["alive"])
        self.assertTrue(actors["npc"]["alive"])
        self.assertTrue(driver.recoveryEnabled)
        self.assertEqual(
            ["nouraajd.aid.highlanderRace." + ending for ending in ("unfunded", "unneeded", "claimed", "persisted")],
            state["branches"],
        )
        self.assertEqual(
            [
                "actual-gooby-reward",
                "funded-road-recovery",
                "funded-unneeded",
                "native-hostile-victory",
                "actual-road-healing-return",
                "paid-claim",
            ],
            state["route_order"],
        )
        driver.playerVictoryAgainst.assert_called_once_with("nouraajd", "aidPritz1", after_seq=4)
        driver.saveAndReload.assert_called_once_with("racial-aid-highlanderRace")

    def testHighlanderAidStillRequiresRealDeficitAfterNativeHealingAndRoadReturn(self):
        for options in ({"combat_damage": 0}, {"road_healing": 22}, {"native_full_heal": True}):
            with self.subTest(options=options):
                driver, state, _actors = self.highlanderPreVictorFixture(**options)
                with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf"), patch.object(
                    nouraajd, "meetVictor", side_effect=lambda *args: state.update(victor=True)
                ), self.assertRaisesRegex(AssertionError, "Four authored opponents left no usable Highlander deficit"):
                    nouraajd.raceAid(driver)
                self.assertEqual((200, 100, 100), nouraajd.aidSnapshot(driver))
                self.assertEqual(4, len(state["combat"]))
                self.assertTrue(
                    _actors["aidPritz5"]["alive"], "The fifth eligible hostile exceeds the fixed work budget"
                )
                self.assertEqual([False, False], state["choices"])
                self.assertFalse(state["claimed"])
                self.assertTrue(driver.recoveryEnabled)
                driver.saveAndReload.assert_not_called()

    def testHighlanderAidRechecksAfterEachReturnWithoutChangingNativeHealing(self):
        driver, state, _actors = self.highlanderPreVictorFixture(road_healing=(22, 4, 4, 4))
        with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf"), patch.object(
            nouraajd, "meetVictor", side_effect=lambda *args: state.update(victor=True)
        ):
            nouraajd.raceAid(driver)
        self.assertEqual(["aidPritz1", "aidPritz2"], state["combat"])
        self.assertEqual(100, state["records"][0]["highlanderAidPreparation"]["afterReturn"][1])
        self.assertEqual(82, state["records"][1]["highlanderAidPreparation"]["afterReturn"][1])
        self.assertEqual([False, False, True], state["choices"])

    def testHighlanderAidRequiresExactCapturedOpponentAndNativeVictory(self):
        driver, state, actors = self.highlanderPreVictorFixture()
        changed = dict(actors["aidPritz1"], __handle__="replacement")
        state["registry"]["aidPritz1"] = changed
        with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf"), patch.object(
            nouraajd, "meetVictor", side_effect=lambda *args: state.update(victor=True)
        ), self.assertRaisesRegex(AssertionError, "opponent identity changed"):
            nouraajd.raceAid(driver)
        self.assertEqual([], state["combat"])
        self.assertFalse(state["claimed"])
        self.assertTrue(driver.recoveryEnabled)
        driver, state, _actors = self.highlanderPreVictorFixture(missing_victory=True)
        with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf"), patch.object(
            nouraajd, "meetVictor", side_effect=lambda *args: state.update(victor=True)
        ), self.assertRaisesRegex(AssertionError, "actual player's native victory"):
            nouraajd.raceAid(driver)
        self.assertEqual([False, False], state["choices"])
        self.assertFalse(state["claimed"])
        self.assertTrue(driver.recoveryEnabled)

    def testHighlanderAidKeepsPriorDriverRecoveryPolicyOnFailure(self):
        driver, state, _actors = self.highlanderPreVictorFixture()
        driver.recoveryEnabled = False
        driver.fight = Mock(side_effect=RuntimeError("native encounter failed"))
        with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf"), patch.object(
            nouraajd, "meetVictor", side_effect=lambda *args: state.update(victor=True)
        ), self.assertRaisesRegex(RuntimeError, "native encounter failed"):
            nouraajd.raceAid(driver)
        self.assertFalse(driver.recoveryEnabled)
        self.assertFalse(state["claimed"])
        self.assertEqual([False, False], state["choices"])
        driver.saveAndReload.assert_not_called()

    def testHighlanderAidRejectsExhaustedAuthoredHostilesWithoutAttackingAnNpc(self):
        driver, state, actors = self.highlanderPreVictorFixture()
        for name, actor in actors.items():
            if name.startswith("aidPritz"):
                actor["alive"] = False
        with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf"), patch.object(
            nouraajd, "meetVictor", side_effect=lambda *args: state.update(victor=True)
        ), self.assertRaisesRegex(AssertionError, "remaining living authored Pritz"):
            nouraajd.raceAid(driver)
        self.assertEqual([], state["combat"])
        self.assertEqual([False, False], state["choices"])
        self.assertTrue(actors["npc"]["alive"])
        self.assertTrue(actors["neutral"]["alive"])
        self.assertTrue(driver.recoveryEnabled)
        driver.saveAndReload.assert_not_called()

    def testHighlanderAidDeclaresItsTwoAdditionalSourcesWithoutDuplicatingDefaultSources(self):
        aid = next(case for case in nouraajd.CASES if case.id == "nouraajd_aid_highlanderRace")
        self.assertEqual(nouraajd.SOURCES + ("res/config/monsters.json", "res/plugins/tile.py"), aid.sources)
        self.assertEqual(len(aid.sources), len(set(aid.sources)))
        for race_id in nouraajd.RACES:
            case = next(case for case in nouraajd.CASES if case.id == "nouraajd_aid_" + race_id)
            self.assertEqual(600.0, case.duration_seconds)
            self.assertEqual(race_id, case.race)
            if race_id != "highlanderRace":
                self.assertEqual(nouraajd.SOURCES, case.sources)
        sentinel = ("res/plugins/tile.py",)
        self.assertEqual(sentinel, nouraajd.case("aid-source-override", (), nouraajd.raceAid, sources=sentinel).sources)

    def outlanderApplicableAidFixture(self):
        driver, state, creatures = self.highlanderMutilationFixture(combat_damage=0)
        driver.race_id = "outlanderRace"
        player = driver.player
        game = SimpleNamespace(
            getMap=lambda: SimpleNamespace(getPlayer=lambda: player),
            getGuiHandler=lambda: SimpleNamespace(notify=Mock()),
        )
        apply_aid = authoredFunction(
            "res/maps/nouraajd/script.py", "_applyRaceService", class_id="TownHallDialog", showReader=Mock()
        )
        dialog = SimpleNamespace(
            getGame=lambda: game,
            _canOfferRaceService=lambda identity: identity == "outlanderRace" and not state["claimed"],
        )

        def choose(dialog_id, name, **kwargs):
            self.assertEqual(("townHallDialog", "claimOutlanderRations"), (dialog_id, name))
            state["choices"].append(apply_aid(dialog, "outlanderRace", 5, 5, 5, "aid"))

        driver.condition = lambda dialog_id, name: name == "canOfferOutlanderRations" and not state["claimed"]
        driver.choose = choose
        driver.fight = Mock(side_effect=AssertionError("An applicable mana deficit needs no courtyard injury detour"))
        return driver, state, creatures

    def testOutlanderAidClaimsActualApplicableManaDeficitWithoutCourtyardDetour(self):
        driver, state, creatures = self.outlanderApplicableAidFixture()
        with (
            patch.object(nouraajd, "start"),
            patch.object(nouraajd, "prepareRolf"),
            patch.object(nouraajd, "meetVictor"),
        ):
            nouraajd.raceAid(driver)
        self.assertFalse(creatures["victorCultist1"].isAlive(), "The existing owned action still executes")
        driver.fight.assert_not_called()
        self.assertEqual([False, False, True], state["choices"])
        self.assertEqual((195, 100, 90), nouraajd.aidSnapshot(driver))
        self.assertEqual("outlanderRace", state["kind"])
        self.assertEqual(("starter", "original-portal", "quest-item"), state["inventory"])
        self.assertTrue(driver.recoveryEnabled)
        driver.saveAndReload.assert_called_once_with("racial-aid-outlanderRace")
        self.assertEqual(
            ["nouraajd.aid.outlanderRace." + outcome for outcome in ("unfunded", "unneeded", "claimed", "persisted")],
            state["branches"],
        )

    def testOutlanderApplicableAidStillRestoresRecoveryStateAfterOwnedActionFailure(self):
        driver, state, _creatures = self.outlanderApplicableAidFixture()
        driver.player.useAction = Mock(side_effect=RuntimeError("actual owned action failure"))
        with (
            patch.object(nouraajd, "start"),
            patch.object(nouraajd, "prepareRolf"),
            patch.object(nouraajd, "meetVictor"),
            self.assertRaisesRegex(RuntimeError, "actual owned action failure"),
        ):
            nouraajd.raceAid(driver)
        self.assertTrue(driver.recoveryEnabled)
        self.assertFalse(state["claimed"])
        self.assertEqual([False, False], state["choices"])
        driver.saveAndReload.assert_not_called()

    def testLetterAndRelicJournalAssertionsFollowTheNextOrdinaryNativeTurn(self):
        for route, quest_class, quest_id, predicate in (
            (nouraajd.letter, "DeliverLetterQuest", "deliverLetterQuest", "is_letter_delivered"),
            (nouraajd.handInRelic, "RetrieveRelicQuest", "retrieveRelicQuest", "is_relic_returned"),
        ):
            with self.subTest(quest=quest_id):
                state = {"resolved": False, "item": 1, "completed": [], "order": []}
                quest_system = SimpleNamespace(**{predicate: lambda: state["resolved"]})
                is_completed = authoredFunction(
                    "res/maps/nouraajd/script.py",
                    "isCompleted",
                    class_id=quest_class,
                    _quest_system_from=lambda owner: quest_system,
                )

                def choose(*args, **kwargs):
                    state.update(resolved=True, item=0)
                    self.assertTrue(is_completed(None))
                    self.assertEqual([], state["completed"], "Dialog callbacks do not run CPlayer.checkQuests")
                    state["order"].append("actual-delivery")

                def tick():
                    self.assertTrue(is_completed(None))
                    state["completed"].append(quest_id)
                    state["order"].append("native-player-onTurn")

                driver = SimpleNamespace(
                    test=self,
                    player={"__handle__": "player"},
                    navigateTo=Mock(),
                    choose=Mock(side_effect=choose),
                    select=Mock(side_effect=lambda *args: state["order"].append("dialog-closed")),
                    count=lambda identity: state["item"],
                    condition=lambda dialog, condition: condition == "has_letter_quest",
                    call=lambda *args: True,
                    questNames=lambda completed=False: state["completed"] if completed else [quest_id],
                    tick=Mock(side_effect=tick),
                )
                with patch.object(nouraajd, "verifyJournals", side_effect=lambda d: state["order"].append("journal")):
                    route(driver)
                self.assertEqual(
                    ["actual-delivery", "dialog-closed", "native-player-onTurn", "journal"], state["order"][-4:]
                )
                driver.tick.assert_called_once_with()

    def testFreshServicesVisitBothActualStationsAndDeclareEveryAvailableRejection(self):
        driver = object()
        with (
            patch.object(nouraajd, "start") as start,
            patch.object(nouraajd, "marketAttempt") as market,
            patch.object(nouraajd, "readSignpost") as sign,
            patch.object(nouraajd, "openStation") as station,
            patch.object(nouraajd, "recipeAttempt") as recipe,
        ):
            nouraajd.authoredServices(driver)
        start.assert_called_once_with(driver)
        market.assert_called_once_with(driver, "market1", "nouraajd.market.insufficientGold", purchased=False)
        sign.assert_called_once_with(driver, "nouraajdSign")
        self.assertEqual(["alchemyTable1", "scribeDesk1"], [call.args[1] for call in station.call_args_list])
        actual = {call.args[2]: (call.args[1], call.kwargs["outcome"]) for call in recipe.call_args_list}
        expected = {
            identity: (
                "alchemyTable1" if value["station"] == "alchemyTable" else "scribeDesk1",
                "locked" if value.get("unlockFlag") else "missingIngredients",
            )
            for identity, value in nouraajd.recipeDefinitions().items()
        }
        self.assertEqual(expected, actual)
        self.assertEqual(len(expected), recipe.call_count)

    def testEarnedFundingNeverSellsStartingEquipmentQuestItemsOrRecipeReagents(self):
        items = {name: {"__handle__": name} for name in ("starter", "loot", "second", "reagent", "quest")}
        state = {"gold": 0}
        market = {"__handle__": "market"}

        def call(handle, method, *args):
            if method == "getObjectProperty":
                return market
            if method == "getItems":
                return list(items.values())
            if method == "getTypeId":
                return "ManaPotion" if handle == items["reagent"] else "Sword"
            if method == "hasTag":
                return handle == items["quest"]
            if method == "getBuyCost":
                return 500 if args[0] == items["loot"] else 300
            if method == "getName":
                return handle["__handle__"]
            raise AssertionError((handle, method, args))

        def sell(name, item):
            self.assertEqual("market1", name)
            self.assertIn(item["__handle__"], {"loot", "second"})
            state["gold"] += call(market, "getBuyCost", item)

        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            navigateTo=Mock(),
            object=Mock(),
            call=call,
            gold=lambda: state["gold"],
            sellAt=Mock(side_effect=sell),
        )
        earned = {"loot", "second", "reagent", "quest"}
        nouraajd.fundEarnedCrafting(driver, earned, 700)
        self.assertEqual(["loot", "second"], [call.args[1]["__handle__"] for call in driver.sellAt.call_args_list])
        self.assertEqual(800, state["gold"])

    def testInsufficientActualEarnedFundingFailsWithoutRepeatingSales(self):
        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            navigateTo=Mock(),
            object=Mock(),
            call=Mock(side_effect=lambda handle, method, *args: [] if method == "getItems" else None),
            gold=lambda: 0,
            sellAt=Mock(),
        )
        with self.assertRaisesRegex(AssertionError, "Actual earned loot did not fund"):
            nouraajd.fundEarnedCrafting(driver, set(), 20)
        driver.sellAt.assert_not_called()

    def testManaIngredientRequiresActualVictorVictoryAndItsOriginalFiniteMarket(self):
        state = {"gold": 200, "rescued": False, "order": []}
        mana = {"__handle__": "actual-mana"}

        def fight(name):
            self.assertEqual("cultLeaderQuest", name)
            state.update(gold=700, rescued=True)
            state["order"].append("actual-fight")

        driver = SimpleNamespace(
            test=self,
            hunt=Mock(side_effect=lambda *args: state["order"].append("real-Gooby")),
            questNames=lambda completed=False: {"mainQuest"},
            gold=lambda: state["gold"],
            fight=fight,
            string=lambda name: "good_end" if state["rescued"] else "encounter_active",
            flag=lambda name: state["rescued"],
            check=Mock(),
        )

        def purchase(d, market, item_type, earned, *, protected_types):
            self.assertTrue(state["rescued"])
            self.assertEqual(("victorMarket", "ManaPotion", {"loot", "actual-mana"}), (market, item_type, earned))
            self.assertIn("LesserManaPotion", protected_types)
            self.assertIn("Scroll", protected_types)
            state["order"].append("actual-purchase")
            return mana

        with (
            patch.object(nouraajd, "meetVictor", side_effect=lambda *args: state["order"].append("authored-dialog")),
            patch.object(nouraajd, "purchaseCallbackItem", side_effect=purchase),
            patch.object(nouraajd, "ownedIdentities", return_value={"starting", "loot", "actual-mana"}),
        ):
            nouraajd.earnVictorCraftingMana(driver, {"starting"})
        self.assertEqual(["real-Gooby", "authored-dialog", "actual-fight", "actual-purchase"], state["order"])
        self.assertEqual(2, driver.check.call_count)

    def testEarnedRecipesUnlockBeforeMissingWitnessThenUseOnlyActuallyPurchasedInputs(self):
        for has_mana in (False, True):
            with self.subTest(has_mana=has_mana):
                state = {"counts": {"Scroll": 0, "LesserLifePotion": 0, "ManaPotion": int(has_mana)}, "order": []}
                stock = [
                    {"__handle__": "paper", "type": "Scroll"},
                    {"__handle__": "small1", "type": "LesserLifePotion"},
                    {"__handle__": "small2", "type": "LesserLifePotion"},
                ]
                market = {"__handle__": "market"}

                def call(handle, method, *args):
                    if method == "getObjectProperty":
                        return market
                    if method == "getItems":
                        return stock
                    if method == "getTypeId":
                        return handle["type"]
                    if method == "getSellCost":
                        return 200 if args[0]["type"] == "Scroll" else 400
                    raise AssertionError((handle, method, args))

                def buy(name, identity, count):
                    state["counts"][identity] += count
                    state["order"].append(("purchase", identity, count))

                def attempt(d, station, recipe, branch, *, outcome):
                    state["order"].append((recipe, outcome))
                    if outcome == "success":
                        if recipe == "brew_life_potion":
                            self.assertGreaterEqual(state["counts"]["LesserLifePotion"], 2)
                        else:
                            self.assertGreaterEqual(state["counts"]["Scroll"], 1)
                            self.assertGreaterEqual(state["counts"]["ManaPotion"], 1)

                driver = SimpleNamespace(
                    test=self,
                    player={"__handle__": "player"},
                    navigateTo=Mock(),
                    object=Mock(),
                    call=call,
                    count=lambda identity: state["counts"].get(identity, 0),
                    buyAt=Mock(side_effect=buy),
                )
                with (
                    patch.object(nouraajd, "start", side_effect=lambda d: state["order"].append("start")),
                    patch.object(nouraajd, "letter", side_effect=lambda d: state["order"].append("earned-unlock")),
                    patch.object(nouraajd, "prepareRolf", side_effect=lambda d: state["order"].append("real-Rolf")),
                    patch.object(
                        nouraajd,
                        "earnVictorCraftingMana",
                        side_effect=lambda d, initial: state["order"].append("actual-Victor-market"),
                    ),
                    patch.object(nouraajd, "ownedIdentities", side_effect=({"starting"}, {"starting", "loot"})),
                    patch.object(nouraajd, "recipeAttempt", side_effect=attempt),
                    patch.object(nouraajd, "fundEarnedCrafting") as funding,
                    patch.object(
                        nouraajd, "marketAttempt", side_effect=lambda *args, **kwargs: buy("market1", "Scroll", 1)
                    ),
                ):
                    if has_mana:
                        nouraajd.earnedCrafting(driver)
                    else:
                        with self.assertRaisesRegex(AssertionError, "actually earned ManaPotion"):
                            nouraajd.earnedCrafting(driver)
                funding.assert_called_once_with(driver, {"loot"}, 1055)
                self.assertEqual(
                    [
                        "start",
                        "earned-unlock",
                        ("craft_town_portal_scroll", "missingIngredients"),
                        ("scribe_emergency_portal_scroll", "missingIngredients"),
                        "real-Rolf",
                    ],
                    state["order"][:5],
                )
                self.assertLess(
                    state["order"].index("actual-Victor-market"), state["order"].index(("brew_life_potion", "success"))
                )
                self.assertIn(("brew_life_potion", "success"), state["order"])
                self.assertEqual(has_mana, ("craft_town_portal_scroll", "success") in state["order"])

    def testVictorCapturedInquisitorEscapeTakesTheSoleDoorInsteadOfTheEasternPocket(self):
        # PR 1597 / 886ac290, job 120725962470, seed 2808043864: native pre-turn-1002 positions.
        opponents = [
            (34, 86, 0),
            (43, 102, 0),
            (43, 103, 0),
            (46, 112, 0),
            (54, 77, 0),
            (58, 92, 0),
            (59, 79, 0),
            (59, 114, 0),
            (60, 87, 0),
            (67, 111, 0),
            (77, 108, 0),
            (82, 93, 0),
        ]
        driver, state = self.courtyardFleeFixture()
        origin = state["position"] = (44, 105, 0)

        class ObservedFirstStep(Exception):
            pass

        driver.step = Mock(side_effect=ObservedFirstStep)
        with patch.object(nouraajd, "fleeHostileCoords", return_value=opponents):
            with self.assertRaises(ObservedFirstStep):
                nouraajd.fleeCourtyardUntil(driver, 1)
        driver.step.assert_called_once_with((44, 106, 0))
        self.assertEqual(10, state["turn"], "This projects the captured native decision; it does not run movement")
        self.assertLessEqual(len(state["probes"][10]), 64)
        self.assertEqual(len(state["probes"][10]), len(set(state["probes"][10])))
        door, enclosed = nouraajd.courtyardExitDistances()
        self.assertEqual((44, 106, 0), door)
        path = [(44, 106, 0), (44, 107, 0), (43, 107, 0), (42, 107, 0), (41, 107, 0), (40, 107, 0)]
        for hop, (previous, target) in enumerate(zip([origin] + path, path), 1):
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(previous, target)))
            self.assertIn(target, state["walkable"])
            clearance = min(nouraajd.courtyardPursuitLowerBound(target, actor, door, enclosed) for actor in opponents)
            self.assertGreater(clearance - hop, 1, "The existing pursuit margin must hold at all six authored hops")


if __name__ == "__main__":
    unittest.main()
