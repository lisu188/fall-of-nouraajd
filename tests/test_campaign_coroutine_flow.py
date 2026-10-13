# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import gc
import types
import unittest
from unittest.mock import patch
import weakref

from tests.test_campaign_driver import DeferredFakeGame, FakePlayer, ScreenFakeGuiHandler, campaign, manifest_fixture
from ui import UiFlowGame


class ActiveContext:
    def __init__(self):
        self.active = True

    def isActive(self):
        return self.active


class AsyncScreenHandler(ScreenFakeGuiHandler):
    def __init__(self):
        super().__init__()
        self.queued_messages = []

    def showCampaignScreen(self, *args):
        raise AssertionError("Native preparation must yield its campaign screen")

    def showMessage(self, text):
        raise AssertionError("Native completion must queue its failure message")

    def showMessageLater(self, text):
        self.queued_messages.append(text)


class FlowGame(DeferredFakeGame):
    def __init__(self, player):
        super().__init__(player)
        self.gui_handler = AsyncScreenHandler()
        self.context = ActiveContext()

    def getContext(self):
        return self.context

    def createWeakResolver(self):
        reference = weakref.ref(self)

        def resolve():
            game = reference()
            if game is None:
                raise RuntimeError("The native game no longer exists")
            return game

        return resolve

    def changeMapWithPreparation(self, *args):
        raise AssertionError("A flow-capable engine must use asynchronous preparation")

    def changeMapWithPreparationFlow(self, map_name, before_entry, completion):
        if not self.accept or self.pending:
            completion(False)
            return False
        self.pending = (map_name, before_entry, completion)
        return True


class CampaignCoroutineFlowTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(campaign, "get_manifest", return_value=manifest_fixture()))

    def begin(self, game_type=FlowGame):
        player = FakePlayer(gold=500, items=("sword", "cursedIdol"))
        game = game_type(player)
        store = campaign.CampaignStateStore(player)
        store.begin("trial", "one")
        self.assertTrue(campaign._beginTransition(game, store, "completed", "mapTwo", "two"))
        return game, player, store

    def assertOriginalState(self, player, store, original_items):
        self.assertEqual("one", store.scenario())
        self.assertEqual([], store.history())
        self.assertEqual(500, player.gold)
        self.assertEqual(original_items, player.getItems())

    def testPreparationYieldsBriefingBeforeCommittingTheMap(self):
        game, player, store = self.begin()
        self.assertEqual("one", store.scenario())
        map_name, before_entry, completion = game.pending
        presentation = before_entry()
        self.addCleanup(presentation.close)
        self.assertIsInstance(presentation, types.GeneratorType)
        self.assertEqual("two", store.scenario())
        self.assertEqual(100, player.gold)
        self.assertEqual([], game.map_changes)
        request = next(presentation)
        self.assertEqual("gui.showCampaignScreen", request["operation"])
        self.assertEqual("Chapter II", request["args"][0])
        self.assertIn("Gold carried: 100", request["args"][1])
        self.assertEqual("Begin chapter", request["args"][2])
        self.assertEqual([], game.gui_handler.screens)
        with self.assertRaises(StopIteration):
            presentation.send(None)
        game.changeMap(map_name)
        completion(True)
        self.assertEqual(["mapTwo"], game.map_changes)
        self.assertEqual([("one", "completed")], store.history())
        self.assertFalse(campaign.hasPendingTransition(game))
        completion(False)
        self.assertEqual("two", store.scenario(), "a completed request cannot roll back a committed chapter")

    def testFailedPreparationRollsBackBeforeQueuingAMessageAndCanRetry(self):
        game, player, store = self.begin()
        original_items = player.getItems()
        _map_name, before_entry, completion = game.pending
        game.pending = None
        presentation = before_entry()
        next(presentation)
        presentation.close()
        player.addGold(50)
        completion(False)
        self.assertOriginalState(player, store, original_items)
        self.assertEqual(1, len(game.gui_handler.queued_messages))
        self.assertTrue(campaign.hasPendingTransition(game))
        self.assertTrue(campaign.retryPending(game))
        map_name, before_entry, completion = game.pending
        presentation = before_entry()
        next(presentation)
        with self.assertRaises(StopIteration):
            presentation.send(None)
        game.changeMap(map_name)
        completion(True)
        self.assertEqual(100, player.gold)
        self.assertEqual(["sword"], player.item_type_ids())
        self.assertEqual([("one", "completed")], store.history())

    def testShutdownCancellationRestoresStateWithoutQueuingPresentation(self):
        game, player, store = self.begin()
        original_items = player.getItems()
        _map_name, before_entry, completion = game.pending
        presentation = before_entry()
        next(presentation)
        game.context.active = False
        presentation.close()
        completion(False)
        self.assertOriginalState(player, store, original_items)
        self.assertEqual([], game.gui_handler.queued_messages)

    def testCallbacksDoNotRetainTheGameAndStillRollBackAfterItsDestruction(self):
        game, player, store = self.begin()
        original_items = player.getItems()
        _map_name, before_entry, completion = game.pending
        presentation = before_entry()
        next(presentation)
        reference = weakref.ref(game)
        del game
        gc.collect()
        self.assertIsNone(reference(), "queued Python callbacks must not keep the native game owner alive")
        presentation.close()
        completion(False)
        self.assertOriginalState(player, store, original_items)

    def testDuplicateProxyRequestsDoNotDependOnGameHashing(self):
        game, _player, _store = self.begin()
        proxy = UiFlowGame(game.createWeakResolver())
        with patch.object(UiFlowGame, "__hash__", side_effect=AssertionError("Game proxy hashing is unsafe")):
            self.assertFalse(campaign.retryPending(proxy))
        _map_name, _before_entry, completion = game.pending
        completion(False)

    def testRejectedFlowRequestReleasesItsGuardAndPreservesRetry(self):
        game, player, store = self.begin()
        original_items = player.getItems()
        _map_name, _before_entry, completion = game.pending
        game.pending = None
        completion(False)
        game.gui_handler.queued_messages.clear()
        game.accept = False
        self.assertFalse(campaign.retryPending(game))
        self.assertOriginalState(player, store, original_items)
        self.assertEqual(1, len(game.gui_handler.queued_messages))
        self.assertTrue(campaign.hasPendingTransition(game))
        game.accept = True
        self.assertTrue(campaign.retryPending(game))
        _map_name, _before_entry, completion = game.pending
        completion(False)

    def testLegacyPreparationStillDrivesTheSameBriefingSynchronously(self):
        game, player, store = self.begin(DeferredFakeGame)
        game.gui_handler = ScreenFakeGuiHandler()
        game.finishTransition()
        self.assertEqual("two", store.scenario())
        self.assertEqual(100, player.gold)
        self.assertEqual(["sword"], player.item_type_ids())
        self.assertEqual("Chapter II", game.gui_handler.screens[0][0])
        self.assertFalse(campaign.hasPendingTransition(game))


if __name__ == "__main__":
    unittest.main()
