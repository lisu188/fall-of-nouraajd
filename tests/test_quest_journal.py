import ast
import json
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

import quest_state

REPO_ROOT = Path(__file__).resolve().parents[1]


class JournalObject:
    def __init__(self, game=None):
        self.game = game
        self.properties = {}
        self.quests = []
        self.completed = []
        self.items = []
        self.objects = {}

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game.getMap()

    def getPlayer(self):
        return getattr(self, "player", None)

    def getQuests(self):
        return self.quests

    def getCompletedQuests(self):
        return self.completed

    def getStringProperty(self, name):
        return self.properties.get(name, "")

    def setStringProperty(self, name, value):
        self.properties[name] = value

    def getBoolProperty(self, name):
        return self.properties.get(name, False)

    def setBoolProperty(self, name, value):
        self.properties[name] = value

    def getNumericProperty(self, name):
        return self.properties.get(name, 0)

    def setNumericProperty(self, name, value):
        self.properties[name] = value

    def getName(self):
        return self.getStringProperty("name")

    def getTypeId(self):
        return self.getStringProperty("typeId")

    def getDescription(self):
        return self.getStringProperty("description")

    def getObjective(self):
        return self.getStringProperty("objective")

    def getReward(self):
        return self.getStringProperty("reward")

    def getHint(self):
        return self.getStringProperty("hint")

    def captureJournal(self, completed):
        pass

    def isCompleted(self):
        return False

    def getTurn(self):
        return 12

    def hasItem(self, predicate):
        return any(predicate(item) for item in self.items)

    def getObjectByName(self, name):
        return self.objects.get(name)


def loadQuestClasses(path):
    classes = {}

    def register(_context):
        def capture(cls):
            classes[cls.__name__] = cls
            return cls

        return capture

    game_stub = types.ModuleType("game")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "game":
            for alias in node.names:
                setattr(game_stub, alias.name, type(alias.name, (JournalObject,), {}))
    for name in ("LegacyBoolFlag", "PlayerQuestRegistry", "QuestStateStore", "ensure_quest", "mapQuest"):
        if hasattr(quest_state, name):
            setattr(game_stub, name, getattr(quest_state, name))
    game_stub.register = register
    game_stub.trigger = lambda context, *_args: register(context)
    game_stub.campaign = types.SimpleNamespace()
    game_stub.claim_once = lambda *_args: True
    game_stub.remove_runtime_actors = lambda *_args, **_kwargs: 0
    queued_work = []
    game_stub.event_loop = types.SimpleNamespace(instance=lambda: types.SimpleNamespace(invoke=queued_work.append))
    context = types.SimpleNamespace(getMap=lambda: None)
    with patch.dict(sys.modules, {"game": game_stub}):
        runpy.run_path(str(path))["load"](None, context)
    return classes


class MapQuestJournalTest(unittest.TestCase):
    def createSession(self, map_name="origin"):
        game = types.SimpleNamespace()
        game.getMap = lambda: game.map
        game.messages = []
        game.getGuiHandler = lambda: types.SimpleNamespace(showMessage=game.messages.append)
        source = JournalObject(game)
        source.mapName = map_name
        player = JournalObject(game)
        source.player = player
        destination = JournalObject(game)
        destination.mapName = "destination"
        destination.player = player
        game.map = source
        return game, source, destination, player

    def createQuest(self, game, player):
        decorator = getattr(quest_state, "mapQuest", lambda _source: lambda cls: cls)

        @decorator("origin")
        class ProgressQuest(JournalObject):
            def isCompleted(self):
                return self.getMap().getBoolProperty("done")

            def getObjective(self):
                return "Done" if self.isCompleted() else f"Progress {self.getMap().getNumericProperty('progress')}"

            def getReward(self):
                return ""

            def getHint(self):
                if getattr(self, "fail_hint", False):
                    raise ValueError("capture failed")
                return ""

        quest = ProgressQuest(game)
        quest.properties.update(name="progressQuest", typeId="progressQuest", description="Recover the relic.")
        player.quests.append(quest)
        return quest

    def journalText(self, quest):
        return quest.getObjective(), quest.getReward(), quest.getHint()

    def test_unread_source_progress_survives_departure_without_destination_reads(self):
        game, source, destination, player = self.createSession()
        quest = self.createQuest(game, player)
        source.setNumericProperty("progress", 4)
        quest.captureJournal(False)
        destination.properties.update(done=True, progress=99)
        before_destination = destination.properties.copy()
        game.map = destination

        self.assertEqual(("Progress 4", "", ""), self.journalText(quest))
        self.assertFalse(quest.isCompleted())
        self.assertEqual(before_destination, destination.properties)
        self.assertEqual([], game.messages)
        self.assertEqual([quest], player.quests)
        self.assertEqual([], player.completed)

    def test_completed_history_is_fixed_after_source_reload_and_property_round_trip(self):
        game, source, destination, player = self.createSession()
        quest = self.createQuest(game, player)
        source.setBoolProperty("done", True)
        quest.captureJournal(True)
        player.quests.clear()
        player.completed.append(quest)
        expected = self.journalText(quest)
        game.map = destination
        self.assertEqual(expected, self.journalText(quest))
        self.assertTrue(quest.isCompleted())
        quest.properties = json.loads(json.dumps(quest.properties))
        game.map = source
        source.properties.clear()
        quest.captureJournal(True)
        self.assertEqual(("Done", "", ""), self.journalText(quest))
        self.assertTrue(quest.isCompleted())

    def test_failed_capture_keeps_last_valid_snapshot(self):
        game, source, destination, player = self.createSession()
        quest = self.createQuest(game, player)
        source.setNumericProperty("progress", 4)
        quest.captureJournal(False)
        before_snapshot = quest.properties.copy()
        source.setNumericProperty("progress", 5)
        quest.fail_hint = True
        with self.assertRaisesRegex(ValueError, "capture failed"):
            quest.captureJournal(False)
        self.assertEqual(before_snapshot, quest.properties)
        game.map = destination
        self.assertEqual(("Progress 4", "", ""), self.journalText(quest))

    def test_legacy_completed_status_uses_neutral_history_without_destination_flags(self):
        game, _source, destination, player = self.createSession()
        quest = self.createQuest(game, player)
        player.quests.clear()
        player.completed.append(quest)
        destination.properties.update(progress=99)
        before_destination = destination.properties.copy()
        game.map = destination
        self.assertTrue(quest.isCompleted())
        self.assertIn("unavailable", quest.getObjective())
        self.assertIn("older save", quest.getHint())
        self.assertNotIn("99", quest.getObjective())
        self.assertEqual(before_destination, destination.properties)

    def test_legacy_completed_status_survives_fresh_source_without_inventing_outcome(self):
        game, source, _destination, player = self.createSession()
        quest = self.createQuest(game, player)
        player.quests.clear()
        player.completed.append(quest)
        self.assertTrue(quest.isCompleted())
        self.assertIn("Completed; outcome details are unavailable", quest.getObjective())
        quest.captureJournal(True)
        source.setNumericProperty("progress", 99)
        self.assertTrue(quest.isCompleted())
        self.assertIn("unavailable", quest.getObjective())
        self.assertNotIn("99", quest.getObjective())

    def test_authored_quest_matrix_keeps_all_27_journals_and_destination_state(self):
        count = 0
        plugin_classes = loadQuestClasses(REPO_ROOT / "res/plugins/castle_campaign.py")
        for map_dir in sorted((REPO_ROOT / "res/maps").iterdir()):
            if not (map_dir / "script.py").is_file():
                continue
            classes = {**plugin_classes, **loadQuestClasses(map_dir / "script.py")}
            config = json.loads((map_dir / "config.json").read_text(encoding="utf-8"))
            for quest_name, entry in config.items():
                cls = classes.get(entry.get("class"))
                if cls is None or not any(base.__name__ == "CQuest" for base in cls.__mro__):
                    continue
                count += 1
                with self.subTest(map=map_dir.name, quest=quest_name):
                    game, source, destination, player = self.createSession(map_dir.name)
                    quest = cls(game)
                    quest.properties.update(entry.get("properties", {}))
                    quest.properties.update(name=quest_name, typeId=quest_name)
                    player.quests.append(quest)
                    self.prepareSource(map_dir.name, source, player)
                    quest.captureJournal(False)
                    expected = self.journalText(quest)
                    if quest_name == "defendSiegeQuest":
                        self.assertIn("2/4 sealed", expected[0])
                    if quest_name == "ninemarchesQuest":
                        self.assertIn("Ser Halda", expected[1])
                    saved = json.loads(json.dumps(quest.properties))
                    destination.properties.update(source.properties)
                    before_destination = destination.properties.copy()
                    game.map = destination
                    self.assertFalse(quest.isCompleted())
                    self.assertEqual(expected, self.journalText(quest))
                    restored = cls(game)
                    restored.properties = saved
                    player.quests[:] = [restored]
                    self.assertEqual(expected, self.journalText(restored))
                    self.assertFalse(restored.isCompleted())
                    self.assertEqual(before_destination, destination.properties)
                    self.assertEqual([], game.messages)
        self.assertEqual(27, count)

    def test_all_27_completed_journals_survive_round_trip_and_fresh_source(self):
        count = 0
        plugin_classes = loadQuestClasses(REPO_ROOT / "res/plugins/castle_campaign.py")
        for map_dir in sorted((REPO_ROOT / "res/maps").iterdir()):
            if not (map_dir / "script.py").is_file():
                continue
            classes = {**plugin_classes, **loadQuestClasses(map_dir / "script.py")}
            config = json.loads((map_dir / "config.json").read_text(encoding="utf-8"))
            for quest_name, entry in config.items():
                cls = classes.get(entry.get("class"))
                if cls is None or not any(base.__name__ == "CQuest" for base in cls.__mro__):
                    continue
                count += 1
                with self.subTest(map=map_dir.name, quest=quest_name):
                    game, source, destination, player = self.createSession(map_dir.name)
                    quest = cls(game)
                    quest.properties.update(entry.get("properties", {}))
                    quest.properties.update(name=quest_name, typeId=quest_name)
                    player.quests.append(quest)
                    self.prepareSource(map_dir.name, source, player)
                    source.properties.update(
                        victory_reported=True,
                        voss_judged=True,
                        voss_spared=True,
                        loyalists_freed=3,
                        throne_taken=True,
                        boss_defeated=True,
                        crown_taken=True,
                        seer_done=True,
                        tithe_taken=True,
                        anchors_destroyed=True,
                        anchors_destroyed_count=3,
                        leader_defeated=True,
                        captive_freed=True,
                        good_ending=True,
                        halda_joined=True,
                        morrigane_joined=True,
                        corvyn_joined=True,
                        quest_state_main="gooby_slain",
                        quest_state_rolf="skull_recovered",
                        quest_state_beren_chain="purged",
                        quest_state_octobogz_contract="completed",
                        quest_state_amulet="returned",
                        quest_state_victor="good_end",
                    )
                    for gate in source.objects.values():
                        gate.setBoolProperty("destroyed", True)
                    scenario = quest.getStringProperty("campaign_scenarioId")
                    if scenario:
                        player.setBoolProperty("campaign_castleCompleted_" + scenario, True)
                    self.assertTrue(quest.isCompleted())
                    quest.captureJournal(True)
                    expected = self.journalText(quest)
                    player.quests.clear()
                    player.completed[:] = [quest]
                    game.map = destination
                    self.assertEqual(expected, self.journalText(quest))
                    self.assertTrue(quest.isCompleted())
                    restored = cls(game)
                    restored.properties = json.loads(json.dumps(quest.properties))
                    player.completed[:] = [restored]
                    self.assertEqual(expected, self.journalText(restored))
                    self.assertTrue(restored.isCompleted())
                    game.map = source
                    source.properties.clear()
                    restored.captureJournal(True)
                    self.assertEqual(expected, self.journalText(restored))
                    self.assertTrue(restored.isCompleted())
                    self.assertEqual({}, destination.properties)
                    self.assertEqual([], game.messages)
        self.assertEqual(27, count)

    def prepareSource(self, map_name, source, player):
        source.properties.update(
            progress=2,
            loyalists_freed=2,
            anchors_destroyed_count=2,
            obelisks_read=4,
            chapter=3,
            sigils_found=2,
            halda_joined=True,
        )
        if map_name == "nouraajd":
            source.properties.update(quest_state_amulet="active", quest_state_victor="encounter_active")
        if map_name == "siege":
            for index in range(4):
                gate = JournalObject()
                gate.setBoolProperty("destroyed", index < 2)
                source.objects[f"spawnPoint{index + 1}"] = gate
        if map_name.startswith("castle"):
            scenario = map_name.removeprefix("castle")
            scenario = scenario[0].lower() + scenario[1:]
            marker = JournalObject()
            marker.setStringProperty(
                "campaign_mission",
                json.dumps({"scenarioId": scenario, "objectiveIds": ["first", "second"], "enemyHeroIds": []}),
            )
            source.objects["castleMission"] = marker
            for name in ("first", "second"):
                objective = JournalObject()
                objective.setStringProperty("label", name.title())
                source.objects[name] = objective
            source.setBoolProperty("campaign_castleCaptured_first", True)


if __name__ == "__main__":
    unittest.main()
