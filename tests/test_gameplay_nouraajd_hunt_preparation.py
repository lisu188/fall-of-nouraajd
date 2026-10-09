# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute bounded earned hunt preparation without a native game or forced route progress."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import gameplay_routes_nouraajd as routes


class GameplayNouraajdHuntPreparationTest(unittest.TestCase):
    def fixture(
        self,
        *,
        enemies=10,
        experience_per_enemy=125,
        class_id="Sorcerer",
        corrupt=None,
        stalled=False,
        cave_present=True,
    ):
        if cave_present:
            self.assertLessEqual(enemies, 10, "An unentered authored catacomb has only ten passive opponents")
        handles = {
            name: {"__handle__": name} for name in ("player", "world", "controller", "catacombs", "letter", "relic")
        }
        actors = {f"pritz{index:02}": {"__handle__": f"pritz{index:02}"} for index in range(enemies)}
        state = {
            "coords": (57, 115, 0),
            "exp": 4250,
            "living": set(actors),
            "order": [],
            "steps": [],
            "letter": handles["letter"],
            "controller": handles["controller"],
            "chain": "letter_pending",
            "victor": "bad_end",
            "scrolls": 1,
            "recovered": True,
            "hunt": {
                "stage": "dormant",
                "slots": {slot: {"status": "pending"} for slot in ("scout", "alpha", "brood")},
            },
        }
        walkable = {(x, y, 0) for x in range(57, 60) for y in range(114, 116)}
        cave_coords = (57, 114, 0)

        def coords(actor=None):
            return (59, 114, 0) if actor and actor["__handle__"] in actors else state["coords"]

        def objectByName(name, required=True):
            if name == "catacombs":
                return handles[name] if cave_present else None
            if name == "cave2":
                return None if state["hunt"]["stage"] == "cleared" else {"__handle__": "cave2"}
            return actors[name] if name in state["living"] else None

        def call(handle, method, *args):
            identity = handle["__handle__"]
            if identity == "player":
                if method == "getLevel":
                    return 4 if state["exp"] >= 6000 else 3
                if method == "getNumericProperty" and args == ("exp",):
                    return state["exp"]
                if method == "getFightController":
                    return state["controller"]
                if method == "getItems":
                    return [state["letter"]] + ([] if cave_present else [handles["relic"]])
                if method == "getBoolProperty":
                    return False
            if identity == "world":
                if method == "getObjects":
                    return [actors[name] for name in sorted(state["living"])]
                if method == "getTile":
                    return {"__handle__": "tile", "coords": args}
            if identity == "tile" and method == "getBoolProperty" and args == ("canStep",):
                return True
            if method == "getTypeId":
                return "Pritz" if identity in actors else "holyRelic" if identity == "relic" else "letterFromRolf"
            if identity in actors:
                if method == "isAlive":
                    return identity in state["living"]
                if method == "getStringProperty" and args == ("affiliation",):
                    return "gooby"
                if method == "getName":
                    return identity
            self.fail((identity, method, args))

        def step(destination):
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(state["coords"], destination)))
            self.assertNotEqual(cave_coords, destination, "Preparation must not enter an unvisited catacomb")
            state["steps"].append(destination)
            if stalled:
                return
            if destination == (59, 114, 0) and state["living"]:
                name = min(state["living"])
                state["living"].remove(name)
                state["exp"] += experience_per_enemy
                state["order"].append("native-victory:" + name)
            else:
                state["coords"] = destination

        def hunt(method, *args):
            state["order"].append(method)
            if method == "finishOriginalMainQuest":
                state["exp"] += 250
                if corrupt == "quest":
                    state["chain"] = "relic_obtained"
                elif corrupt == "identity":
                    state["letter"] = {"__handle__": "replacement-letter"}
                elif corrupt == "controller":
                    state["controller"] = {"__handle__": "different-controller"}
            elif method == "recoverOnRoadPair":
                self.assertEqual((57, 115, 0), state["coords"])
            elif method == "enterHunt":
                self.assertGreaterEqual(state["exp"], 6000, "Scout must follow actual earned level-four preparation")
                state["hunt"]["stage"] = "brood"
                state["hunt"]["slots"]["scout"]["status"] = "dead"
                state["recovered"] = False
            elif method == "retreatWithOwnedAuthoredScroll":
                self.assertEqual(1, state["scrolls"])
                state["scrolls"] -= 1
                state["recovered"] = True
            elif method in ("recoverOnAuthoredRoad", "recoverBeforeRemainingBrood"):
                state["recovered"] = True
            elif method == "defeat":
                self.assertTrue(state["recovered"], "Do not begin another encounter without actual recovery")
                state["recovered"] = False
                state["hunt"]["slots"][args[0]]["status"] = "dead"
                if args[0] == "brood":
                    state["hunt"]["stage"] = "cleared"

        driver = SimpleNamespace(
            test=self,
            player=handles["player"],
            game_map=handles["world"],
            map_name="nouraajd",
            class_id=class_id,
            call=call,
            coords=coords,
            object=objectByName,
            step=step,
            canStep=lambda destination: destination in walkable,
            questNames=lambda completed=False: ["deliverLetterQuest"] if not completed else ["rolfQuest"],
            string=lambda name: (
                json.dumps(state["hunt"])
                if name == "octobogzHuntRegistry"
                else state["victor"] if name == "quest_state_victor" else state["chain"]
            ),
            flag=lambda name: name == "OCTOBOGZ_SLAIN" and state["hunt"]["stage"] == "cleared",
            hunt=hunt,
            snapshot=lambda: {"coords": state["coords"], "exp": state["exp"]},
            record=lambda action: state["order"].append(action),
            navigateTo=lambda name: state["order"].append("navigate:" + name),
            combats=0,
        )
        authored = ({"catacombs": cave_coords}, walkable)
        return driver, state, authored

    def testActualClearHuntEarnsLevelBeforeScoutAndRecoversBetweenEveryEncounter(self):
        # After actual relic recovery, the eight entrance opponents supplement the ten passive spawns.
        driver, state, authored = self.fixture(enemies=12, cave_present=False)
        boundary = routes.huntQuestBoundary(driver)
        with patch("tests.narrative_walkthrough.authoredRegion", return_value=authored):
            routes.clearHunt(driver)
        self.assertEqual(6000, state["exp"])
        self.assertEqual(12, driver.combats)
        self.assertEqual(boundary, routes.huntQuestBoundary(driver))
        self.assertEqual(0, state["scrolls"])
        self.assertEqual(
            [
                "enterHunt",
                "retreatWithOwnedAuthoredScroll",
                "prepareHealingStockAtAuthoredMarket",
                "recoverOnAuthoredRoad",
                "defeat",
                "recoverBeforeRemainingBrood",
                "defeat",
            ],
            state["order"][state["order"].index("enterHunt") :],
        )

    def testQuestProgressItemReplacementAndControllerReplacementAreRejected(self):
        for corruption in ("quest", "identity", "controller"):
            with self.subTest(corruption=corruption):
                driver, state, authored = self.fixture(corrupt=corruption)
                with patch("tests.narrative_walkthrough.authoredRegion", return_value=authored):
                    with self.assertRaisesRegex(AssertionError, "Gooby preparation changed"):
                        routes.prepareEarnedHuntLevel(driver)
                self.assertEqual([], state["steps"])

    def testFiniteEnemyExhaustionFailsWithoutInventingFurtherExperience(self):
        for count, gain, expected_fights in ((0, 125, 0), (10, 125, 10), (18, 1, 18)):
            with self.subTest(enemies=count):
                driver, state, authored = self.fixture(
                    enemies=count, experience_per_enemy=gain, cave_present=count <= 10
                )
                with patch("tests.narrative_walkthrough.authoredRegion", return_value=authored):
                    with self.assertRaisesRegex(AssertionError, "Finite authored preparation did not earn"):
                        routes.prepareEarnedHuntLevel(driver)
                self.assertEqual(expected_fights, driver.combats)
                self.assertEqual(4500 + expected_fights * gain, state["exp"])
                self.assertNotIn("enterHunt", state["order"])

    def testSourceRoutingCannotEnterTheStillPresentRelicCave(self):
        driver, state, authored = self.fixture()
        boundary = routes.huntQuestBoundary(driver)
        walkable = authored[1] - {authored[0]["catacombs"]}
        routes.walkHuntPreparation(driver, (59, 115, 0), walkable, boundary)
        self.assertEqual((59, 115, 0), state["coords"])
        self.assertNotIn(authored[0]["catacombs"], state["steps"])
        self.assertEqual(boundary, routes.huntQuestBoundary(driver))

    def testMovementReplansAroundANativeObjectWallOnPassableTerrain(self):
        driver, state, authored = self.fixture(enemies=0)
        boundary = routes.huntQuestBoundary(driver)
        blocked = (58, 115, 0)
        walkable = (set(authored[1]) - {authored[0]["catacombs"]}) | {(57, 116, 0), (58, 116, 0), (59, 116, 0)}
        probes = []

        def can_step(destination):
            probes.append(destination)
            return destination in walkable and destination != blocked

        original_step = driver.step

        def checked_step(destination):
            self.assertNotEqual(blocked, destination, "The native controller rejects this object wall")
            original_step(destination)

        driver.canStep, driver.step = can_step, checked_step
        routes.walkHuntPreparation(driver, (59, 115, 0), walkable, boundary)
        self.assertIn(blocked, probes)
        self.assertNotIn(blocked, state["steps"])
        self.assertEqual((59, 115, 0), state["coords"])
        self.assertEqual(boundary, routes.huntQuestBoundary(driver))
        self.assertLessEqual(len(state["steps"]), 512)

    def testMovementStallKeepsTheExistingBoundAndDoesNotAwardExperience(self):
        driver, state, authored = self.fixture(stalled=True)
        with self.assertRaisesRegex(AssertionError, "existing 512-step bound"):
            routes.walkHuntPreparation(driver, (58, 115, 0), authored[1], routes.huntQuestBoundary(driver))
        self.assertEqual(512, len(state["steps"]))
        self.assertEqual(4250, state["exp"])
        self.assertEqual(0, driver.combats)

    def testOtherExistingClassesKeepTheirOwnOrdinaryControllerAndPreparation(self):
        for class_id in ("Warrior", "Assasin", "Inquisitor", "Wayfarer"):
            with self.subTest(class_id=class_id):
                driver, state, _authored = self.fixture(class_id=class_id)
                boundary = routes.huntQuestBoundary(driver)
                routes.prepareEarnedHuntLevel(driver)
                self.assertEqual([], state["order"])
                self.assertEqual(boundary, routes.huntQuestBoundary(driver))

    def victorFixture(
        self,
        *,
        resolved=None,
        corrupt=None,
        turn_cost=1,
        affordable=True,
        incidental_leader=False,
        missing_victory=False,
    ):
        names = ("cultLeaderQuest", *("victorCultist" + str(index) for index in range(1, 5)))
        actors = {name: {"__handle__": name} for name in names}
        items = {name: {"__handle__": name} for name in ("ward", "portal", "quest", "staff", "life")}
        market = {"__handle__": "actual-victor-market"}
        state = {
            "victor": resolved or "not_started",
            "turn": 0,
            "gold": 200,
            "exp": 5375,
            "dead": set(),
            "order": [],
            "victories": [],
        }

        def fight(name):
            state["order"].append(name)
            state["turn"] += turn_cost
            if corrupt != "despawn":
                state["dead"].add(name)
            if corrupt != "experience":
                state["exp"] += 250 if name == "cultLeaderQuest" else 125
            if corrupt != "despawn":
                state["victories"].append({"seq": len(state["victories"]) + 1, "name": name})
            if name == "cultLeaderQuest" or incidental_leader:
                if not incidental_leader:
                    self.assertEqual(set(names), state["dead"])
                else:
                    state["dead"].add("cultLeaderQuest")
                    state["exp"] += 250
                    if not missing_victory:
                        state["victories"].append({"seq": len(state["victories"]) + 1, "name": "cultLeaderQuest"})
                state.update(victor="good_end", gold=state["gold"] + 500)

        def call(handle, method, *args):
            identity = handle["__handle__"]
            if method == "isAlive":
                return identity not in state["dead"]
            if method == "getTurn":
                return state["turn"]
            if method == "getNumericProperty" and args == ("exp",):
                return state["exp"]
            if method == "getItems":
                return (
                    [items["life"]]
                    if handle == market
                    else [items[key] for key in ("ward", "portal", "quest", "staff")]
                )
            if method == "getTypeId":
                return {
                    "life": "LifePotion",
                    "ward": "Scroll",
                    "portal": "TownPortalScroll",
                    "quest": "holyRelic",
                    "staff": "Staff",
                }[identity]
            if method == "getEquipped":
                return {"0": items["staff"]}
            if method == "hasTag":
                return identity == "quest" and args == ("quest",)
            if method == "getSellCost":
                return 800
            if method == "getBuyCost":
                return 160 if affordable else 0
            self.fail((handle, method, args))

        driver = SimpleNamespace(
            test=self,
            game_map={"__handle__": "world"},
            player={"__handle__": "player"},
            string=lambda key: state["victor"],
            number=lambda key: 0,
            object=lambda name: actors[name],
            fight=fight,
            latestPlayerVictory=lambda map_name: state["victories"][-1] if state["victories"] else None,
            playerVictoryAgainst=lambda map_name, name, after_seq=0: next(
                (
                    record
                    for record in reversed(state["victories"])
                    if record["name"] == name and record["seq"] > after_seq
                ),
                None,
            ),
            call=call,
            gold=lambda: state["gold"],
            flag=lambda name: state["victor"] == "good_end",
            record=lambda action: state["order"].append(action),
        )
        return driver, state, market, items

    def testOptionalVictorPreparationRequiresFourActualVictoriesThenTheOriginalFiniteMarket(self):
        driver, state, market, items = self.victorFixture()
        with (
            patch.object(routes, "huntQuestBoundary", return_value="unchanged-letter-relic-controller"),
            patch.object(
                routes, "meetVictor", side_effect=lambda *args: state.update(victor="encounter_active")
            ) as meet,
            patch.object(routes, "requestedMarket", return_value=(object(), market)),
            patch.object(routes, "purchaseCallbackItem", return_value=items["life"]) as purchase,
        ):
            self.assertTrue(routes.prepareVictorHuntStock(driver, "unchanged-letter-relic-controller"))
        meet.assert_called_once_with(driver, "deescalated", False)
        self.assertEqual(
            ["victorCultist" + str(index) for index in range(1, 5)] + ["cultLeaderQuest"], state["order"][:5]
        )
        self.assertEqual(6125, state["exp"])
        purchase.assert_called_once_with(
            driver, "victorMarket", "LifePotion", {"ward"}, protected_types={"TownPortalScroll"}
        )

    def testOptionalVictorPreparationRejectsDespawnMissingExperienceDeadlineAndInsufficientQuotes(self):
        for kwargs, message in (
            ({"corrupt": "despawn"}, "genuine cultist defeats"),
            ({"corrupt": "experience"}, "not greater"),
            ({"turn_cost": 76}, "not less than or equal"),
            ({"affordable": False}, "Observed finite earned funds"),
        ):
            with self.subTest(kwargs=kwargs):
                driver, state, market, _items = self.victorFixture(**kwargs)
                with (
                    patch.object(routes, "huntQuestBoundary", return_value="boundary"),
                    patch.object(
                        routes, "meetVictor", side_effect=lambda *args: state.update(victor="encounter_active")
                    ),
                    patch.object(routes, "requestedMarket", return_value=(object(), market)),
                    patch.object(routes, "purchaseCallbackItem") as purchase,
                ):
                    with self.assertRaisesRegex(AssertionError, message):
                        routes.prepareVictorHuntStock(driver, "boundary")
                purchase.assert_not_called()

    def testIncidentalNativeLeaderVictoryCanFinishPreparationWithoutInventingCultistVictories(self):
        driver, state, market, items = self.victorFixture(incidental_leader=True)
        with (
            patch.object(routes, "huntQuestBoundary", return_value="boundary"),
            patch.object(routes, "meetVictor", side_effect=lambda *args: state.update(victor="encounter_active")),
            patch.object(routes, "requestedMarket", return_value=(object(), market)),
            patch.object(routes, "purchaseCallbackItem", return_value=items["life"]),
        ):
            self.assertTrue(routes.prepareVictorHuntStock(driver, "boundary"))
        self.assertEqual(["victorCultist1"], state["order"][:1])
        self.assertEqual({"victorCultist1", "cultLeaderQuest"}, state["dead"])
        self.assertEqual(5750, state["exp"], "Only observed victories earn experience; level four remains required")
        self.assertEqual(700, state["gold"])

    def testEarlyRescueStateAndRewardCannotReplaceTheActualPlayerLeaderVictory(self):
        driver, state, market, items = self.victorFixture(incidental_leader=True, missing_victory=True)
        with (
            patch.object(routes, "huntQuestBoundary", return_value="boundary"),
            patch.object(routes, "meetVictor", side_effect=lambda *args: state.update(victor="encounter_active")),
            patch.object(routes, "requestedMarket", return_value=(object(), market)),
            patch.object(routes, "purchaseCallbackItem", return_value=items["life"]) as purchase,
        ):
            with self.assertRaisesRegex(AssertionError, "actual player victory against the leader"):
                routes.prepareVictorHuntStock(driver, "boundary")
        purchase.assert_not_called()

    def testOptionalPreparationNeverChangesAnExistingVictorOutcome(self):
        for outcome in ("encounter_active", "good_end", "bad_end"):
            with self.subTest(outcome=outcome):
                driver, state, _market, _items = self.victorFixture(resolved=outcome)
                with patch.object(routes, "meetVictor") as meet:
                    self.assertFalse(routes.prepareVictorHuntStock(driver, "unchanged"))
                self.assertEqual(outcome, state["victor"])
                self.assertEqual([], state["order"])
                meet.assert_not_called()


if __name__ == "__main__":
    unittest.main()
