import json
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

import quest_state

REPO_ROOT = Path(__file__).resolve().parents[1]


class PropertyObject:
    def __init__(self, game=None):
        self.game = game
        self.properties = {}

    def getGame(self):
        return self.game

    def getPlayer(self):
        return getattr(self, "player", None)

    def getStringProperty(self, name):
        return self.properties.get(name, "")

    def setStringProperty(self, name, value):
        self.properties[name] = value

    def getBoolProperty(self, name):
        return self.properties.get(name, False)

    def setBoolProperty(self, name, value):
        self.properties[name] = value

    def setNumericProperty(self, name, value):
        self.properties[name] = value

    def getTurn(self):
        return 12


def loadQuestClasses(game_map=None, context=None, pending=None):
    classes = {}

    def register(context):
        def capture(cls):
            classes[cls.__name__] = cls
            return cls

        return capture

    game_stub = types.ModuleType("game")
    for name in ("CEvent", "CTrigger", "CQuest", "CPlayer", "CDialog", "Coords"):
        setattr(game_stub, name, type(name, (PropertyObject,), {}))
    for name in ("LegacyBoolFlag", "PlayerQuestRegistry", "QuestStateStore", "ensure_quest"):
        setattr(game_stub, name, getattr(quest_state, name))

    class QuestStateStore(quest_state.QuestStateStore):
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            classes[cls.__name__] = cls

    game_stub.QuestStateStore = QuestStateStore
    game_stub.claim_once = lambda *_args: True
    game_stub.remove_runtime_actors = lambda *_args, **_kwargs: 0
    game_stub.showReader = lambda *_args, **_kwargs: None
    game_stub.rewardSnapshot = lambda *_args, **_kwargs: {}
    game_stub.showRewardReceipt = lambda *_args, **_kwargs: None
    game_stub.register = register
    game_stub.trigger = lambda context, *_args: register(context)
    game_stub.campaign = types.SimpleNamespace()
    game_stub.narrative = types.SimpleNamespace()
    callbacks = pending if pending is not None else []
    game_stub.event_loop = types.SimpleNamespace(instance=lambda: types.SimpleNamespace(invoke=callbacks.append))
    if context is None:
        context = types.SimpleNamespace(getMap=lambda: game_map)
    with patch.dict(sys.modules, {"game": game_stub}):
        runpy.run_path(str(REPO_ROOT / "res/maps/nouraajd/script.py"))["load"](None, context)
    return classes


class NouraajdQuestJournalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quest_classes = loadQuestClasses()

    def createSession(self):
        player = PropertyObject()
        nouraajd = PropertyObject()
        nouraajd.player = player
        nouraajd.mapName = "nouraajd"
        ritual = PropertyObject()
        ritual.player = player
        ritual.mapName = "ritual"
        game = types.SimpleNamespace(map=nouraajd)
        game.getMap = lambda: game.map
        return game, nouraajd, ritual, player

    def test_victor_state_survives_map_transition_and_player_property_round_trip(self):
        for outcome in ("encounter_active", "good_end", "bad_end"):
            with self.subTest(outcome=outcome):
                game, nouraajd, ritual, player = self.createSession()
                quest_system = self.quest_classes["QuestSystem"](nouraajd)
                quest_system.mark_victor_encounter_active()
                if outcome == "good_end":
                    quest_system.mark_victor_good_end()
                elif outcome == "bad_end":
                    quest_system.mark_victor_bad_end()
                quest = self.quest_classes["VictorQuest"](game)

                expected_text = (quest.getObjective(), quest.getReward(), quest.getHint())
                completed = outcome != "encounter_active"
                self.assertEqual(completed, quest.isCompleted())
                if completed:
                    quest.onComplete()
                game.map = ritual

                self.assertEqual(expected_text, (quest.getObjective(), quest.getReward(), quest.getHint()))
                self.assertEqual(completed, quest.isCompleted())
                self.assertEqual({}, ritual.properties)

                restored_player = PropertyObject()
                restored_player.properties = json.loads(json.dumps(player.properties))
                ritual.player = restored_player
                restored_quest = self.quest_classes["VictorQuest"](game)
                self.assertEqual(
                    expected_text,
                    (restored_quest.getObjective(), restored_quest.getReward(), restored_quest.getHint()),
                )
                self.assertEqual(completed, restored_quest.isCompleted())
                self.assertEqual({}, ritual.properties)

    def test_unread_victor_state_ignores_contradictory_destination_map(self):
        game, nouraajd, ritual, _player = self.createSession()
        quest_system = self.quest_classes["QuestSystem"](nouraajd)
        quest_system.mark_victor_encounter_active()
        quest_system.mark_victor_bad_end()
        ritual.setStringProperty("quest_state_victor", "good_end")
        game.map = ritual

        quest = self.quest_classes["VictorQuest"](game)

        self.assertIn("was taken", quest.getObjective())
        self.assertEqual("No reward if Victor's daughter is taken.", quest.getReward())
        self.assertTrue(quest.isCompleted())
        self.assertEqual({"quest_state_victor": "good_end"}, ritual.properties)

    def test_legacy_nouraajd_map_overrides_player_snapshot_before_departure(self):
        game, nouraajd, ritual, player = self.createSession()
        player.setStringProperty("nouraajdVictorState", "good_end")
        nouraajd.setStringProperty("quest_state_victor", "bad_end")
        quest = self.quest_classes["VictorQuest"](game)

        self.assertIn("was taken", quest.getObjective())
        game.map = ritual
        self.assertIn("was taken", quest.getObjective())
        self.assertEqual({}, ritual.properties)

    def test_quest_defaults_initialize_without_a_player(self):
        game_map = PropertyObject()
        quest_system = self.quest_classes["QuestSystem"](game_map)

        self.assertTrue(quest_system.initialize_defaults())
        self.assertEqual("not_started", quest_system.get_state("victor"))

    def checkCompletedSaveMigration(self, outcome, objective, reward):
        game, nouraajd, ritual, player = self.createSession()
        quest_type = self.quest_classes["QuestSystem"]
        for quest, value in quest_type.QUEST_DEFAULTS.items():
            nouraajd.setStringProperty(quest_type.QUEST_KEYS[quest], outcome if quest == "victor" else value)
        for flag in quest_type.LEGACY_BOOL_FLAGS:
            state = nouraajd.getStringProperty(quest_type.QUEST_KEYS[flag.quest])
            nouraajd.setBoolProperty(flag.name, flag.evaluate(state))
        nouraajd.setNumericProperty("VICTOR_COURTYARD_TURN", 37)
        nouraajd.setBoolProperty("VICTOR_REWARD_GRANTED", outcome == "good_end")
        player.setNumericProperty("gold", 937)
        player.setNumericProperty("hp", 41)
        player.setStringProperty("inventoryFixture", "LifePotion,ShadowBlade")
        completed_quest = self.quest_classes["VictorQuest"](game)
        player.getCompletedQuests = lambda: [completed_quest]
        before_map = dict(nouraajd.properties)
        before_player = dict(player.properties)
        self.assertFalse(quest_type(nouraajd).initialize_defaults())
        self.assertEqual("", player.getStringProperty("nouraajdVictorState"))

        # The native save loader registers scripts without a map, before restoring the player.
        game.map = None
        pending = []
        loaded_classes = loadQuestClasses(context=game, pending=pending)
        self.assertEqual("", player.getStringProperty("nouraajdVictorState"))
        game.map = nouraajd
        # Request travel immediately; migration must precede the queued scene transition.
        pending.append(lambda: setattr(game, "map", ritual))
        while pending:
            pending.pop(0)()
        self.assertIs(ritual, game.map)
        restored_player = PropertyObject()
        restored_player.properties = json.loads(json.dumps(player.properties))
        ritual.player = restored_player
        restored_quest = loaded_classes["VictorQuest"](game)

        self.assertIn(objective, restored_quest.getObjective())
        self.assertIn(reward, restored_quest.getReward())
        self.assertTrue(restored_quest.isCompleted())
        self.assertEqual(outcome, restored_player.getStringProperty("nouraajdVictorState"))
        self.assertEqual({**before_player, "nouraajdVictorState": outcome}, restored_player.properties)
        self.assertEqual(before_map, nouraajd.properties)
        self.assertEqual({}, ritual.properties)
        self.assertEqual([completed_quest], player.getCompletedQuests())

    def testLoadedRescuedSaveMigratesBeforeUnreadDeparture(self):
        self.checkCompletedSaveMigration("good_end", "survived", "500 gold")

    def testLoadedTimedOutSaveMigratesBeforeUnreadDeparture(self):
        self.checkCompletedSaveMigration("bad_end", "was taken", "No reward")

    def testFreshNouraajdLoadPreservesExistingPlayerOutcome(self):
        for outcome in ("encounter_active", "good_end", "bad_end"):
            with self.subTest(outcome=outcome):
                game, nouraajd, _ritual, player = self.createSession()
                player.setStringProperty("nouraajdVictorState", outcome)
                before_player = dict(player.properties)
                # Return travel constructs the new map before attaching the carried player.
                nouraajd.player = None
                pending = []
                loadQuestClasses(context=game, pending=pending)
                self.assertEqual("not_started", nouraajd.getStringProperty("quest_state_victor"))
                before_map = dict(nouraajd.properties)
                nouraajd.player = player
                self.assertEqual(1, len(pending))
                pending.pop()()

                self.assertEqual(before_player, player.properties)
                self.assertEqual(before_map, nouraajd.properties)

    def testFreshNouraajdJournalKeepsCompletedOutcome(self):
        for outcome, objective, reward, hint in (
            ("good_end", "survived", "500 gold", "fled the courtyard alive"),
            ("bad_end", "was taken", "No reward", "courtyard is empty"),
        ):
            with self.subTest(outcome=outcome):
                game, nouraajd, _ritual, player = self.createSession()
                player.setStringProperty("nouraajdVictorState", outcome)
                nouraajd.setStringProperty("quest_state_victor", "not_started")
                before_player = dict(player.properties)
                before_map = dict(nouraajd.properties)
                quest = self.quest_classes["VictorQuest"](game)

                self.assertIn(objective, quest.getObjective())
                self.assertIn(reward, quest.getReward())
                self.assertIn(hint, quest.getHint())
                self.assertTrue(quest.isCompleted())
                self.assertEqual(before_player, player.properties)
                self.assertEqual(before_map, nouraajd.properties)

    def testUnrelatedQuestProgressPreservesCompletedVictorSnapshot(self):
        for outcome in ("good_end", "bad_end"):
            with self.subTest(outcome=outcome):
                game, nouraajd, _ritual, player = self.createSession()
                nouraajd.player = None
                quest_system = self.quest_classes["QuestSystem"](nouraajd)
                quest_system.initialize_defaults()
                nouraajd.player = player
                player.setStringProperty("nouraajdVictorState", outcome)
                player.setNumericProperty("gold", 937)
                player.setNumericProperty("hp", 41)
                before_player = dict(player.properties)

                quest_system.start_amulet()

                self.assertEqual("active", quest_system.get_state("amulet"))
                self.assertEqual("not_started", quest_system.get_state("victor"))
                for flag in quest_system.LEGACY_BOOL_FLAGS:
                    self.assertEqual(
                        flag.evaluate(quest_system.get_state(flag.quest)), nouraajd.getBoolProperty(flag.name)
                    )
                self.assertEqual(before_player, player.properties)
                self.assertTrue(self.quest_classes["VictorQuest"](game).isCompleted())

    def testLegacySyncRetainsMeaningfulVictorSourceStatePrecedence(self):
        for outcome in ("encounter_active", "good_end", "bad_end"):
            with self.subTest(outcome=outcome):
                _game, nouraajd, _ritual, player = self.createSession()
                player.setStringProperty("nouraajdVictorState", "bad_end" if outcome == "good_end" else "good_end")
                nouraajd.setStringProperty("quest_state_victor", outcome)

                self.quest_classes["QuestSystem"](nouraajd).sync_legacy_flags()

                self.assertEqual(outcome, player.getStringProperty("nouraajdVictorState"))
                self.assertEqual(outcome, nouraajd.getStringProperty("quest_state_victor"))

    def testDependencyRegistrationDoesNotReadDetachedNouraajdState(self):
        game, nouraajd, ritual, player = self.createSession()
        player.setStringProperty("nouraajdVictorState", "good_end")
        nouraajd.setStringProperty("quest_state_victor", "bad_end")
        ritual.setStringProperty("quest_state_victor", "bad_end")
        before_source = dict(nouraajd.properties)
        before_destination = dict(ritual.properties)
        game.map = None
        pending = []
        loadQuestClasses(context=game, pending=pending)
        self.assertEqual(1, len(pending))
        game.map = ritual
        pending.pop()()

        self.assertEqual("good_end", player.getStringProperty("nouraajdVictorState"))
        self.assertEqual(before_source, nouraajd.properties)
        self.assertEqual(before_destination, ritual.properties)

    def testDeferredMigrationToleratesAbsentMapOrPlayer(self):
        for has_map in (False, True):
            with self.subTest(has_map=has_map):
                game, nouraajd, _ritual, player = self.createSession()
                nouraajd.player = None
                game.map = None
                pending = []
                loadQuestClasses(context=game, pending=pending)
                self.assertEqual(1, len(pending))
                if has_map:
                    game.map = nouraajd
                pending.pop()()
                self.assertEqual({}, player.properties)
                self.assertEqual({}, nouraajd.properties)


if __name__ == "__main__":
    unittest.main()
