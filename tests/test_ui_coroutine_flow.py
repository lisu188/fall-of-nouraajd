# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import gc
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

from tests.test_ui_frontend import FakeGame, ui


class UiCoroutineFlowTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(ui.campaign, "hasPendingTransition", return_value=False))

    def advance(self, flow, answer=None):
        result = flow.advance(json.dumps(answer))
        return json.loads(result) if result is not None else None

    def testPauseHelpAndResumeYieldWithoutCallingSynchronousModals(self):
        game = FakeGame(current=object())
        flow = ui.UiFlow("pause", lambda: game)
        self.addCleanup(flow.close)
        request = self.advance(flow)
        self.assertEqual("showChoice", request["operation"])
        self.assertEqual("Paused", request["args"][0])
        request = self.advance(flow, "help")
        self.assertEqual("showCampaignScreen", request["operation"])
        self.assertEqual("Help", request["args"][0])
        self.assertEqual("showChoice", self.advance(flow)["operation"])
        self.assertIsNone(self.advance(flow, "resume"))
        self.assertEqual([], game.handler.screens)
        self.assertTrue(game.context.active)

    def testSettingsFlowAppliesTheExistingPreferenceBehavior(self):
        game = FakeGame(current=object())
        flow = ui.UiFlow("pause", lambda: game)
        self.addCleanup(flow.close)
        self.advance(flow)
        self.assertEqual("Settings", self.advance(flow, "settings")["args"][0])
        self.assertEqual("Settings", self.advance(flow, "highContrast")["args"][0])
        self.assertTrue(game.gui.settings["highContrast"])
        self.assertEqual("Paused", self.advance(flow, "")["args"][0])
        self.assertIsNone(self.advance(flow, "resume"))
        self.assertEqual([], game.handler.screens)

    def testInvalidSaveNameYieldsErrorAndRetainsEnteredText(self):
        game = FakeGame(current=object())
        flow = ui.UiFlow("saveMenu", lambda: game)
        self.addCleanup(flow.close)
        self.assertEqual("showChoice", self.advance(flow)["operation"])
        self.assertEqual("showTextInput", self.advance(flow, "newSave")["operation"])
        self.assertEqual("showCampaignScreen", self.advance(flow, "..invalid")["operation"])
        self.assertEqual("..invalid", self.advance(flow)["args"][2])
        self.assertIsNone(self.advance(flow, ""))
        self.assertEqual([], game.handler.screens)

    def testSaveResultAndFailureUseTheSharedPythonBehavior(self):
        for successful in (True, False):
            with self.subTest(successful=successful):
                game = FakeGame(current=object())
                save = Mock(return_value=successful)
                native = SimpleNamespace(CMapLoader=SimpleNamespace(saveWithResult=save))
                flow = ui.UiFlow("saveMenu", lambda: game)
                self.addCleanup(flow.close)
                with patch.dict(sys.modules, {"_game": native}):
                    self.advance(flow)
                    self.advance(flow, "newSave")
                    request = self.advance(flow, "session-slot")
                    save.assert_called_once_with(game.current, "session-slot")
                    if successful:
                        self.assertIsNone(request)
                        self.assertIn("Session slot", ui.sessionSaveStatus(game))
                    else:
                        self.assertEqual("Save failed", request["args"][0])
                        self.assertIsNone(self.advance(flow))
                self.assertEqual(["Saving your adventure...", "closed"], game.handler.loading)
                self.assertEqual([], game.handler.screens)

    def testCancellationClosesAllNestedFramesAndTheirFinallyBlocks(self):
        game = FakeGame(current=object())

        def pauseFlow(game):
            with ui.loading(game, "Waiting"):
                yield ui.uiRequest("choose", game, "Nested", [{"id": "ok"}])

        with patch.object(ui, "pauseFlow", pauseFlow):
            flow = ui.UiFlow("pause", lambda: game)
            self.assertEqual("showChoice", self.advance(flow)["operation"])
            flow.close()
            flow.close()
        self.assertEqual(["Waiting", "closed"], game.handler.loading)
        self.assertEqual([], game.handler.screens)

    def testSuspendedFlowDoesNotOwnItsGame(self):
        game = FakeGame(current=object())
        owner = weakref.ref(game)
        flow = ui.UiFlow("pause", owner)
        self.advance(flow)
        del game
        gc.collect()
        self.assertIsNone(owner())
        flow.close()

    def testDefeatFlowYieldsResolvedReceiptWithoutSynchronousModalsOrRepeatedLosses(self):
        player = Mock()
        player.getStringProperty.return_value = json.dumps(
            {"map": "nouraajd", "hp": 7, "lostItems": [{"id": "oldSword", "label": "Old sword", "count": 2}]}
        )
        game_map = SimpleNamespace(getPlayer=lambda: player)
        game = FakeGame(current=game_map)
        flow = ui.UiFlow("showDefeat", lambda: game)
        self.addCleanup(flow.close)
        request = self.advance(flow)
        self.assertEqual("showChoice", request["operation"])
        self.assertEqual("Defeated", request["args"][0])
        choices = json.loads(request["args"][1])
        self.assertIn("Health after recovery: 7", choices[0]["detail"])
        self.assertIn("Old sword x2", choices[0]["detail"])
        player.setStringProperty.assert_called_once_with("uiDefeatReceipt", "")
        self.assertEqual([], game.handler.screens, "native defeat recovery must yield rather than call a sync modal")
        self.assertIsNone(self.advance(flow, "continue"))
        player.setHp.assert_not_called()
        player.removeItem.assert_not_called()
        player.addItem.assert_not_called()

    def testNativeSessionStatusSurvivesTemporaryPythonWrappers(self):
        state = [""]
        handler = FakeGame().handler
        handler.getSessionSaveStatus = lambda: state[0]
        handler.setSessionSaveStatus = lambda value: state.__setitem__(0, value)

        def resolve():
            game = FakeGame()
            game.handler = handler
            return game

        proxy = ui.UiFlowGame(resolve)
        ui.recordSessionSave(proxy, "native-slot", "save")
        gc.collect()
        self.assertIn("Native slot", ui.sessionSaveStatus(proxy))

    def testNativeModalFailureReturnsToTheGeneratorErrorHandler(self):
        recovered = []

        def prepare():
            try:
                yield ui.uiRequest("gui.showCampaignScreen", "Briefing", "Body", "Continue")
            except RuntimeError as error:
                recovered.append(str(error))
                yield ui.uiRequest("gui.showCampaignScreen", "Error", "Recovery", "Continue")

        callback = Mock(return_value=prepare())
        flow = ui.UiFlow.fromCallback(callback)
        self.addCleanup(flow.close)
        callback.assert_not_called()
        self.assertEqual("Briefing", self.advance(flow)["args"][0])
        request = json.loads(flow.advance("null", "native modal failure"))
        self.assertEqual("Error", request["args"][0])
        self.assertEqual(["native modal failure"], recovered)
        self.assertIsNone(self.advance(flow))
        callback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
