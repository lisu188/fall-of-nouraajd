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

    def testNewAdventureYieldsNativeStartBeforeLoadingEitherMapKind(self):
        from tests.test_ui_frontend import FakeProvider

        for mode, race in (("random", ""), ("scenario", "humanRace")):
            with self.subTest(mode=mode):
                game = FakeGame(current=None)
                game.provider = FakeProvider(maps=["nouraajd"])
                loader = Mock()
                with (
                    patch.dict(sys.modules, {"_game": SimpleNamespace(CGameLoader=loader)}),
                    patch.object(ui.campaign, "list_campaigns", return_value=[]),
                ):
                    flow = ui.newAdventureFlow(game)
                    self.addCleanup(flow.close)
                    self.assertEqual("choose", next(flow)["operation"])
                    request = flow.send(mode)
                    if mode == "scenario":
                        self.assertEqual("Choose a scenario", request["args"][1])
                        request = flow.send("nouraajd")
                    self.assertEqual("chooseCharacter", request["operation"])
                    request = flow.send(("Warrior", race))
                    expected = ["Warrior", race] if mode == "random" else ["nouraajd", "Warrior", race]
                    operation = "gui.startRandomGameWithPlayer" if mode == "random" else "gui.startGameWithPlayer"
                    self.assertEqual(operation, request["operation"])
                    self.assertEqual(expected, list(request["args"]))
                    loader.startGameWithPlayer.assert_not_called()
                    loader.startRandomGameWithPlayer.assert_not_called()
                    game.current = SimpleNamespace(getPlayer=lambda: object())
                    with self.assertRaises(StopIteration) as finished:
                        flow.send(None)
                    self.assertTrue(finished.exception.value)
                self.assertEqual("closed", game.handler.loading[-1])

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

    def testNativeObjectArgumentsRetainIdentityAndTokensAreConsumedPerOperation(self):
        class NativeObject:
            pass

        item = NativeObject()

        def prepare():
            yield ui.uiRequest("gui.showDialog", item, item)
            yield ui.uiRequest("gui.showDialog", item)

        flow = ui.UiFlow.fromCallback(prepare)
        self.addCleanup(flow.close)
        with patch.dict(sys.modules, {"_game": SimpleNamespace(CGameObject=NativeObject)}):
            first = self.advance(flow)
            tokens = [value["__nativeObject"] for value in first["args"]]
            self.assertNotEqual(tokens[0], tokens[1])
            self.assertIs(item, flow.takeObjectArgument(tokens[0]))
            with self.assertRaises(KeyError):
                flow.takeObjectArgument(tokens[0])
            second = self.advance(flow)
            with self.assertRaises(KeyError):
                flow.takeObjectArgument(tokens[1])
            token = second["args"][0]["__nativeObject"]
            self.assertNotIn(token, tokens)
            self.assertIs(item, flow.takeObjectArgument(token))
            self.assertIsNone(self.advance(flow))
        self.assertEqual({}, flow.objectArguments)

    def testObjectArgumentsReleaseOnFailureAndCloseAndRejectFabricatedTokens(self):
        class NativeObject:
            pass

        references = []

        def prepare():
            item = NativeObject()
            references.append(weakref.ref(item))
            try:
                yield ui.uiRequest("gui.showDialog", item)
            finally:
                del item

        with patch.dict(sys.modules, {"_game": SimpleNamespace(CGameObject=NativeObject)}):
            for fail in (False, True):
                flow = ui.UiFlow.fromCallback(prepare)
                self.advance(flow)
                self.assertIsNotNone(references[-1]())
                if fail:
                    with self.assertRaisesRegex(RuntimeError, "modal failed"):
                        flow.advance("null", "modal failed")
                flow.close()
                self.assertIsNone(references[-1]())
                self.assertEqual({}, flow.objectArguments)
            for value in (object(), {"__nativeObject": "object_1"}):
                with self.assertRaises((TypeError, ValueError)):
                    ui.UiFlow.fromCallback(lambda: iter(())).encodeArgument(value)
        with self.assertRaises(TypeError):
            flow.takeObjectArgument(1)
        with self.assertRaises(KeyError):
            flow.takeObjectArgument("fabricated")

    def testResumableHookSharesSynchronousBehaviorAndSuspendsWithoutOwningGame(self):
        class NativeObject:
            pass

        events = []
        game = FakeGame()
        game.handler.showTrade = lambda item: events.append(("shown", item))
        reference = weakref.ref(game)
        item = NativeObject()

        class Receiver:
            getGame = staticmethod(reference)

            @ui.resumableHook
            def onEnter(self, item):
                events.append(("before", item))
                game = ui.flowGame(self.getGame())
                yield ui.uiRequest("gui.showTrade", item)
                events.append(("after", item))
                return 7

        receiver = Receiver()
        self.assertEqual(7, receiver.onEnter(item))
        self.assertEqual([("before", item), ("shown", item), ("after", item)], events)
        events.clear()
        flow = ui.UiFlow.fromCallback(lambda: receiver.onEnterFlow(item))
        with patch.dict(sys.modules, {"_game": SimpleNamespace(CGameObject=NativeObject)}):
            request = self.advance(flow)
        self.assertEqual("showTrade", request["operation"])
        self.assertEqual([("before", item)], events)
        del game
        gc.collect()
        self.assertIsNone(reference())
        self.assertIsNone(self.advance(flow))
        self.assertEqual([("before", item), ("after", item)], events)
        flow.close()


if __name__ == "__main__":
    unittest.main()
