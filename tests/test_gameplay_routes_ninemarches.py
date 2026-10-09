# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Recovery sequencing regressions; fake drivers confer no native gameplay credit."""

import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import gameplay_routes_ninemarches as marches
from tests.test_gameplay_route_dialogs import authoredFunction


class NineMarchesRecoveryTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.trace = Path(temporary.name) / "native.trace.jsonl"
        self.state = {"hp": 35, "mana": 2, "position": (500, 618, 0), "reputation": -7, "shrine_used": False}
        self.player = {"__handle__": "player"}
        self.game_map = {"__handle__": "map"}
        self.scroll = {"__handle__": "earned-scroll"}
        self.other_item = {"__handle__": "earned-sword"}
        self.items = [self.scroll, self.other_item]
        self.used = []
        self.scroll_destination = (500, 662, 0)
        on_use = authoredFunction("res/plugins/object.py", "onUse", class_id="TownPortalScroll")
        authored_map = SimpleNamespace(getEntryX=lambda: 500, getEntryY=lambda: 662, getEntryZ=lambda: 0)

        def moveTo(*coords):
            self.assertEqual((500, 662, 0), coords, "Execute the scroll's actual authored entry destination")
            self.state.update(position=self.scroll_destination)

        creature = SimpleNamespace(getMap=lambda: authored_map, moveTo=moveTo)

        def call(handle, method, *args):
            if handle == self.player:
                if method in {"getHp", "getMana"}:
                    return self.state["hp" if method == "getHp" else "mana"]
                if method in {"getHpMax", "getManaMax"}:
                    return 70 if method == "getHpMax" else 35
                if method == "getName":
                    return "player"
                if method == "getItems":
                    return list(self.items)
                if method == "useItem":
                    self.assertIn(args[0], self.items)
                    self.used.append(args[0])
                    on_use(None, SimpleNamespace(getCause=lambda: creature))
                    self.items.remove(args[0])
                    return
            if handle == self.game_map and method in {"getEntryX", "getEntryY", "getEntryZ"}:
                return getattr(authored_map, method)()
            if handle in (self.scroll, self.other_item):
                if method == "getName":
                    return "townPortalScroll" if handle == self.scroll else "lootedSword"
                if method == "getTypeId":
                    return "TownPortalScroll" if handle == self.scroll else "Sword"
            raise AssertionError((handle, method, args))

        def recover(*, road_cells):
            self.assertIs(marches.recoveryRoadCells(), road_cells)
            self.assertFalse(self.driver.recoveryEnabled, "Road steps must preserve owned potion stock")
            self.state.update(hp=70, mana=35)
            return 35

        self.driver = SimpleNamespace(
            test=self,
            trace_path=self.trace,
            player=self.player,
            game_map=self.game_map,
            map_name="ninemarches",
            call=call,
            coords=lambda: self.state["position"],
            pump=Mock(),
            record=Mock(),
            recoveryEnabled=True,
            roadRecoveryTarget=Mock(return_value=(500, 619, 0)),
            recoverOnAuthoredRoad=Mock(side_effect=recover),
            _marches_retreat_scroll_name="townPortalScroll",
        )

    def append(
        self, seq, *, event="combat_finished", map_name="ninemarches", player=True, outcome=1, participants=None
    ):
        hero = {"name": "player", "isPlayer": True}
        npc = {"name": "fieldRaider", "isPlayer": False}
        attacker, opponents = (
            participants if participants is not None else ((npc, [hero]) if outcome == 2 else (hero, [npc]))
        )
        record = {
            "seq": seq,
            "event": event,
            "map": map_name,
            "survivor": {"name": "player" if player else "fieldRaider", "isPlayer": player},
            "attacker": attacker,
            "opponents": opponents,
        }
        if outcome is not None:
            record["outcome"] = outcome
        with self.trace.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record) + "\n")

    def testRecoveryRequiresANewNativePlayerVictoryAndRunsOnce(self):
        marches.afterCombat(self.driver)
        self.append(1, event="level_up")
        self.append(2, map_name="nouraajd")
        self.append(3, player=False)
        marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_not_called()
        self.append(4)
        marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())
        self.state.update(hp=20, mana=0)
        marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())
        self.assertTrue(self.driver.recoveryEnabled)
        self.assertEqual([], self.used)

    def testIncrementalCombatWitnessSurvivesNativeTraceRotation(self):
        self.append(1, event="movement")
        self.assertFalse(marches.newCombatWitness(self.driver))
        self.append(2)
        self.assertTrue(marches.newCombatWitness(self.driver))
        self.trace.replace(Path(str(self.trace) + ".1"))
        self.append(3)
        self.assertTrue(marches.newCombatWitness(self.driver))
        self.assertFalse(marches.newCombatWitness(self.driver))
        self.assertEqual(3, self.driver._marches_combat_seq)

    def testStalledCancelledInvalidAndMissingOutcomesAreNotVictoryWitnesses(self):
        source = (Path(__file__).resolve().parents[1] / "src/handler/CFightHandler.h").read_text(encoding="utf-8")
        outcomes = {name: int(value) for name, value in re.findall(r"^\s*(\w+)\s*=\s*(\d+),", source, re.MULTILINE)}
        self.assertEqual(
            {"Invalid": 0, "AttackerVictory": 1, "AttackerDefeat": 2, "Stalled": 3, "Cancelled": 4}, outcomes
        )
        for seq, outcome in enumerate((outcomes["Invalid"], outcomes["Stalled"], outcomes["Cancelled"], None), 1):
            self.append(seq, outcome=outcome)
        marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_not_called()
        self.append(5, outcome=outcomes["AttackerDefeat"])
        marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())

    def testVictoryWithFullResourcesNeedsNoRecoveryOrScroll(self):
        self.state.update(hp=70, mana=35)
        self.append(1)
        marches.afterCombat(self.driver)
        self.driver.roadRecoveryTarget.assert_not_called()
        self.driver.recoverOnAuthoredRoad.assert_not_called()
        self.assertEqual([], self.used)

    def testThirdPartyPlayerPoisonCasterDoesNotWitnessParticipationInNpcCombat(self):
        npc = {"name": "fieldRaider", "isPlayer": False}
        self.append(1, outcome=2, participants=(npc, [{"name": "fenGhoul", "isPlayer": False}]))
        self.append(2, outcome=2, participants=(npc, [{"name": "other-player", "isPlayer": True}]))
        self.append(3, outcome=2, participants=(npc, [{"name": "player", "isPlayer": False}]))
        marches.afterCombat(self.driver)
        self.assertEqual(0, self.driver.roadRecoveryTarget.call_count)
        self.assertEqual(0, self.driver.recoverOnAuthoredRoad.call_count)
        self.assertEqual([], self.used)
        self.append(4, outcome=2)
        marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())

    def testNavigationRecoversBeforeContinuingAfterAnObservedCombat(self):
        order = []

        def navigate(name, *, adjacent, after_tick):
            order.append((name, adjacent))
            self.append(1)
            after_tick()
            self.assertEqual((70, 35), (self.state["hp"], self.state["mana"]))
            order.append("continue-target")

        self.driver.navigateTo = navigate
        marches.walk(self.driver, "digSite", adjacent=True)
        self.assertEqual([("digSite", True), "continue-target"], order)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())

    def testOffRoadRecoveryUsesOnlyTheOwnedScrollAndItsAuthoredDestination(self):
        self.driver.roadRecoveryTarget.return_value = None
        self.append(1)
        marches.afterCombat(self.driver)
        self.assertEqual([self.scroll], self.used)
        self.assertEqual([self.other_item], self.items)
        self.assertEqual((500, 662, 0), self.state["position"])
        self.assertIsNone(self.driver._marches_retreat_scroll_name)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())
        self.assertEqual(-7, self.state["reputation"])
        self.assertFalse(self.state["shrine_used"])

    def testRetreatResolvesTheActuallyOwnedIdentityAfterReload(self):
        self.scroll["__handle__"] = "reloaded-earned-scroll"
        marches.retreatWithOwnedScroll(self.driver)
        self.assertEqual("reloaded-earned-scroll", self.used[0]["__handle__"])
        self.assertEqual([self.other_item], self.items)

    def testMissingOrUnconsumedScrollCannotBecomeAnEscapeFixture(self):
        for failure in ("missing", "unconsumed", "wrong-destination"):
            with self.subTest(failure=failure):
                self.items[:] = [self.other_item] if failure == "missing" else [self.scroll, self.other_item]
                self.driver._marches_retreat_scroll_name = "townPortalScroll"
                self.scroll_destination = (1, 1, 0) if failure == "wrong-destination" else (500, 662, 0)
                original = self.driver.call

                def call(handle, method, *args):
                    result = original(handle, method, *args)
                    if method == "useItem" and failure == "unconsumed":
                        self.items.append(args[0])
                    return result

                self.driver.call = call
                with self.assertRaises(AssertionError):
                    marches.retreatWithOwnedScroll(self.driver)
                self.driver.call = original
        self.driver.recoverOnAuthoredRoad.assert_not_called()

    def testRecoveryFailurePropagatesWithoutAnEscapeRetry(self):
        self.append(1)
        self.driver.recoverOnAuthoredRoad.side_effect = AssertionError("Natural road recovery budget exhausted")
        with self.assertRaisesRegex(AssertionError, "budget exhausted"):
            marches.afterCombat(self.driver)
        self.assertTrue(self.driver.recoveryEnabled)
        self.assertEqual([], self.used)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())

    def testPursuingTargetDefeatedDuringRoadRecoveryRemainsARealCombatVictory(self):
        actor = {"__handle__": "pursuing-raider"}
        state = {"alive": True, "exp": 250}
        original_call = self.driver.call

        def call(handle, method, *args):
            if handle == actor and method == "isAlive":
                return state["alive"]
            if handle == self.player and method == "getNumericProperty" and args == ("exp",):
                return state["exp"]
            return original_call(handle, method, *args)

        def recover(*, road_cells):
            state.update(alive=False, exp=500)
            self.state.update(hp=70, mana=35)
            return 20

        self.append(1)
        self.driver.call = call
        self.driver.object = lambda name, required=True: actor if state["alive"] else None
        self.driver.recoverOnAuthoredRoad.side_effect = recover
        self.driver.navigateTo = Mock(side_effect=AssertionError("Defeated actor must not be navigated to again"))
        self.driver.combats = 0
        marches.fight(self.driver, "pursuingRaider")
        self.assertEqual(1, self.driver.combats)
        self.driver.navigateTo.assert_not_called()

    def testRecoveryRoadsExcludeEveryAuthoredObjectIncludingBranchTriggers(self):
        source = Path(__file__).resolve().parents[1] / "res/maps/ninemarches/map.json"
        document = json.loads(source.read_text(encoding="utf-8"))
        coordinates = {
            actor["name"]: (
                int(actor["x"] // document["tilewidth"]),
                int(actor["y"] // document["tileheight"]),
                int(layer["properties"]["level"]),
            )
            for layer in document["layers"]
            if layer["type"] == "objectgroup"
            for actor in layer["objects"]
        }
        roads = marches.recoveryRoadCells()
        all_roads = marches.authoredRoadCells("ninemarches")
        self.assertTrue(roads)
        self.assertLess(roads, all_roads)
        self.assertTrue(roads.isdisjoint(coordinates.values()))
        for name in (
            "boneKeyCache",
            "obeliskFields",
            "obeliskBarrows",
            "ironGateThreshold",
            "brassGateThreshold",
            "guardBarrows3",
            "guardAsh3",
            "guardCoast1",
            "digSite",
            "townPortalScroll",
        ):
            with self.subTest(name=name):
                self.assertIn(coordinates[name], all_roads)
                self.assertNotIn(coordinates[name], roads)
        self.append(1)
        marches.afterCombat(self.driver)
        self.driver.roadRecoveryTarget.assert_called_once_with(road_cells=roads)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=roads)

    def testStartCollectsTheAuthoredScrollWithoutClaimingSitesOrChangingReputation(self):
        self.items[:] = []
        state = {"scrollPresent": True}
        self.driver.startMap = Mock()
        self.driver.questNames = lambda: ["ninemarchesQuest"]
        self.driver.object = lambda name, required=False: (
            self.scroll if name == "townPortalScroll" and state["scrollPresent"] else None
        )

        def pickup(driver, name):
            self.assertEqual("townPortalScroll", name)
            state["scrollPresent"] = False
            self.items.append(self.scroll)

        with patch.object(marches, "walk", side_effect=pickup):
            marches.start(self.driver)
        self.driver.startMap.assert_called_once_with("ninemarches")
        self.assertEqual("townPortalScroll", self.driver._marches_retreat_scroll_name)
        self.assertEqual(-7, self.state["reputation"])
        self.assertFalse(self.state["shrine_used"])

    def testPortalArrivalIsVerifiedBeforeRecoveryAndReverseEntryStillRevisits(self):
        names = ("monolithHub", "monolithCoast", "monolithAsh", "monolithCold")
        positions = {name: (10 * index, 0, 0) for index, name in enumerate(names, 1)}
        exits = dict(zip(names, (names[1], names[0], names[3], names[2])))
        state = {"position": (0, 0, 0), "pendingCombat": False}
        actions = []
        self.driver.object = lambda name: name
        self.driver.coords = lambda handle=None: positions[handle] if handle else state["position"]

        def enter(name):
            state["position"] = positions[exits[name]]
            state["pendingCombat"] = name == "monolithCold"

        def navigate(name, *, after_tick):
            self.assertTrue(callable(after_tick), "Long portal approaches retain the real combat callback")
            actions.append(("navigate", name))
            enter(name)

        def revisit(name):
            self.assertEqual(positions[name], state["position"])
            actions.append(("revisit", name))
            enter(name)

        def check(branch_id, condition, **evidence):
            self.assertTrue(condition)
            self.assertEqual(evidence["destination"], state["position"])
            actions.append(("arrival", branch_id))

        def recover(driver):
            if state["pendingCombat"]:
                actions.append(("recovery", state["position"]))
                state.update(position=(500, 662, 0), pendingCombat=False)

        self.driver.navigateTo = navigate
        self.driver.revisit = revisit
        self.driver.check = check
        with patch.object(marches, "start"), patch.object(marches, "afterCombat", side_effect=recover):
            marches.portals(self.driver)
        self.assertEqual(
            [("revisit", "monolithCoast"), ("revisit", "monolithCold")],
            [entry for entry in actions if entry[0] == "revisit"],
        )
        self.assertEqual(("arrival", "ninemarches.portal.monolithCold"), actions[-2])
        self.assertEqual(("recovery", positions["monolithAsh"]), actions[-1])


if __name__ == "__main__":
    unittest.main()
