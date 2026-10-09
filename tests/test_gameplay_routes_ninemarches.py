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
from tests.gameplay_branch_driver import GameplayBranchDriver
from tests.gameplay_branch_types import RouteCase
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

        case = RouteCase("nine_recovery_unit", "unit", ("ninemarches",), (), lambda driver: None)
        self.driver = GameplayBranchDriver(self, Mock(), None, case, "Warrior", Path("."))
        self.driver.harness._mcp_engine_call.return_value = True
        self.driver.__dict__.update(
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

    def testUnresolvedOutcomePermanentlyBlocksRecoveryInsteadOfRetryingALaterVictory(self):
        source = (Path(__file__).resolve().parents[1] / "src/handler/CFightHandler.h").read_text(encoding="utf-8")
        outcomes = {name: int(value) for name, value in re.findall(r"^\s*(\w+)\s*=\s*(\d+),", source, re.MULTILINE)}
        self.assertEqual(
            {"Invalid": 0, "AttackerVictory": 1, "AttackerDefeat": 2, "Stalled": 3, "Cancelled": 4}, outcomes
        )
        self.append(1, outcome=outcomes["Stalled"])
        with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
            marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_not_called()
        self.append(2, outcome=outcomes["AttackerDefeat"])
        with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
            marches.afterCombat(self.driver)
        self.driver.recoverOnAuthoredRoad.assert_not_called()

    def testVictoryWithFullResourcesNeedsNoRecoveryOrScroll(self):
        self.state.update(hp=70, mana=35)
        self.append(1)
        marches.afterCombat(self.driver)
        self.driver.roadRecoveryTarget.assert_not_called()
        self.driver.recoverOnAuthoredRoad.assert_not_called()
        self.assertEqual([], self.used)

    def testVictoryAboveDerivedResourceCapsNeedsNoRecoveryOrScroll(self):
        self.state.update(hp=81, mana=42)
        self.append(1)
        marches.afterCombat(self.driver)
        self.assertEqual(0, self.driver.roadRecoveryTarget.call_count)
        self.assertEqual(0, self.driver.recoverOnAuthoredRoad.call_count)
        self.assertEqual((81, 42), (self.state["hp"], self.state["mana"]))
        self.assertEqual([], self.used)

    def testRecoveryRestoresOnlyTheDeficitWithoutRejectingAnUntouchedOverflow(self):
        for overflow, deficit, restored in (("mana", "hp", 70), ("hp", "mana", 35)):
            with self.subTest(overflow=overflow):
                self.state.update(hp=81 if overflow == "hp" else 35, mana=42 if overflow == "mana" else 2)
                before = self.state[overflow]
                self.append(1 if overflow == "mana" else 2)

                def recover(*, road_cells):
                    self.assertIs(marches.recoveryRoadCells(), road_cells)
                    self.assertFalse(self.driver.recoveryEnabled)
                    self.state[deficit] = restored
                    return 12

                self.driver.recoverOnAuthoredRoad.side_effect = recover
                marches.afterCombat(self.driver)
                self.assertEqual(before, self.state[overflow])
                self.assertEqual(restored, self.state[deficit])
        self.assertEqual(2, self.driver.recoverOnAuthoredRoad.call_count)
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

    def testAConsumedRetreatScrollRequiresRealControllerWalkingToTheAuthoredEntry(self):
        self.items[:] = [self.other_item]
        self.driver._marches_retreat_scroll_name = None
        self.driver.roadRecoveryTarget.return_value = None
        origin = self.state["position"]

        def navigate(coords):
            self.assertEqual(self.scroll_destination, coords)
            self.assertEqual(origin, self.state["position"])
            self.assertEqual([self.other_item], self.items)
            self.state["position"] = coords

        self.driver.navigateCoords = Mock(side_effect=navigate)
        self.append(1)
        marches.afterCombat(self.driver)
        self.driver.navigateCoords.assert_called_once_with(self.scroll_destination)
        self.assertEqual([], self.used)
        self.assertEqual([self.other_item], self.items)
        self.assertIsNone(self.driver._marches_retreat_scroll_name)
        self.driver.recoverOnAuthoredRoad.assert_called_once_with(road_cells=marches.recoveryRoadCells())
        self.assertEqual(-7, self.state["reputation"])
        self.assertFalse(self.state["shrine_used"])

    def testWalkingRetreatCannotRetryDefeatOrAcceptAWrongEntryOrChangedPlayer(self):
        for failure in ("native defeat", "wrong-entry", "changed-player"):
            with self.subTest(failure=failure):
                self.driver._marches_retreat_scroll_name = None
                self.items[:] = [self.other_item]
                self.driver.recoverOnAuthoredRoad.reset_mock()

                def navigate(coords):
                    if failure == "native defeat":
                        raise AssertionError("actual native defeat")
                    if failure == "changed-player":
                        self.driver.player = {"__handle__": "replacement"}
                    self.state["position"] = (1, 1, 0) if failure == "wrong-entry" else coords

                self.driver.navigateCoords = Mock(side_effect=navigate)
                with self.assertRaises(AssertionError):
                    marches.retreatToRecoveryRoad(self.driver)
                self.driver.navigateCoords.assert_called_once_with(self.scroll_destination)
                self.driver.recoverOnAuthoredRoad.assert_not_called()
                self.assertEqual([], self.used)
                self.driver.player = self.player

    def testRetreatResolvesTheActuallyOwnedIdentityAfterReload(self):
        self.scroll["__handle__"] = "reloaded-earned-scroll"
        marches.retreatWithOwnedScroll(self.driver)
        self.assertEqual("reloaded-earned-scroll", self.used[0]["__handle__"])
        self.assertEqual([self.other_item], self.items)

    def testActualRecoveryScrollUseCreditsTheDeclaredRetreatWithExactIdentityAndMovement(self):
        branch = "ninemarches.scroll.retreat"
        self.driver.case = RouteCase("nine_scroll_unit", "unit", ("ninemarches",), (branch,), lambda driver: None)
        self.driver.snapshot = lambda: {"position": self.state["position"]}
        origin = self.state["position"]
        marches.retreatWithOwnedScroll(self.driver)
        self.assertEqual([self.scroll], self.used)
        self.assertEqual([self.other_item], self.items)
        self.assertIn(branch, self.driver.branches)
        self.assertEqual(
            {"item": self.scroll["__handle__"], "origin": origin, "destination": (500, 662, 0)},
            self.driver.branches[branch]["evidence"],
        )
        self.assertIsNone(self.driver._marches_retreat_scroll_name)

    def testScrollAtTheEntryCannotClaimRetreatOrConsumeTheOriginal(self):
        self.state["position"] = self.scroll_destination
        with self.assertRaisesRegex(AssertionError, "away from the destination"):
            marches.retreatWithOwnedScroll(self.driver)
        self.assertEqual([], self.used)
        self.assertEqual([self.scroll, self.other_item], self.items)
        self.assertEqual("townPortalScroll", self.driver._marches_retreat_scroll_name)

    def testMissingOrUnconsumedScrollCannotBecomeAnEscapeFixture(self):
        branch = "ninemarches.scroll.retreat"
        self.driver.case = RouteCase("nine_scroll_unit", "unit", ("ninemarches",), (branch,), lambda driver: None)
        self.driver.snapshot = lambda: {"position": self.state["position"]}
        for failure in ("missing", "unconsumed", "wrong-destination"):
            with self.subTest(failure=failure):
                self.items[:] = [self.other_item] if failure == "missing" else [self.scroll, self.other_item]
                self.driver._marches_retreat_scroll_name = "townPortalScroll"
                self.state["position"] = (500, 618, 0)
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
                self.assertNotIn(branch, self.driver.branches, "A failed item-use oracle must never credit retreat")
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

    def serviceRouteFixture(self, *, combat_retreat=False, credited=True):
        state = {"gold": 0, "flags": {}, "position": "entry", "reputation": 0}
        items = [self.scroll]
        gift = {"__handle__": "earned-aegis"}
        parchment = {"__handle__": "shop-parchment"}
        mana = {"__handle__": "shop-mana"}
        crafted = {"__handle__": "crafted-scroll"}
        types = {
            self.scroll["__handle__"]: "TownPortalScroll",
            gift["__handle__"]: "aegisOfHalda",
            parchment["__handle__"]: "Scroll",
            mana["__handle__"]: "ManaPotion",
            crafted["__handle__"]: "TownPortalScroll",
        }
        actions = []
        player = SimpleNamespace(
            isPlayer=lambda: True,
            addGold=lambda gold: state.update(gold=state["gold"] + gold),
            healProc=Mock(),
            addItem=lambda item_id: items.append(gift),
            checkQuests=Mock(),
        )
        game_instance = SimpleNamespace(getGuiHandler=lambda: SimpleNamespace(notify=Mock()))
        game_map = SimpleNamespace(
            getPlayer=lambda: player,
            getBoolProperty=lambda name: state["flags"].get(name, False),
            setBoolProperty=lambda name, value: state["flags"].update({name: value}),
            getGame=lambda: game_instance,
        )
        game_instance.getMap = lambda: game_map
        learning_stone = authoredFunction("res/maps/ninemarches/script.py", "onEnter", class_id="LearningStone")
        recruit_companion = authoredFunction(
            "res/maps/ninemarches/script.py",
            "recruit",
            class_id="CompanionDialog",
            adjust_reputation=lambda game_map, value: state.update(reputation=state["reputation"] + value),
            rewardSnapshot=lambda player: {},
            showRewardReceipt=Mock(),
        )

        def call(handle, method, *args):
            if handle == self.player and method == "getItems":
                return list(items)
            if method == "getTypeId":
                return types[handle["__handle__"]]
            if method == "getName":
                return "townPortalScroll" if handle == self.scroll else handle["__handle__"]
            raise AssertionError((handle, method, args))

        def walk(driver, name, adjacent=False):
            state["position"] = name
            if name == "learningStone":
                learning_stone(SimpleNamespace(getMap=lambda: game_map), SimpleNamespace(getCause=lambda: player))

        def station(driver, name, branch=None, *, navigate):
            navigate(name)
            detail = (
                "Missing: parchment"
                if state["flags"].get("CAN_CRAFT_SCROLLS")
                else "Locked: Study Gravewatch's learning stone"
            )
            return tuple(
                {"id": recipe_id, "enabled": False, "detail": detail}
                for recipe_id in (
                    "craft_town_portal_scroll",
                    "scribe_emergency_portal_scroll",
                )
            )

        def recipe(driver, station_name, recipe_id, branch, *, outcome, navigate):
            navigate(station_name)
            actions.append(("recipe", recipe_id, outcome))
            if outcome == "locked":
                self.assertFalse(state["flags"].get("CAN_CRAFT_SCROLLS", False))
            elif outcome == "missingIngredients":
                self.assertTrue(state["flags"].get("CAN_CRAFT_SCROLLS"))
                self.assertNotIn(parchment, items)
            else:
                self.assertEqual("success", outcome)
                self.assertTrue(state["flags"].get("CAN_CRAFT_SCROLLS"))
                self.assertIn(parchment, items)
                self.assertIn(mana, items)
                self.assertGreaterEqual(state["gold"], 35)
                items.remove(parchment)
                items.remove(mana)
                items.append(crafted)
                state["gold"] -= 35

        def market(driver, name, branch, *, purchased, navigate):
            navigate(name)
            if purchased:
                self.assertGreaterEqual(state["gold"], 200)
                state["gold"] -= 200
                items.append(parchment)
                return parchment
            self.assertLess(state["gold"], 200)

        def retreat(driver):
            self.assertIn(self.scroll, items)
            self.assertEqual("townPortalScroll", driver._marches_retreat_scroll_name)
            actions.append(("retreat",))
            items.remove(self.scroll)
            state["position"] = "entry"
            driver._marches_retreat_scroll_name = None
            if credited:
                driver.branches["ninemarches.scroll.retreat"] = {"evidence": {"item": self.scroll["__handle__"]}}

        def recruit(driver, companion):
            self.assertEqual("halda", companion)
            self.assertIn(self.scroll, items, "Preserve the actual retreat scroll through the first Halda approach")
            self.assertEqual("townPortalScroll", driver._marches_retreat_scroll_name)
            actions.append(("approach-halda",))
            if combat_retreat:
                retreat(driver)
            before_gold = state["gold"]
            recruit_companion(
                SimpleNamespace(
                    getGame=lambda: game_instance,
                    can_recruit=lambda: True,
                    JOINED_FLAG="halda_joined",
                    BOON="aegisOfHalda",
                )
            )
            self.assertEqual(before_gold, state["gold"], "The actual companion reward is an item, not gold")
            actions.append(("recruited-halda",))
            return "knight", "knightDialog", "aegisOfHalda"

        def sell(name, item):
            self.assertEqual(name, state["position"])
            self.assertIs(gift, item)
            self.assertIn(item, items)
            actions.append(("sell-earned-gift",))
            items.remove(item)
            state["gold"] += 5000

        def buy(name, item_type):
            self.assertEqual(name, state["position"])
            self.assertEqual("ManaPotion", item_type)
            self.assertGreaterEqual(
                state["gold"], 1600, "Buying cheap parchment alone does not fund the mana ingredient"
            )
            actions.append(("buy-finite-mana",))
            items.append(mana)
            state["gold"] -= 1600

        self.driver.call = call
        self.driver.flag = lambda name: state["flags"].get(name, False)
        self.driver.sellAt = sell
        self.driver.buyAt = buy
        with patch.object(marches, "start", side_effect=lambda d: actions.append(("start",))), patch.object(
            marches, "verifyWaypointPublication", side_effect=lambda d: actions.append(("published",))
        ), patch.object(marches, "walk", side_effect=walk), patch.object(marches, "readSignpost"), patch.object(
            marches, "openStation", side_effect=station
        ), patch.object(
            marches, "recipeAttempt", side_effect=recipe
        ), patch.object(
            marches, "marketAttempt", side_effect=market
        ), patch.object(
            marches, "retreatWithOwnedScroll", side_effect=retreat
        ), patch.object(
            marches, "useOwnedScroll", side_effect=lambda d, item, branch: retreat(d), create=True
        ), patch.object(
            marches, "recruit", side_effect=recruit
        ):
            marches.serviceRoute(self.driver)
        self.assertEqual([crafted], items)
        self.assertEqual(3285, state["gold"])
        self.assertEqual(2, state["reputation"])
        self.assertEqual([("start",), ("published",)], actions[:2])
        self.assertLess(actions.index(("sell-earned-gift",)), actions.index(("buy-finite-mana",)))
        self.assertEqual(("recipe", "craft_town_portal_scroll", "success"), actions[-1])
        self.assertEqual(1, actions.count(("retreat",)))
        self.assertLess(actions.index(("approach-halda",)), actions.index(("retreat",)))
        if combat_retreat:
            self.assertLess(actions.index(("retreat",)), actions.index(("recruited-halda",)))
        else:
            self.assertLess(actions.index(("recruited-halda",)), actions.index(("retreat",)))
        self.assertIn("ninemarches.scroll.retreat", self.driver.branches)

    def testServiceRouteUnlocksTheActualScribeAndFundsItsRecipeWithAnEarnedGift(self):
        self.serviceRouteFixture()

    def testServiceRouteCreditsTheOriginalScrollUsedDuringTheFirstHaldaApproachOnlyOnce(self):
        self.serviceRouteFixture(combat_retreat=True)

    def testServiceRouteRejectsAConsumedOriginalScrollWithoutAnActualRetreatWitness(self):
        with self.assertRaisesRegex(AssertionError, "actual original scroll retreat witness"):
            self.serviceRouteFixture(combat_retreat=True, credited=False)


if __name__ == "__main__":
    unittest.main()
