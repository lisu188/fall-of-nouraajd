# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "res"))
import ui


class FakeGui:
    def __init__(self):
        self.settings = {
            "uiScale": 100,
            "textScale": 100,
            "highContrast": False,
            "bindings": dict(ui.DEFAULT_BINDINGS),
            "customSetting": "preserve",
        }
        self.notifications = []

    def getUiPreferences(self):
        return json.dumps(self.settings)

    def applyUiPreferences(self, text):
        self.settings = json.loads(text)
        return True

    def notify(self, text):
        self.notifications.append(text)


class FakeHandler:
    def __init__(self, selections=()):
        self.selections = list(selections)
        self.screens = []
        self.errors = []
        self.confirmations = []
        self.answer = True
        self.character = ("", "")
        self.input_value = ""
        self.loading = []

    def showChoice(self, title, choices, action, back):
        self.screens.append((title, json.loads(choices), action, back))
        if not self.selections:
            raise AssertionError("Unexpected additional choice screen: " + title)
        return self.selections.pop(0)

    def showCharacterCreationOptions(self, classes, races):
        self.character_rows = (json.loads(classes), json.loads(races))
        return self.character

    def showConfirm(self, title, body, confirm_label, cancel_label):
        self.confirmations.append((title, body, confirm_label, cancel_label))
        return self.answer

    def showInfo(self, text, centered):
        self.errors.append(text)

    def showCampaignScreen(self, title, body, action):
        self.screens.append((title, body, action))

    def showTextInput(self, title, prompt, initial_value):
        return self.input_value

    def showLoading(self, text):
        self.loading.append(text)

    def hideLoading(self):
        self.loading.append("closed")


class FakeContext:
    def __init__(self):
        self.active = True

    def isActive(self):
        return self.active

    def shutdown(self):
        self.active = False


class FakeProvider:
    def __init__(self, root=None, saves=(), maps=()):
        self.root = root
        self.saves = saves
        self.maps = maps

    def getPath(self, name):
        return str(self.root / name) if self.root else ""

    def getFiles(self, kind):
        return self.saves if kind == "SAVE" else self.maps


class FakeGame:
    def __init__(self, selections=(), current=None):
        self.gui = FakeGui()
        self.handler = FakeHandler(selections)
        self.context = FakeContext()
        self.provider = FakeProvider()
        self.current = current

    def getGui(self):
        return self.gui

    def getGuiHandler(self):
        return self.handler

    def getContext(self):
        return self.context

    def getResourcesProvider(self):
        return self.provider

    def getMap(self):
        return self.current


class FrontendChoiceTest(unittest.TestCase):
    def testChoicePreservesOrderAndDuplicateLabels(self):
        game = FakeGame(["second"])
        rows = [{"id": "second", "label": "Same"}, {"id": "first", "label": "Same"}]
        self.assertEqual("second", ui.choose(game, "Choose", rows))
        self.assertEqual(rows, game.handler.screens[0][1])

    def testUnknownDisabledAndCancelledChoicesAreRejected(self):
        rows = [{"id": "available", "label": "Available"}, {"id": "disabled", "label": "Disabled", "enabled": False}]
        for selection in ("missing", "disabled", ""):
            with self.subTest(selection=selection):
                self.assertEqual("", ui.choose(FakeGame([selection]), "Choose", rows))

    def testDuplicateIdsFailBeforeOpeningUi(self):
        game = FakeGame()
        with self.assertRaises(ValueError):
            ui.choose(game, "Choose", [{"id": "same", "label": "One"}, {"id": "same", "label": "Two"}])
        self.assertEqual([], game.handler.screens)

    def testCharacterConfirmationReturnsOnlyKnownIds(self):
        choices = ([{"id": "Warrior", "label": "Warrior"}], [{"id": "humanRace", "label": "Human"}])
        for selection, expected in (
            (("", ""), ("", "")),
            (("unknown", "humanRace"), ("", "")),
            (("Warrior", "humanRace"), ("Warrior", "humanRace")),
        ):
            game = FakeGame()
            game.handler.character = selection
            with patch.object(ui, "characterChoices", return_value=choices):
                self.assertEqual(expected, ui.chooseCharacter(game))

    def testNoSelectableRaceKeepsTemplateRace(self):
        game = FakeGame()
        game.handler.character = ("Warrior", ui.DEFAULT_RACE_ID)
        rows = ([{"id": "Warrior", "label": "Warrior"}], [{"id": ui.DEFAULT_RACE_ID, "label": "Default race"}])
        with patch.object(ui, "characterChoices", return_value=rows):
            self.assertEqual(("Warrior", ""), ui.chooseCharacter(game))

    def testCharacterPreviewComposesSelectableRaceOnDetachedTemplates(self):
        game = FakeGame()
        objects = Mock()
        objects.getAllSubTypes.side_effect = lambda base: ["Warrior"] if base == "CPlayer" else ["humanRace", "npcRace"]
        game.getObjectHandler = lambda: objects
        created = []

        def createObject(type_id):
            result = Mock()
            result.getStringProperty.side_effect = lambda key: type_id if key == "label" else ""
            result.getBoolProperty.return_value = type_id == "humanRace"
            result.getActions.return_value = []
            action = types.SimpleNamespace(getStringProperty=lambda key: "Strike")
            equipment = types.SimpleNamespace(getStringProperty=lambda key: "Iron sword")
            result.getEffectiveInteractions.return_value = [action]
            result.getEquipped.return_value = {"0": equipment}
            result.getHpMax.return_value = 20
            result.getManaMax.return_value = 6
            result.getStats.return_value = types.SimpleNamespace(
                getStrength=lambda: 7, getAgility=lambda: 4, getStamina=lambda: 5, getIntelligence=lambda: 3
            )
            result.getBaseStats.return_value = result.getStats.return_value
            created.append((type_id, result))
            return result

        game.createObject = createObject
        classes, races = ui.characterChoices(game)
        self.assertEqual(["humanRace"], [row["id"] for row in races])
        self.assertIn("Health 20", classes[0]["previews"]["humanRace"])
        self.assertIn("Strength 7", classes[0]["previews"]["humanRace"])
        self.assertIn("Starting abilities\nStrike", classes[0]["previews"]["humanRace"])
        self.assertIn("Starting equipment\nIron sword", classes[0]["previews"]["humanRace"])
        templates = [obj for type_id, obj in created if type_id == "Warrior"]
        self.assertEqual(2, len(templates))
        templates[0].setObjectProperty.assert_not_called()
        templates[1].addExp.assert_called_once_with(0)
        templates[1].heal.assert_called_once_with(0)
        templates[1].setObjectProperty.assert_called_once_with("race", created[-1][1])

    def testHelpUsesATitledScrollableAcknowledgement(self):
        game = FakeGame()
        ui.showHelp(game)
        self.assertEqual([("Help", ui.helpText(game), "Continue")], game.handler.screens)
        self.assertEqual([], game.handler.errors)

    def testCampaignBrowserIncludesSavedChapterProgress(self):
        game = FakeGame(["story"])
        manifest = {
            "campaignId": "story",
            "title": "A story",
            "start": "first",
            "scenarios": {
                "first": {"title": "The beginning", "briefing": "Begin here."},
                "second": {"title": "The crossing", "briefing": "Cross here."},
            },
        }
        saves = [{"campaignId": "story", "scenarioId": "second", "label": "At the bridge"}]
        with (
            patch.object(ui.campaign, "list_campaigns", return_value=[manifest]),
            patch.object(ui, "savedGames", return_value=saves),
        ):
            self.assertEqual("story", ui.chooseCampaign(game))
        detail = game.handler.screens[0][1][0]["detail"]
        self.assertIn("Chapters: 2", detail)
        self.assertIn("Saved chapter: The crossing", detail)
        self.assertIn("At the bridge", detail)

    def testDefeatShowsOnlyResolvedLossReceiptWithoutChangingThePlayer(self):
        player = Mock()
        player.getStringProperty.return_value = json.dumps(
            {"map": "nouraajd", "hp": 12, "lostItems": [{"id": "sword", "label": "Iron sword", "count": 1}]}
        )
        game_map = Mock()
        game_map.getPlayer.return_value = player
        game = FakeGame(["continue"], game_map)
        ui.showDefeat(game)
        detail = game.handler.screens[0][1][0]["detail"]
        self.assertIn("Health after recovery: 12", detail)
        self.assertIn("Iron sword x1", detail)
        player.setStringProperty.assert_called_once_with("uiDefeatReceipt", "")
        player.removeItem.assert_not_called()

    def testCancelledNewAdventureNeverStartsAMap(self):
        game = FakeGame([""])
        loader = Mock()
        with patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}):
            self.assertFalse(ui.newAdventure(game))
        loader.startGameWithPlayer.assert_not_called()
        loader.startRandomGameWithPlayer.assert_not_called()

    def testStandaloneScenariosExcludeEveryCampaignChapterMap(self):
        game = FakeGame(["scenario", "", ""])
        game.provider = FakeProvider(maps=["openingMap", "standaloneMap", "lateChapter", "secondCampaign"])
        manifests = [
            {"scenarios": {"opening": {"map": "openingMap"}, "ending": {"map": "lateChapter"}}},
            {"scenarios": {"opening": {"map": "secondCampaign"}}},
        ]
        loader = Mock()
        with (
            patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}),
            patch.object(ui.campaign, "list_campaigns", return_value=manifests),
        ):
            self.assertFalse(ui.newAdventure(game))
        scenario_rows = next(rows for title, rows, _, _ in game.handler.screens if title == "Choose a scenario")
        self.assertEqual(["standaloneMap"], [row["id"] for row in scenario_rows])
        loader.startGameWithPlayer.assert_not_called()

    def testCampaignOnlyContentShowsTheStandaloneEmptyStateAndAllowsBack(self):
        game = FakeGame(["scenario", ""])
        game.provider = FakeProvider(maps=["openingMap"])
        loader = Mock()
        with (
            patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}),
            patch.object(ui.campaign, "list_campaigns", return_value=[{"scenarios": {"first": {"map": "openingMap"}}}]),
        ):
            self.assertFalse(ui.newAdventure(game))
        self.assertTrue(any("No scenarios are available" in error for error in game.handler.errors))
        self.assertEqual(["New adventure", "New adventure"], [screen[0] for screen in game.handler.screens])
        loader.startGameWithPlayer.assert_not_called()

    def testScenarioPreviewUsesOnlyTheAuthoredArrivalAndKeepsStableId(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenario = root / "maps" / "ninemarches"
            scenario.mkdir(parents=True)
            (scenario / "config.json").write_text(
                json.dumps(
                    {
                        "lateQuest": {"class": "Quest", "properties": {"text": "Unplayed ending"}},
                        "arrival": {"class": "StartEvent", "properties": {"text": "Follow the road to Gravewatch."}},
                    }
                ),
                encoding="utf-8",
            )
            game = FakeGame()
            game.provider = FakeProvider(root)
            with patch.object(ui.campaign, "artworkForMap", return_value=""):
                rows = ui.scenarioChoices(game, ["ninemarches", "missingMap"])
            self.assertEqual(
                {"id": "ninemarches", "label": "Nine Marches", "detail": "Follow the road to Gravewatch."}, rows[0]
            )
            self.assertEqual("Missing Map", rows[1]["label"])
            self.assertNotIn("Unplayed ending", rows[0]["detail"])

    def testMainMenuOrderAndUnavailableContinue(self):
        game = FakeGame(["quit"])
        self.assertFalse(ui.mainMenu(game))
        rows = game.handler.screens[0][1]
        self.assertEqual(["continue", "new", "load", "settings", "help", "quit"], [row["id"] for row in rows])
        self.assertFalse(rows[0]["enabled"])
        self.assertFalse(game.context.active)

    def testMainMenuContinueResumesCurrentMapWithoutLoading(self):
        current = object()
        game = FakeGame(["continue"], current)
        self.assertTrue(ui.mainMenu(game, in_session=True))
        self.assertIs(current, game.current)
        self.assertTrue(game.context.active)

    def testPauseEscapeResumesWithoutMutation(self):
        current = object()
        game = FakeGame([""], current)
        ui.pause(game)
        self.assertIs(current, game.current)
        self.assertEqual([], game.gui.notifications)
        self.assertTrue(game.context.active)


class FrontendSaveTest(unittest.TestCase):
    def setUp(self):
        ui.SAVE_PREVIEW_CACHE.clear()
        ui.SESSION_SAVE_STATUS.clear()

    def testSuccessfulSaveTimestampIsShownInPauseAndRetainedAfterFailure(self):
        game = FakeGame(["resume"], current=object())
        original_settings = dict(game.gui.settings)
        loader = types.SimpleNamespace(saveWithResult=Mock(return_value=True))
        with (
            patch.dict(sys.modules, {"_game": types.SimpleNamespace(CMapLoader=loader)}),
            patch.object(ui, "datetime", wraps=datetime) as clock,
        ):
            clock.now.return_value = datetime(2026, 9, 13, 14, 2, 3)
            self.assertTrue(ui.saveGame(game, "before-gate"))
            status = ui.sessionSaveStatus(game)
            self.assertEqual("Last successful save: 2026-09-13 14:02:03 · Before gate.", status)
            loader.saveWithResult.return_value = False
            clock.now.return_value = datetime(2026, 9, 13, 14, 5, 0)
            self.assertFalse(ui.saveGame(game, "later-attempt"))
            self.assertEqual(status, ui.sessionSaveStatus(game))
        ui.pause(game)
        self.assertIn(status, game.handler.screens[0][1][0]["detail"])
        self.assertIn(status, game.handler.screens[0][1][1]["detail"])
        self.assertEqual(original_settings, game.gui.settings)
        self.assertEqual("No successful save in this session.", ui.sessionSaveStatus(FakeGame()))

    def testSuccessfulLoadRecordsItsOwnTimeAndFailedLoadRetainsIt(self):
        game = FakeGame(current=object())
        restored = object()
        loader = types.SimpleNamespace(
            loadSavedGame=Mock(side_effect=lambda current, slot: setattr(current, "current", restored))
        )
        with (
            patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}),
            patch.object(ui, "datetime", wraps=datetime) as clock,
        ):
            clock.now.return_value = datetime(2026, 9, 13, 15, 4, 5)
            self.assertTrue(ui.loadGame(game, "journey"))
            status = ui.sessionSaveStatus(game)
            self.assertEqual("Last successful load: 2026-09-13 15:04:05 · Journey.", status)
            loader.loadSavedGame.side_effect = OSError("corrupt save")
            clock.now.return_value = datetime(2026, 9, 13, 15, 8, 0)
            self.assertFalse(ui.loadGame(game, "broken"))
            self.assertEqual(status, ui.sessionSaveStatus(game))
        self.assertIn(status, game.handler.confirmations[-1][1])

    def testEveryDiscardPromptIncludesTheLastSuccessfulOperation(self):
        for flow in ("main", "pause", "new", "load"):
            with self.subTest(flow=flow):
                game = FakeGame(["random", ""] if flow == "new" else ["quit", "resume"], current=object())
                game.handler.answer = False
                with patch.object(ui, "datetime", wraps=datetime) as clock:
                    clock.now.return_value = datetime(2026, 9, 13, 12, 34, 56)
                    ui.recordSessionSave(game, "checkpoint", "save")
                with (
                    patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=Mock())}),
                    patch.object(ui, "chooseCharacter", return_value=("Warrior", "humanRace")),
                ):
                    if flow == "main":
                        game.handler.selections = ["quit", "continue"]
                        ui.mainMenu(game)
                    elif flow == "pause":
                        ui.pause(game)
                    elif flow == "new":
                        ui.newAdventure(game)
                    else:
                        ui.loadGame(game, "other")
                self.assertIn("2026-09-13 12:34:56", game.handler.confirmations[0][1])
                self.assertTrue(game.context.active)

    def testNewAdventureDoesNotInheritThePreviousAdventuresSaveStatus(self):
        game = FakeGame(["random"], current=object())
        ui.recordSessionSave(game, "old-adventure", "save")
        new_map = types.SimpleNamespace(getPlayer=lambda: object())
        loader = types.SimpleNamespace(
            startRandomGameWithPlayer=Mock(side_effect=lambda current, *args: setattr(current, "current", new_map))
        )
        with (
            patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}),
            patch.object(ui, "chooseCharacter", return_value=("Warrior", "humanRace")),
        ):
            self.assertTrue(ui.newAdventure(game))
        self.assertEqual("No successful save in this session.", ui.sessionSaveStatus(game))

    def testLegacyAndVersionedSavesShowMetadataWithoutLoadingEngine(self):
        for versioned in (True, False):
            with self.subTest(versioned=versioned), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "save").mkdir()
                snapshot = {
                    "class": "CMap",
                    "properties": {
                        "mapName": "nouraajd",
                        "turn": 21,
                        "objects": [{"class": "CPlayer", "properties": {"playerClassId": "Warrior", "level": 4}}],
                    },
                }
                document = {"snapshot": snapshot, "mapName": "nouraajd"} if versioned else snapshot
                (root / "save" / "journey.json").write_text(json.dumps(document), encoding="utf-8")
                row = ui.readSavePreview(FakeProvider(root), "journey")
                self.assertIn("Map: Nouraajd", row["detail"])
                self.assertIn("Turn: 21", row["detail"])
                self.assertIn("Class: Warrior", row["detail"])
                self.assertIn("Level: 4", row["detail"])

    def testCorruptPrimaryUsesBackupMetadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "save").mkdir()
            (root / "save" / "journey.json").write_text("broken", encoding="utf-8")
            (root / "save" / "journey.json.bak").write_text(
                json.dumps({"class": "CMap", "properties": {"mapName": "ritual"}}), encoding="utf-8"
            )
            row = ui.readSavePreview(FakeProvider(root), "journey")
            self.assertIn("Map: Ritual", row["detail"])
            self.assertIn("Recovery copy", row["detail"])

    def testMissingSavePreviewRemainsLoadableForNativeRecovery(self):
        row = ui.readSavePreview(FakeProvider(), "journey")
        self.assertEqual("journey", row["id"])
        self.assertIn("Preview unavailable", row["detail"])
        self.assertNotIn("enabled", row)

    def testSaveFailureDoesNotClaimSuccess(self):
        game = FakeGame(current=object())
        loader = types.SimpleNamespace(saveWithResult=Mock(return_value=False))
        with patch.dict(sys.modules, {"_game": types.SimpleNamespace(CMapLoader=loader)}):
            self.assertFalse(ui.saveGame(game, "journey"))
        self.assertEqual([], game.gui.notifications)
        self.assertIn("could not be saved", game.handler.errors[0])

    def testSuccessfulSaveUsesNativeStatusAndNotifies(self):
        game = FakeGame(current=object())
        loader = types.SimpleNamespace(saveWithResult=Mock(return_value=True))
        with patch.dict(sys.modules, {"_game": types.SimpleNamespace(CMapLoader=loader)}):
            self.assertTrue(ui.saveGame(game, "journey"))
        loader.saveWithResult.assert_called_once_with(game.current, "journey")
        self.assertEqual(["Saved Journey."], game.gui.notifications)
        self.assertEqual(["Saving your adventure...", "closed"], game.handler.loading)

    def testManualSaveUsesEnteredName(self):
        game = FakeGame(["newSave"], current=object())
        game.handler.input_value = "Before the gate"
        with patch.object(ui, "saveGame", return_value=True) as save:
            self.assertTrue(ui.saveMenu(game))
        save.assert_called_once_with(game, "Before-the-gate")

    def testNamedSaveCancellationDoesNotWrite(self):
        game = FakeGame(["newSave"], current=object())
        with patch.object(ui, "saveGame") as save:
            self.assertFalse(ui.saveMenu(game))
        save.assert_not_called()

    def testNamingAnExistingSlotStillRequiresOverwriteConfirmation(self):
        game = FakeGame(["newSave"], current=object())
        game.provider.saves = ["Before-the-gate"]
        game.handler.input_value = "Before the gate"
        game.handler.answer = False
        with patch.object(ui, "saveGame") as save:
            self.assertFalse(ui.saveMenu(game))
        save.assert_not_called()

    def testSaveNameValidationRejectsPathTraversal(self):
        for name in ("../escape", "save/elsewhere", ".hidden", "double..dot", "", " " * 10, "a" * 81):
            with self.subTest(name=name):
                self.assertEqual("", ui.normalizeSaveName(name))
        self.assertEqual("After-the-ruins", ui.normalizeSaveName(" After the ruins "))

    def testCancelledOverwriteDoesNotWrite(self):
        game = FakeGame(["slot:journey"], current=object())
        game.provider.saves = ["journey"]
        game.handler.answer = False
        with patch.object(ui, "saveGame") as save:
            self.assertFalse(ui.saveMenu(game))
        save.assert_not_called()

    def testLoadFailureKeepsPreviousMapAndDoesNotNotify(self):
        current = object()
        game = FakeGame(current=current)
        loader = types.SimpleNamespace(loadSavedGame=Mock())
        with patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}):
            self.assertFalse(ui.loadGame(game, "journey"))
        self.assertIs(current, game.current)
        self.assertEqual([], game.gui.notifications)
        self.assertIn("could not be loaded", game.handler.errors[0])
        self.assertEqual(["Loading saved adventure...", "closed"], game.handler.loading)

    def testLoadCancellationDoesNotCallLoader(self):
        game = FakeGame(current=object())
        game.handler.answer = False
        loader = types.SimpleNamespace(loadSavedGame=Mock())
        with patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}):
            self.assertFalse(ui.loadGame(game, "journey"))
        loader.loadSavedGame.assert_not_called()


class FrontendPreferencesTest(unittest.TestCase):
    def testSettingsUpdatesPreserveOtherFields(self):
        game = FakeGame(["textScale", "150", ""])
        ui.showSettings(game)
        self.assertEqual(150, game.gui.settings["textScale"])
        self.assertEqual("preserve", game.gui.settings["customSetting"])
        self.assertEqual(ui.DEFAULT_BINDINGS, game.gui.settings["bindings"])

    def testHelpReflectsRemappedKeys(self):
        game = FakeGame()
        game.gui.settings["bindings"]["inventory"] = "b"
        text = ui.helpText(game)
        self.assertIn("Inventory: b", text)
        self.assertNotIn("Developer console", text)
        self.assertIn("preview a route", text)
        self.assertIn("Choose Travel or press Enter", text)
        self.assertIn("Select an item to inspect", text)
        self.assertIn("holding a key does not repeat", text)
        self.assertIn("Press M to expand", text)
        self.assertIn("inspecting menus does not", text)
        self.assertIn("[ and ] switch between panel regions", text)

    def testResetUsesNativeDefaultsOnlyAfterExplicitConfirmation(self):
        game = FakeGame(["reset", ""])
        game.gui.applyUiPreferences = Mock(return_value=True)
        ui.showSettings(game)
        game.gui.applyUiPreferences.assert_called_once_with("{}")
        self.assertEqual("Reset defaults", game.handler.confirmations[0][2])
        self.assertIn("Text size: 100%", game.handler.confirmations[0][1])
        self.assertEqual(["Settings saved."], game.gui.notifications)

    def testCancellingResetKeepsCurrentSettings(self):
        game = FakeGame(["reset", ""])
        game.handler.answer = False
        game.gui.applyUiPreferences = Mock()
        ui.showSettings(game)
        game.gui.applyUiPreferences.assert_not_called()
        self.assertEqual([], game.gui.notifications)

    def testPreferenceFailureReportsErrorAndKeepsPreviousValues(self):
        game = FakeGame(["textScale", "150", ""])
        previous = dict(game.gui.settings)
        game.gui.applyUiPreferences = Mock(return_value=False)
        ui.showSettings(game)
        self.assertEqual(previous, game.gui.settings)
        self.assertIn("could not be applied", game.handler.errors[0])
        self.assertEqual([], game.gui.notifications)

    def testBindingChoicesRejectConflicts(self):
        game = FakeGame(["inventory", "s"])
        self.assertIsNone(ui.configureBinding(game, game.gui.settings))
        key_rows = game.handler.screens[1][1]
        self.assertFalse(next(row for row in key_rows if row["id"] == "s")["enabled"])
        self.assertEqual("i", game.gui.settings["bindings"]["inventory"])


class FrontendSafetyDetailsTest(unittest.TestCase):
    def testCampaignPreviewUsesCampaignOrOpeningChapterArtwork(self):
        for campaign_art, chapter_art, expected in (
            ("images/campaign.png", "images/chapter.png", "images/campaign.png"),
            ("", "images/chapter.png", "images/chapter.png"),
            ("", "", ""),
        ):
            with self.subTest(campaign_art=campaign_art, chapter_art=chapter_art):
                game = FakeGame(["story"])
                manifest = {
                    "campaignId": "story",
                    "title": "A story",
                    "start": "opening",
                    "artwork": campaign_art,
                    "scenarios": {"opening": {"title": "Opening", "briefing": "Begin here.", "artwork": chapter_art}},
                }
                with patch.object(ui.campaign, "list_campaigns", return_value=[manifest]):
                    self.assertEqual("story", ui.chooseCampaign(game))
                row = game.handler.screens[0][1][0]
                self.assertEqual(expected, row.get("image", ""))
                if not expected:
                    self.assertNotIn("image", row)

    def testScenarioPreviewIncludesOnlyAvailableMapArtwork(self):
        game = FakeGame()
        with patch.object(ui.campaign, "artworkForMap", side_effect=["images/map.png", ""]) as artwork:
            rows = ui.scenarioChoices(game, ["knownMap", "unknownMap"])
        self.assertEqual("images/map.png", rows[0]["image"])
        self.assertNotIn("image", rows[1])
        self.assertEqual(["knownMap", "unknownMap"], [call.args[0] for call in artwork.call_args_list])

    def testExpandedMapBindingIsDisabledAndCannotReplaceAControl(self):
        game = FakeGame(["inventory", "m"])
        self.assertIsNone(ui.configureBinding(game, game.gui.settings))
        map_key = next(row for row in game.handler.screens[1][1] if row["id"] == "m")
        self.assertFalse(map_key["enabled"])
        self.assertIn("Reserved for the expanded map", map_key["detail"])
        self.assertEqual("i", game.gui.settings["bindings"]["inventory"])

    def testStandaloneMetadataFailureKeepsSessionAndAllowsRetry(self):
        active_map = object()
        game = FakeGame(["scenario", "scenario", "standaloneMap", ""], current=active_map)
        game.provider = FakeProvider(maps=["standaloneMap"])
        loader = Mock()
        with (
            patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}),
            patch.object(ui.campaign, "list_campaigns", side_effect=[ValueError("Unreadable campaign"), [], []]),
            patch.object(ui, "chooseCharacter", return_value=("", "")),
        ):
            self.assertFalse(ui.newAdventure(game))
        self.assertIs(active_map, game.getMap())
        self.assertIn("Campaign information could not be read", game.handler.errors[0])
        self.assertIn("try again or go Back", game.handler.errors[0])
        self.assertEqual(3, sum(screen[0] == "New adventure" for screen in game.handler.screens))
        self.assertEqual(1, sum(screen[0] == "Choose a scenario" for screen in game.handler.screens))
        loader.startGameWithPlayer.assert_not_called()

    def testStandaloneMetadataFailureAllowsBackWithoutStartingAnything(self):
        for error in (OSError("Missing"), ValueError("Invalid"), TypeError("Wrong type"), KeyError("scenarios")):
            with self.subTest(error=type(error).__name__):
                game = FakeGame(["scenario", ""])
                loader = Mock()
                with (
                    patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}),
                    patch.object(ui.campaign, "list_campaigns", side_effect=error),
                ):
                    self.assertFalse(ui.newAdventure(game))
                self.assertEqual(["New adventure", "New adventure"], [screen[0] for screen in game.handler.screens])
                self.assertEqual(1, len(game.handler.errors))
                loader.startGameWithPlayer.assert_not_called()
                loader.startRandomGameWithPlayer.assert_not_called()

    def testStartupLoadingNamesTheActualOperation(self):
        cases = (
            ("campaign", ["campaign"], "Loading campaign..."),
            ("scenario", ["scenario", "standaloneMap"], "Entering scenario..."),
            ("random", ["random"], "Generating random dungeon..."),
        )
        for mode, selections, expected in cases:
            with self.subTest(mode=mode):
                game = FakeGame(selections)
                game.provider = FakeProvider(maps=["standaloneMap"])
                started_map = types.SimpleNamespace(getPlayer=lambda: object())

                def start(*args):
                    game.current = started_map

                loader = types.SimpleNamespace(
                    startGameWithPlayer=Mock(side_effect=start), startRandomGameWithPlayer=Mock(side_effect=start)
                )
                with (
                    patch.dict(sys.modules, {"_game": types.SimpleNamespace(CGameLoader=loader)}),
                    patch.object(ui.campaign, "list_campaigns", return_value=[]),
                    patch.object(ui.campaign, "start", side_effect=start),
                    patch.object(ui, "chooseCampaign", return_value="campaignId"),
                    patch.object(ui, "chooseCharacter", return_value=("Warrior", "humanRace")),
                ):
                    self.assertTrue(ui.newAdventure(game))
                self.assertEqual([expected, "closed"], game.handler.loading)

    def testPauseLoadExplainsWhyItIsUnavailableWithoutSaves(self):
        game = FakeGame(["load"], current=object())
        with patch.object(ui, "loadMenu") as load_menu:
            ui.pause(game)
        load_row = next(row for row in game.handler.screens[0][1] if row["id"] == "load")
        self.assertFalse(load_row["enabled"])
        self.assertIn("No saved adventures", load_row["detail"])
        load_menu.assert_not_called()

    def testPauseLoadIsAvailableWhenASaveExists(self):
        game = FakeGame(["load"], current=object())
        game.provider = FakeProvider(saves=["journey"])
        with patch.object(ui, "loadMenu", return_value=True) as load_menu:
            ui.pause(game)
        load_row = next(row for row in game.handler.screens[0][1] if row["id"] == "load")
        self.assertTrue(load_row["enabled"])
        load_menu.assert_called_once_with(game)

    def testCombatHelpExplainsSelectionExecutionRestrictionsAndPause(self):
        text = ui.helpText(FakeGame())
        for required in (
            "Select a living enemy",
            "select an action",
            "mana cost, and target",
            "Execute action",
            "more mana than you have remains unavailable",
            "Use item explicitly",
            "inspecting items do not take a turn",
            "Choose Combat log or press L to review recent combat events without taking a turn",
            "Escape opens the pause menu and keeps the encounter active",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
