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


def loadQuestClasses():
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
    game_stub.register = register
    game_stub.trigger = lambda context, *_args: register(context)
    game_stub.campaign = types.SimpleNamespace()
    context = types.SimpleNamespace(getMap=lambda: None)
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


if __name__ == "__main__":
    unittest.main()
