# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute bounded earned hunt preparation without a native game or forced route progress."""

import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import gameplay_routes_nouraajd as routes
from tests.gameplay_branch_rewards import observeMainQuestReward, requireMainQuestReward, resetMainQuestRewardSession
from tests.test_gameplay_route_dialogs import authoredFunction


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

    def mainQuestRewardFixture(self, *, pay=True, player_class="Warrior"):
        player_ref = {
            "id": player_class,
            "name": "actual-hero",
            "typeId": player_class,
            "type": "CPlayer",
            "isPlayer": True,
        }
        state = {"gold": 100, "claimed": False, "records": []}
        player = SimpleNamespace(
            getItems=lambda: [],
            getEquipped=lambda: {},
            getGold=lambda: state["gold"],
            getNumericProperty=lambda key: 0,
        )
        game_map = SimpleNamespace(getPlayer=lambda: player)
        game = SimpleNamespace(getMap=lambda: game_map)

        def addGold(amount):
            if pay:
                before = state["gold"]
                state["gold"] += amount
                state["records"].append(
                    {
                        "event": "gold_changed",
                        "actor": player_ref,
                        "map": "nouraajd",
                        "before": before,
                        "after": state["gold"],
                        "delta": amount,
                    }
                )

        def showReader(game_instance, title, body):
            self.assertIs(game, game_instance)
            state["records"].append(
                {
                    "event": "reader_requested",
                    "title": title,
                    "body": body,
                    "titleLength": len(title.encode("utf-8")),
                    "bodyLength": len(body.encode("utf-8")),
                    "player": player_ref,
                    "map": "nouraajd",
                    "headless": True,
                }
            )

        def claimOnce(world, flag):
            self.assertIs(game_map, world)
            self.assertEqual("GOOBY_REWARD_CLAIMED", flag)
            if state["claimed"]:
                return False
            state["claimed"] = True
            return True

        player.addGold = addGold
        snapshot = authoredFunction("res/game.py", "rewardSnapshot")
        receipt = authoredFunction("res/game.py", "showRewardReceipt", rewardSnapshot=snapshot, showReader=showReader)
        complete = authoredFunction(
            "res/maps/nouraajd/script.py",
            "onComplete",
            class_id="MainQuest",
            claim_once=claimOnce,
            rewardSnapshot=snapshot,
            showRewardReceipt=receipt,
            MAIN_QUEST_GOLD_REWARD=200,
        )
        quest = SimpleNamespace(getGame=lambda: game)
        state["records"].append(
            {"event": "quest_completed", "quest": "mainQuest", "player": player_ref, "map": "nouraajd"}
        )
        complete(quest)
        return state, lambda: complete(quest)

    def testActualMainQuestRewardFunctionsProduceExactlyOneNativePaymentAndReceipt(self):
        state, repeat = self.mainQuestRewardFixture()
        validator = SimpleNamespace()
        for record in state["records"]:
            observeMainQuestReward(validator, [record])
        receipt = requireMainQuestReward(validator, "actual-hero")
        self.assertEqual(300, state["gold"])
        self.assertEqual(200, receipt["payment"]["delta"])
        before = copy.deepcopy(state)
        repeat()
        self.assertEqual(before, state, "The actual claim guard must prevent repeated grants and receipts")
        observeMainQuestReward(validator, [{"event": "map_moved"}])
        self.assertIs(receipt, requireMainQuestReward(validator, "actual-hero"))

    def testFreshHuntGamesDrainAndIsolateRewardsForSameNameIncludingSameClass(self):
        from tests.gameplay_branch_driver import GameplayBranchDriver
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        helper = OctobogzMcpWalkthroughTest(methodName="runTest")
        positions = {"native.jsonl": {"offset": 123}}
        validator = SimpleNamespace(
            _combat_failure=None, _combat_trace_positions=positions, _combat_trace_seq=300, _player_victories={}
        )
        helper._native_combat_validator = validator
        helper.refresh, helper.pump = Mock(), Mock()
        pending, starts, drained = [], [], []

        def drain(actual):
            self.assertIs(validator, actual)
            if pending:
                observeMainQuestReward(actual, pending)
                drained.append(requireMainQuestReward(actual, "actual-hero"))
                actual._combat_trace_seq += len(pending)
                pending.clear()

        def engine(name, *args):
            if name == "CGameLoader.loadGame":
                with self.assertRaisesRegex(AssertionError, "actual 200-gold"):
                    requireMainQuestReward(validator, "actual-hero")
                return {"__handle__": "game-" + str(len(starts))}
            self.assertEqual("CGameLoader.startGameWithPlayer", name)
            self.assertEqual((helper.game, "nouraajd"), args[:2])
            starts.append(args[2])

        helper.engine = engine
        with patch.object(GameplayBranchDriver, "assertNativeCombatOutcomes", side_effect=drain):
            for player_class in ("Warrior", "Sorcerer", "Sorcerer"):
                helper.startFreshHuntGame(player_class)
                state, _repeat = self.mainQuestRewardFixture(player_class=player_class)
                pending.extend(state["records"])
            drain(validator)
        self.assertEqual(["Warrior", "Sorcerer", "Sorcerer"], starts)
        self.assertEqual(starts, [receipt["completion"]["player"]["typeId"] for receipt in drained])
        self.assertEqual(3, helper.refresh.call_count)
        self.assertEqual(3, helper.pump.call_count)
        self.assertIs(positions, validator._combat_trace_positions)
        self.assertEqual(309, validator._combat_trace_seq)
        self.assertIsNone(validator._combat_failure)
        with self.assertRaisesRegex(AssertionError, "twice"):
            observeMainQuestReward(validator, state["records"])

    def testFreshRewardSessionCannotEraseUnfinishedOrFailedNativeEvidence(self):
        state, _repeat = self.mainQuestRewardFixture()
        for size in (1, 2):
            with self.subTest(received_records=size):
                validator = SimpleNamespace(_combat_failure=None)
                observeMainQuestReward(validator, state["records"][:size])
                pending = validator._pending_main_quest_reward
                receipts = validator._main_quest_rewards
                with self.assertRaisesRegex(AssertionError, "unfinished"):
                    resetMainQuestRewardSession(validator)
                self.assertIs(pending, validator._pending_main_quest_reward)
                self.assertIs(receipts, validator._main_quest_rewards)
        validator = SimpleNamespace(_combat_failure=("Unresolved native player combat", {"outcome": 3}))
        with self.assertRaisesRegex(AssertionError, "failed native evidence"):
            resetMainQuestRewardSession(validator)
        self.assertIsNotNone(validator._combat_failure)

    def testMatrixAdapterSharesFreshGameResetButRetainsCheckpointReward(self):
        from tests.gameplay_branch_driver import GameplayBranchDriver
        from tests.gameplay_branch_types import RouteCase
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        case = RouteCase("reward_session", "unit", ("nouraajd",), (), lambda driver: None)
        driver = GameplayBranchDriver(self, Mock(), {"proc": SimpleNamespace()}, case, "Warrior", ".")
        state, _repeat = self.mainQuestRewardFixture()
        phase, boundaries = ["checkpoint"], []

        def refresh():
            driver.game_map, driver.player = {"__handle__": "map"}, {"__handle__": "player"}
            driver.map_name = "nouraajd"

        def call(actor, method, *args):
            return {
                "getName": "actual-hero",
                "getGui": None,
                "getTurn": 7,
                "getStringProperty": "",
                "getBoolProperty": False,
            }[method]

        def engine(name, *args):
            if name == "CGameLoader.loadGame":
                if phase[0] != "checkpoint":
                    self.assertEqual([phase[0]], boundaries)
                    with self.assertRaisesRegex(AssertionError, "actual 200-gold"):
                        requireMainQuestReward(driver, "actual-hero")
                return {"__handle__": phase[0] + "-game"}
            if name == "CMapLoader.saveWithResult":
                return True
            self.assertIn(name, ("CGameLoader.loadSavedGame", "CGameLoader.startGameWithPlayer"))

        def drain():
            if phase[0] != "checkpoint" and not boundaries:
                self.assertIs(receipt, requireMainQuestReward(driver, "actual-hero"))
                boundaries.append(phase[0])

        refresh()
        driver.game = {"__handle__": "original-game"}
        driver.call, driver.engine, driver.refresh = call, engine, refresh
        driver.assertNativeCombatOutcomes = Mock(side_effect=drain)
        driver.assertSurvival, driver.pump = Mock(), Mock()
        driver.properties, driver._slot, driver.record = Mock(return_value={}), Mock(return_value="checkpoint"), Mock()
        with patch.object(OctobogzMcpWalkthroughTest, "trackLivingHuntActors"):
            driver.hunt("trackLivingHuntActors")
        adapter = driver._hunt_adapter
        observeMainQuestReward(driver, state["records"])
        receipt = adapter.requireOriginalMainQuestReward()
        with patch("tests.gameplay_branch_driver.verifyJournals", return_value={}):
            driver.saveAndReload("same-game")
        self.assertIs(receipt, adapter.requireOriginalMainQuestReward())

        for startup in ("map", "starting-save"):
            phase[0] = startup
            boundaries.clear()
            with (
                patch("tests.gameplay_branch_driver.captureWaypointCreation"),
                patch("tests.gameplay_branch_driver.captureAmbientCave"),
                patch(
                    "tests.gameplay_branch_driver.subprocess.run",
                    return_value=SimpleNamespace(returncode=0, stdout="{}", stderr=""),
                ),
                patch("pathlib.Path.is_file", return_value=True),
            ):
                if startup == "map":
                    driver.startMap("nouraajd")
                else:
                    driver.loadStartingSave(campaign_id="fallOfNouraajd")
            self.assertIs(adapter, driver._hunt_adapter)
            with self.assertRaisesRegex(AssertionError, "actual 200-gold"):
                adapter.requireOriginalMainQuestReward()
            observeMainQuestReward(driver, state["records"])
            receipt = adapter.requireOriginalMainQuestReward()
        with self.assertRaisesRegex(AssertionError, "twice"):
            observeMainQuestReward(driver, state["records"])

    def testActualAuthoredReceiptWithoutTheNativePaymentIsRejected(self):
        state, _repeat = self.mainQuestRewardFixture(pay=False)
        self.assertIn("No new rewards.", state["records"][-1]["body"])
        with self.assertRaisesRegex(AssertionError, "no witnessed native payment"):
            observeMainQuestReward(SimpleNamespace(), state["records"])

    def testMainQuestRewardRejectsWrongPaymentOrPresentation(self):
        state, _repeat = self.mainQuestRewardFixture()
        for label, index, changes in (
            ("amount", 1, {"after": 299, "delta": 199}),
            ("arithmetic", 1, {"after": 301}),
            ("boolean", 1, {"before": True}),
            ("recipient", 1, {"actor": {"name": "another-hero", "isPlayer": True}}),
            ("payment-map", 1, {"map": "ritual"}),
            ("receipt-player", 2, {"player": {"name": "another-hero", "isPlayer": True}}),
            ("receipt-map", 2, {"map": "ritual"}),
            ("visible-reader", 2, {"headless": False}),
            ("title-length", 2, {"titleLength": 1}),
            ("truncated", 2, {"bodyLength": 1}),
            ("lying-amount", 2, {"body": "Gold: +199", "bodyLength": 10}),
            ("duplicate-amount", 2, {"body": "Gold: +200\nGold: +200", "bodyLength": 21}),
            ("conflicting-amount", 2, {"body": "Gold: +200\nGold: +1", "bodyLength": 19}),
        ):
            with self.subTest(label=label):
                records = copy.deepcopy(state["records"])
                records[index].update(changes)
                with self.assertRaises(AssertionError):
                    observeMainQuestReward(SimpleNamespace(), records)

    def testMainQuestRewardRequiresCompletionPaymentAndPresentationInOrder(self):
        state, _repeat = self.mainQuestRewardFixture()
        completion, payment, receipt = state["records"]
        for records in (
            [receipt],
            [payment, receipt],
            [completion, receipt],
            [completion, payment, payment, receipt],
            [completion, payment, {"event": "quest_completed", "quest": "anotherQuest"}],
        ):
            with self.subTest(records=records), self.assertRaises(AssertionError):
                observeMainQuestReward(SimpleNamespace(), records)
        for records in ([], [completion], [completion, payment]):
            with self.subTest(records=records):
                validator = SimpleNamespace()
                observeMainQuestReward(validator, records)
                with self.assertRaises(AssertionError):
                    requireMainQuestReward(validator, "actual-hero")
        validator = SimpleNamespace()
        observeMainQuestReward(validator, state["records"])
        with self.assertRaisesRegex(AssertionError, "twice"):
            observeMainQuestReward(validator, state["records"])
        with self.assertRaises(AssertionError):
            requireMainQuestReward(validator, "another-hero")

    def testMainQuestCompletionRequiresAuthoredActualPlayerIdentity(self):
        state, _repeat = self.mainQuestRewardFixture()
        for changes in (
            {"player": None},
            {"player": {"name": "npc", "isPlayer": False}},
            {"player": {"name": "", "isPlayer": True}},
            {"map": "ritual"},
        ):
            with self.subTest(changes=changes):
                records = copy.deepcopy(state["records"])
                records[0].update(changes)
                with self.assertRaises(AssertionError):
                    observeMainQuestReward(SimpleNamespace(), records)

    def testOriginalGoobyHelperRejectsAutomaticCompletionWithoutItsActualReward(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        for pay in (False, True):
            with self.subTest(pay=pay):
                state, _repeat = self.mainQuestRewardFixture(pay=pay)
                helper = OctobogzMcpWalkthroughTest(methodName="runTest")
                helper.player, helper.game_map = "player", "map"
                helper.snapshot = Mock()
                helper.recoverOnRoadPair = Mock()
                helper.walkTo = Mock()
                helper.questNames = lambda method: ["mainQuest"]
                helper.call = lambda actor, method, *args: True if method == "getBoolProperty" else "actual-hero"
                helper.advanceQuestEvaluationTurn = Mock(
                    side_effect=AssertionError("Already completed during movement")
                )
                validator = SimpleNamespace(test=helper, _combat_failure=None, trace_path=None)
                helper._native_combat_validator = validator

                def verifyReward():
                    observeMainQuestReward(validator, state["records"])
                    return OctobogzMcpWalkthroughTest.requireOriginalMainQuestReward(helper)

                helper.requireOriginalMainQuestReward = verifyReward
                if pay:
                    helper.finishOriginalMainQuest()
                    self.assertEqual(300, state["gold"])
                else:
                    with self.assertRaisesRegex(AssertionError, "no witnessed native payment"):
                        helper.finishOriginalMainQuest()
                helper.advanceQuestEvaluationTurn.assert_not_called()

    def testMatrixHuntAdapterRequiresTheSameDriverOwnedRewardEvidence(self):
        state, _repeat = self.mainQuestRewardFixture()
        driver = SimpleNamespace(
            assertNativeCombatOutcomes=Mock(), call=Mock(return_value="actual-hero"), player="hero"
        )
        verify = authoredFunction(
            "tests/gameplay_branch_driver.py",
            "requireOriginalMainQuestReward",
            class_id="Adapter",
            driver=driver,
            requireMainQuestReward=requireMainQuestReward,
        )
        with self.assertRaisesRegex(AssertionError, "actual 200-gold"):
            verify(SimpleNamespace())
        observeMainQuestReward(driver, state["records"])
        self.assertEqual(200, verify(SimpleNamespace())["payment"]["delta"])
        self.assertEqual(2, driver.assertNativeCombatOutcomes.call_count)
        driver.call.assert_called_with(driver.player, "getName")

    def testSharedNativeValidatorCollectsAndLatchesMainQuestEvidence(self):
        from tests.gameplay_branch_driver import GameplayBranchDriver

        state, _repeat = self.mainQuestRewardFixture()
        for pay in (True, False):
            with self.subTest(pay=pay):
                records = copy.deepcopy(state["records"])
                if not pay:
                    records.pop(1)
                for seq, record in enumerate(records, start=1):
                    record["seq"] = seq
                validator = SimpleNamespace(
                    test=self,
                    _combat_failure=None,
                    trace_path="native.jsonl",
                    _combat_trace_positions={},
                    _combat_trace_seq=0,
                    player=None,
                )
                with (
                    patch.object(GameplayBranchDriver, "assertNativeTraceOutput"),
                    patch("tests.gameplay_branch_driver.readNewNativeTrace", return_value=records),
                ):
                    if pay:
                        GameplayBranchDriver.assertNativeCombatOutcomes(validator)
                        self.assertEqual(200, requireMainQuestReward(validator, "actual-hero")["payment"]["delta"])
                    else:
                        with self.assertRaisesRegex(AssertionError, "Invalid native MainQuest reward"):
                            GameplayBranchDriver.assertNativeCombatOutcomes(validator)
                        self.assertIsNotNone(validator._combat_failure)
                        with self.assertRaises(AssertionError):
                            GameplayBranchDriver.assertNativeCombatOutcomes(validator)


if __name__ == "__main__":
    unittest.main()
