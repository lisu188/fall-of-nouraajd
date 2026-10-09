# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Victor's real rescue callback precedes the next native quest evaluation."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import gameplay_routes_nouraajd as routes
from tests import gameplay_routes_recipe_gold as gold_routes
from tests.test_gameplay_route_dialogs import authoredFunction

ROOT = Path(__file__).resolve().parents[1]


class SettledRoute(Exception):
    """Stop the focused fixture after the completed-quest assertion."""


class GameplayVictorSettlementTest(unittest.TestCase):
    def fixture(self, *, callback_refused=False, combat_failed=False):
        state = {
            "victor": "bad_end" if callback_refused else "encounter_active",
            "gold": 220,
            "turn": 12,
            "flags": {},
            "active": {"victorQuest"},
            "completed": {"rolfQuest", "mainQuest"},
            "alive": True,
            "order": [],
        }
        player, leader = ({"__handle__": name} for name in ("player", "leader"))
        native_player = SimpleNamespace(
            addGold=lambda amount: state.update(gold=state["gold"] + amount), healProc=Mock()
        )
        world = SimpleNamespace(
            getPlayer=lambda: native_player,
            getBoolProperty=lambda key: state["flags"].get(key, False),
        )
        gui = SimpleNamespace(showTrade=lambda market: state["order"].append("actual-callback-market"))
        game = SimpleNamespace(
            getMap=lambda: world,
            getGuiHandler=lambda: gui,
            createObject=lambda identity: SimpleNamespace(getStates=lambda: []),
        )
        quest_system = SimpleNamespace(
            get_state=lambda identity: state["victor"],
            mark_victor_good_end=lambda: state.update(victor="good_end"),
        )

        def claimOnce(game_map, key):
            if state["flags"].get(key):
                return False
            state["flags"][key] = True
            return True

        source = "res/maps/nouraajd/script.py"
        rescue = authoredFunction(
            source,
            "trigger",
            class_id="CultLeaderQuestTrigger",
            _quest_system_from=lambda obj: quest_system,
            claim_once=claimOnce,
            rewardSnapshot=Mock(),
            showRewardReceipt=Mock(),
            narrative=SimpleNamespace(victorResponse=lambda actual_game: ""),
            _clear_victor_encounter=Mock(),
        )
        completed = authoredFunction(source, "isCompleted", class_id="VictorQuest")
        quest = SimpleNamespace(_getState=lambda: state["victor"])
        trigger = SimpleNamespace(getGame=lambda: game)

        def fight(name):
            self.assertEqual("cultLeaderQuest", name)
            state["order"].append("native-combat")
            if combat_failed:
                raise AssertionError("A defeated hero cannot finish the rescue")
            state["alive"] = False
            rescue(trigger, leader, None)
            # CMap sends player.onTurn/checkQuests before this movement combat.
            self.assertNotIn("victorQuest", state["completed"])

        def call(handle, method, *args):
            if handle == player:
                if method == "getStringProperty":
                    return "deescalated"
                if method == "getItems":
                    return []
                if method == "getEquipped":
                    return {}
                if method == "checkQuests":
                    state["order"].append("native-quest-evaluation")
                    self.assertFalse(state["alive"])
                    self.assertEqual("good_end", state["victor"])
                    if completed(quest):
                        state["active"].discard("victorQuest")
                        state["completed"].add("victorQuest")
                    return None
            self.fail((handle, method, args))

        def check(branch, condition, **evidence):
            self.assertTrue(condition, branch)

        def barrier(*args, **kwargs):
            raise SettledRoute

        def hunt(method):
            self.assertEqual("finishOriginalMainQuest", method)
            state["gold"] = 220

        driver = SimpleNamespace(
            test=self,
            player=player,
            race_id="humanRace",
            call=call,
            object=lambda name, required=True: leader if state["alive"] else None,
            fight=fight,
            check=check,
            string=lambda key: state["victor"],
            flag=lambda key: state["flags"].get(key, False),
            questNames=lambda completed=False: sorted(state["completed" if completed else "active"]),
            gold=lambda: state["gold"],
            hunt=hunt,
            navigateTo=barrier,
        )
        return driver, state, barrier

    def runRescuePrefix(self, route, driver, state, barrier):
        module = routes if route == "victor" else gold_routes
        with (
            patch.object(module, "meetVictor"),
            patch.object(module, "victorCountdownCheckpoint"),
            patch.object(gold_routes, "raceAid", lambda d: state.update(gold=20)),
            patch.object(gold_routes, "prepareRolf"),
            patch.object(gold_routes, "callbackContext"),
            patch.object(gold_routes, "requestedMarket", barrier),
        ):
            if route == "victor":
                routes.victorRoute(driver, "deescalated", direct=False, saved=True, start_new=False)
            else:
                gold_routes.nourPortalGoldRefusal(driver)

    def testBothActualRescueCallersSettleTheEarnedQuestWithoutAnotherMapTurn(self):
        for route in ("victor", "portal-gold"):
            for class_id in ("Warrior", "Assasin", "Sorcerer", "Inquisitor", "Wayfarer"):
                with self.subTest(route=route, class_id=class_id):
                    driver, state, barrier = self.fixture()
                    driver.class_id = class_id
                    with self.assertRaises(SettledRoute):
                        self.runRescuePrefix(route, driver, state, barrier)
                    self.assertEqual(
                        ["native-combat", "actual-callback-market", "native-quest-evaluation"], state["order"]
                    )
                    self.assertEqual(720, state["gold"])
                    self.assertEqual(12, state["turn"])
                    self.assertEqual({"rolfQuest", "mainQuest", "victorQuest"}, state["completed"])
                    self.assertEqual(set(), state["active"])

    def testARefusedRescueCallbackCannotBeSettledIntoACompletedQuest(self):
        for route in ("victor", "portal-gold"):
            with self.subTest(route=route):
                driver, state, barrier = self.fixture(callback_refused=True)
                with self.assertRaises(AssertionError):
                    self.runRescuePrefix(route, driver, state, barrier)
                self.assertNotIn("native-quest-evaluation", state["order"])
                self.assertNotIn("victorQuest", state["completed"])
                self.assertEqual({"victorQuest"}, state["active"])

    def testACombatFailureCannotReachQuestSettlement(self):
        for route in ("victor", "portal-gold"):
            with self.subTest(route=route):
                driver, state, barrier = self.fixture(combat_failed=True)
                with self.assertRaisesRegex(AssertionError, "defeated hero"):
                    self.runRescuePrefix(route, driver, state, barrier)
                self.assertEqual(["native-combat"], state["order"])
                self.assertEqual({"victorQuest"}, state["active"])

    def testNativeQuestEvaluationOccursBeforeTheTurnMovementAndDoesNotMoveThePlayer(self):
        map_source = (ROOT / "src/core/CMap.cpp").read_text(encoding="utf-8")
        move = map_source[map_source.index("void CMap::move() {") :]
        self.assertLess(move.index("CGameEvent::CType::onTurn"), move.index("struct PlannedCreature"))
        trigger = map_source[
            map_source.index('auto turnTrigger = std::make_shared<CCustomTrigger>("player", "onTurn"') :
        ]
        self.assertIn("_player->checkQuests();", trigger[:400])
        player_source = (ROOT / "src/object/CPlayer.cpp").read_text(encoding="utf-8")
        check = player_source[player_source.index("void CPlayer::checkQuests() {") :]
        check = check[: check.index("void CPlayer::captureQuestJournal()")]
        self.assertIn("quest->isCompleted()", check)
        self.assertIn("completedQuests.insert(quest);", check)
        for forbidden in ("moveTo(", "setCoords(", "addGold(", "setHp("):
            self.assertNotIn(forbidden, check)
