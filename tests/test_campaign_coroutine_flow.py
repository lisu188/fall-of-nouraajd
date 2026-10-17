# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import gc
import json
import types
import unittest
from unittest.mock import patch
import weakref

from tests.test_campaign_driver import DeferredFakeGame, FakePlayer, ScreenFakeGuiHandler, campaign, manifest_fixture
from ui import UiFlowGame
import ui


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

    def changeMapWithPreparationFlow(self, map_name, before_entry, completion, commit_before_entry=None):
        if not self.accept or self.pending:
            completion(False)
            return False
        self.pending = (map_name, before_entry, completion)
        self.commit_before_entry = commit_before_entry
        return True


class AsyncGame(DeferredFakeGame):
    def __init__(self, player):
        super().__init__(player)
        self.gui_handler = ScreenFakeGuiHandler()
        self.gui_handler.showMessageLater = self.gui_handler.showMessage
        self.entry_requests = []

    def changeMapWithPreparationFlow(self, map_name, before_entry, completion, commit_before_entry=None):
        self.commit_before_entry = commit_before_entry
        return self.changeMapWithPreparation(map_name, before_entry, completion)

    def finishTransition(self, success=True):
        map_name, before_entry, completion = self.pending
        self.pending = None
        if success:
            flow = before_entry()
            if flow is not None:
                self.entry_requests.extend(flow)
            if self.commit_before_entry is not None:
                self.commit_before_entry()
            self.changeMap(map_name)
        completion(success)


def reloadPlayer(player):
    saved = json.loads(
        json.dumps(
            {
                "gold": player.gold,
                "items": player.item_type_ids(),
                "strings": player.string_properties,
                "bools": player.bool_properties,
            }
        )
    )
    restored = FakePlayer(saved["gold"], saved["items"])
    restored.string_properties.update(saved["strings"])
    restored.bool_properties.update(saved["bools"])
    return restored


class CampaignCoroutineFlowTest(unittest.TestCase):
    def setUp(self):
        self.manifest = manifest_fixture()
        self.manifest["scenarios"]["one"]["next"].update(good_ending="two", bad_ending="two")
        self.enterContext(patch.object(campaign, "get_manifest", return_value=self.manifest))

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

    def testCampaignStartAwaitsNativePlayerAttachmentBeforeInitializingAndPresenting(self):
        from tests.test_campaign_driver import FakeMap

        for race in ("", "testRace"):
            with self.subTest(race=race):
                game = FlowGame(FakePlayer())
                flow = campaign.startFlow(game, "trial", "Warrior", race)
                self.addCleanup(flow.close)
                request = next(flow)
                self.assertEqual("gui.startGameWithPlayer", request["operation"])
                self.assertEqual(("mapOne", "Warrior", race), request["args"])
                self.assertFalse(campaign.state(game).active())
                attached_player = FakePlayer()
                game.map = FakeMap(attached_player)
                briefing = flow.send(None)
                self.assertEqual("campaign._show_screen", briefing["operation"])
                self.assertEqual("Chapter I", briefing["args"][1])
                self.assertEqual("trial", campaign.state(game).campaign_id())
                self.assertEqual("one", campaign.state(game).scenario())
                with self.assertRaises(StopIteration) as stopped:
                    flow.send(None)
                self.assertIs(attached_player, stopped.exception.value.player)

    def testPreparationYieldsBriefingBeforeCommittingTheMap(self):
        game, player, store = self.begin()
        self.assertEqual("one", store.scenario())
        map_name, before_entry, completion = game.pending
        presentation = before_entry()
        self.addCleanup(presentation.close)
        self.assertIsInstance(presentation, types.GeneratorType)
        self.assertEqual("one", store.scenario())
        self.assertEqual(500, player.gold)
        self.assertEqual([], game.map_changes)
        request = next(presentation)
        self.assertEqual("gui.showCampaignScreen", request["operation"])
        self.assertEqual("Chapter II", request["args"][0])
        self.assertIn("Gold carried: 100", request["args"][1])
        self.assertEqual("Begin chapter", request["args"][2])
        self.assertEqual([], game.gui_handler.screens)
        self.assertEqual("one", store.scenario(), "a save during the briefing must retain its source chapter")
        self.assertTrue(campaign.hasPendingTransition(game))
        with self.assertRaises(StopIteration):
            presentation.send(None)
        self.assertEqual("one", store.scenario())
        self.assertEqual(500, player.gold)
        game.commit_before_entry()
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
        game.commit_before_entry()
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

    def session(self, scenario="one"):
        self.manifest["scenarios"]["two"]["carryover"] = {}
        player = FakePlayer(500, ("sword",))
        campaign.CampaignStateStore(player).begin("trial", scenario)
        return AsyncGame(player), player

    def testOutcomeIsSavedBeforeItsFirstModalAndNeverCallsASynchronousScreen(self):
        game, player = self.session()
        flow = campaign.complete_scenarioFlow(game, "completed", outcome_summary="Rewards received\nGold: +200")
        self.addCleanup(flow.close)
        request = next(flow)
        self.assertEqual("gui.showCampaignScreen", request["operation"])
        self.assertIn("Gold: +200", request["args"][1])
        self.assertEqual([], game.gui_handler.screens)
        self.assertEqual([], game.gui_handler.messages)
        pending = json.loads(player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
        self.assertEqual("outcome", pending["stage"])
        self.assertEqual("mapTwo", pending["targetMap"])
        self.assertEqual([], campaign.state(game).history())
        self.assertIsNone(game.pending)

    def testCancelledOutcomeResumesFromSavedIntentAndCommitsHistoryOnce(self):
        game, player = self.session()
        flow = campaign.complete_scenarioFlow(game, "completed")
        next(flow)
        restored = reloadPlayer(player)
        flow.close()
        reloaded = AsyncGame(restored)
        retry = campaign.retryPendingFlow(reloaded)
        self.assertEqual("gui.showCampaignScreen", next(retry)["operation"])
        with self.assertRaises(StopIteration) as result:
            retry.send(None)
        self.assertTrue(result.exception.value)
        self.assertEqual([], campaign.state(reloaded).history())
        reloaded.finishTransition()
        self.assertEqual([("one", "completed")], campaign.state(reloaded).history())
        self.assertEqual("two", campaign.state(reloaded).scenario())
        self.assertEqual(500, restored.gold)
        self.assertFalse(campaign.hasPendingTransition(reloaded))
        self.assertEqual("gui.showCampaignScreen", reloaded.entry_requests[0]["operation"])
        self.assertFalse(campaign.retryPending(reloaded))

    def testTerminalAcknowledgmentCanBeReloadedWithoutRepeatingHistoryOrCompletion(self):
        game, player = self.session("two")
        flow = campaign.complete_scenarioFlow(game, "completed")
        self.assertEqual("Chapter II", next(flow)["args"][0])
        self.assertEqual("Trial Campaign", flow.send(None)["args"][0])
        self.assertTrue(campaign.state(game).finished())
        self.assertTrue(campaign.hasPendingTransition(game))
        self.assertEqual([("two", "completed")], campaign.state(game).history())
        restored = reloadPlayer(player)
        flow.close()
        reloaded = AsyncGame(restored)
        retry = campaign.retryPendingFlow(reloaded)
        self.assertEqual("Trial Campaign", next(retry)["args"][0])
        retry.close()
        self.assertEqual([("two", "completed")], campaign.state(reloaded).history())
        retry = campaign.retryPendingFlow(reloaded)
        next(retry)
        with self.assertRaises(StopIteration):
            retry.send(None)
        self.assertTrue(campaign.state(reloaded).finished())
        self.assertFalse(campaign.hasPendingTransition(reloaded))
        self.assertIsNone(campaign.complete_scenario(reloaded, "completed"))
        self.assertEqual([("two", "completed")], campaign.state(reloaded).history())

    def testConcurrentOutcomeReadersShareThePresentationAndCancellationReleasesIt(self):
        game, _player = self.session("two")
        first = campaign.complete_scenarioFlow(game, "completed")
        next(first)
        second = campaign.complete_scenarioFlow(game, "completed")
        with self.assertRaises(StopIteration):
            next(second)
        self.assertEqual([], campaign.state(game).history())
        first.close()
        retried = campaign.retryPendingFlow(game)
        self.addCleanup(retried.close)
        self.assertEqual("Chapter II", next(retried)["args"][0])

    def testLegacyPendingDocumentsStillRetryAndForeignChapterIntentsCannotAdvance(self):
        game, player = self.session()
        pending = campaign.prepareCompletion(game, "completed")
        pending.pop("stage")
        pending.pop("outcomeSummary")
        player.setStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY, json.dumps(pending))
        self.assertTrue(campaign.retryPending(game))
        self.assertEqual([], game.gui_handler.screens)
        game.finishTransition()
        self.assertEqual([("one", "completed")], campaign.state(game).history())
        player.setStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY, json.dumps(pending))
        self.assertFalse(campaign.hasPendingTransition(game))
        self.assertFalse(campaign.retryPending(game))
        self.assertEqual(["mapTwo"], game.map_changes)

    def testInvalidCompletionRouteCannotFinishAnEarlierChapter(self):
        game, player = self.session()
        pending = campaign.prepareCompletion(game, "completed")
        pending.update(targetMap="", targetScenario="")
        player.setStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY, json.dumps(pending))
        flow = campaign.retryPendingFlow(game)
        with self.assertRaisesRegex(campaign.CampaignError, "campaign route"):
            next(flow)
        self.assertFalse(campaign.state(game).finished())
        self.assertEqual([], campaign.state(game).history())
        self.assertEqual([], game.gui_handler.screens)

    def testSuspendedOutcomeDoesNotOwnTheGame(self):
        game, _player = self.session()
        reference = weakref.ref(game)
        flow = campaign.complete_scenarioFlow(game, "completed")
        next(flow)
        del game
        gc.collect()
        self.assertIsNone(reference())
        flow.close()

    def testRitualRewardCancellationPersistsTheBranchAndNeverPaysAgainAfterReload(self):
        self.manifest["scenarios"]["two"]["carryover"] = {}
        from tests import test_narrative_consequences as fixture

        install = fixture.installHookFlows

        def installWithReceipt(api):
            install(api)

            def receipt(*_args, **_kwargs):
                yield ui.uiRequest("gui.showMessage", "Authored reward receipt")

            api.showRewardReceiptFlow = receipt

        for good in (True, False):
            with self.subTest(good=good), patch.object(fixture, "installHookFlows", installWithReceipt):
                classes = fixture.loadMapClasses("ritual")
                game = fixture.Game()
                game.map.properties.update(anchors_destroyed=True, leader_defeated=True, captive_lost=not good)
                campaign.CampaignStateStore(game.player).begin("trial", "one")
                action = classes["CapturedSoulDialog"](game)
                flow = action.free_captiveFlow() if good else action.continueAfterLossFlow()
                self.addCleanup(flow.close)
                self.assertEqual("gui.showMessage", next(flow)["operation"])
                pending = json.loads(game.player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
                self.assertEqual("good_ending" if good else "bad_ending", pending["outcome"])
                saved = json.loads(
                    json.dumps(
                        {
                            "player": game.player.properties,
                            "map": game.map.properties,
                            "gold": game.player.gold,
                            "items": game.player.items,
                        }
                    )
                )
                flow.close()
                reloaded = fixture.Game()
                reloaded.player.properties.update(saved["player"])
                reloaded.map.properties.update(saved["map"])
                reloaded.player.gold = saved["gold"]
                reloaded.player.items[:] = saved["items"]
                retry = campaign.retryPendingFlow(reloaded)
                self.assertEqual("gui.checkQuests", next(retry)["operation"])
                self.assertEqual("gui.showMessage", retry.send(None)["operation"])
                with self.assertRaises(StopIteration):
                    retry.send(None)
                reloaded.finishTransition(True)
                self.assertEqual(300 if good else 100, reloaded.player.gold)
                self.assertEqual(["LifePotion"] if good else [], reloaded.player.items)
                self.assertEqual([("one", pending["outcome"])], campaign.state(reloaded).history())
                self.assertFalse(campaign.hasPendingTransition(reloaded))

    def testCastleTurnRecoversFinalCaptureWithoutRepeatingItsGold(self):
        from tests.test_castle_campaign import CastlePresentationTest, loadCastleModule

        fixture = CastlePresentationTest()
        fixture.castle = loadCastleModule()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.mission.update(objectiveIds=["tower1"], defenderIds=["tower1Guard"], enemyHeroIds=[])
        fixture.game_map.objects["castleMission"].setStringProperty("campaign_mission", json.dumps(fixture.mission))
        fixture.game_map.setBoolProperty(fixture.castle.defeatedFlag("tower1Guard"), True)
        marker = fixture.game_map.objects["tower1"]
        receipt = fixture.game_stub.showRewardReceiptFlow

        def suspendedReceipt(*_args, **_kwargs):
            yield ui.uiRequest("gui.showMessage", "Captured objective receipt")

        fixture.game_stub.showRewardReceiptFlow = suspendedReceipt
        flow = fixture.castle.captureObjectiveFlow(marker, fixture.player)
        self.addCleanup(flow.close)
        self.assertEqual("gui.showMessage", next(flow)["operation"])
        saved = json.loads(
            json.dumps(
                {"map": fixture.game_map.properties, "player": fixture.player.properties, "gold": fixture.player.gold}
            )
        )
        flow.close()
        self.assertFalse(saved["map"].get("campaign_castleFinished_griffinCliff", False))
        fixture.game_map.properties.update(saved["map"])
        fixture.player.properties.update(saved["player"])
        fixture.player.gold = saved["gold"]
        fixture.game_stub.showRewardReceiptFlow = receipt
        restored = CastlePresentationTest()
        restored.castle = fixture.castle
        restored.setUp()
        self.addCleanup(restored.doCleanups)
        restored.mission.update(fixture.mission)
        restored.game_map.objects["castleMission"].setStringProperty("campaign_mission", json.dumps(restored.mission))
        restored.game_map.properties.update(saved["map"])
        restored.player.properties.update(saved["player"])
        restored.player.gold = saved["gold"]
        mission = restored.registry["CastleMissionStart"]("castleMission", restored.game_map)
        mission.setBoolProperty("campaign_castleInitialized", True)
        mission.onTurn(None)
        self.assertEqual(saved["gold"] + restored.mission["victoryGold"], restored.player.gold)
        self.assertEqual(1, len(restored.routes))
        mission.onTurn(None)
        self.assertEqual(saved["gold"] + restored.mission["victoryGold"], restored.player.gold)
        self.assertEqual(1, len(restored.routes))

    def testOutcomeCannotRouteAReplacementMapPlayerOrCampaign(self):
        from tests.test_campaign_driver import FakeMap

        for replacement in ("player", "map", "campaign", "pending", "generation", "inactive"):
            with self.subTest(replacement=replacement):
                game, player = self.session()
                context = ActiveContext()
                context.generation = 1
                context.captureTransitionGeneration = lambda: context.generation
                context.isTransitionGenerationCurrent = lambda expected: expected == context.generation
                game.getContext = lambda: context
                flow = campaign.complete_scenarioFlow(game, "completed")
                next(flow)
                old_pending = player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY)
                other = FakePlayer(800)
                campaign.CampaignStateStore(other).begin("replacement", "other")
                if replacement == "player":
                    game.map = FakeMap(other)
                elif replacement == "map":
                    game.map = FakeMap(player)
                elif replacement == "campaign":
                    campaign.state(game).begin("replacement", "other")
                elif replacement == "pending":
                    player.setStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY, "replacement payload")
                elif replacement == "generation":
                    context.generation += 1
                else:
                    context.active = False
                with self.assertRaises(StopIteration):
                    flow.send(None)
                self.assertEqual([], game.map_changes)
                self.assertEqual(800, other.gold)
                self.assertEqual([], campaign.CampaignStateStore(other).history())
                self.assertEqual([], campaign.CampaignStateStore(player).history())
                if replacement != "pending":
                    self.assertEqual(old_pending, player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))

    def testTerminalScreenCannotClearAReplacedOwnersPendingIntent(self):
        from tests.test_campaign_driver import FakeMap

        game, player = self.session("two")
        flow = campaign.complete_scenarioFlow(game, "completed")
        next(flow)
        flow.send(None)
        pending = player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY)
        replacement = FakePlayer(800)
        game.map = FakeMap(replacement)
        with self.assertRaises(StopIteration):
            flow.send(None)
        self.assertEqual(pending, player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
        self.assertEqual("", replacement.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
        self.assertEqual([("two", "completed")], campaign.CampaignStateStore(player).history())

    def testRetryLeaseBeginsBeforeItsQuestBarrier(self):
        game, player = self.session()
        player.checkQuests = lambda: None
        campaign.prepareCompletion(game, "completed")
        first, second = campaign.retryPendingFlow(game), campaign.retryPendingFlow(game)
        self.addCleanup(first.close)
        self.assertEqual("gui.checkQuests", next(first)["operation"])
        with self.assertRaises(StopIteration) as stopped:
            next(second)
        self.assertFalse(stopped.exception.value)
        self.assertEqual("gui.showCampaignScreen", first.send(None)["operation"])
        first.close()
        retried = campaign.retryPendingFlow(game)
        self.addCleanup(retried.close)
        self.assertEqual("gui.checkQuests", next(retried)["operation"])

    def testPreparedStandaloneFallbackAwaitsQuestsButLegacyPendingDoesNot(self):
        player = FakePlayer(500)
        calls = []
        player.checkQuests = lambda: calls.append("checked")
        game = AsyncGame(player)
        pending = campaign.prepareCompletion(game, "completed", fallback_map="legacy")
        self.assertEqual("authored", pending["stage"])
        flow = campaign.retryPendingFlow(game)
        self.assertEqual("gui.checkQuests", next(flow)["operation"])
        self.assertIsNone(game.pending)
        player.checkQuests()
        with self.assertRaises(StopIteration):
            flow.send(None)
        game.finishTransition()
        self.assertEqual(["checked"], calls)
        self.assertEqual(["legacy"], game.map_changes)
        pending.pop("stage")
        player.setStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY, json.dumps(pending))
        flow = campaign.retryPendingFlow(game)
        with self.assertRaises(StopIteration):
            next(flow)
        self.assertEqual(["checked"], calls)
        game.finishTransition()

    def testCommittedTerminalOutcomeRepairsItsStageWithoutDuplicatingHistory(self):
        game, _player = self.session("two")
        campaign.prepareCompletion(game, "completed")
        store = campaign.state(game)
        store.record_outcome("two", "completed")
        store.finish()
        flow = campaign.complete_scenarioFlow(game, "completed")
        self.assertEqual("Trial Campaign", next(flow)["args"][0])
        self.assertEqual([("two", "completed")], store.history())
        with self.assertRaises(StopIteration):
            flow.send(None)
        self.assertFalse(campaign.hasPendingTransition(game))
        self.assertEqual([("two", "completed")], store.history())

    def testSaveDuringBriefingRetainsTheSourceUntilAtomicNativeCommit(self):
        game, player, store = self.begin()
        map_name, before_entry, completion = game.pending
        briefing = before_entry()
        next(briefing)
        restored = reloadPlayer(player)
        self.assertEqual("one", store.scenario())
        self.assertEqual(500, player.gold)
        self.assertEqual(["cursedIdol", "sword"], player.item_type_ids())
        self.assertTrue(campaign.hasPendingTransition(game))
        briefing.close()
        completion(False)
        reloaded = FlowGame(restored)
        self.assertTrue(campaign.retryPending(reloaded))
        target, before_entry, completion = reloaded.pending
        briefing = before_entry()
        next(briefing)
        with self.assertRaises(StopIteration):
            briefing.send(None)
        self.assertEqual("one", campaign.state(reloaded).scenario(), "posted native parents have not committed yet")
        self.assertTrue(campaign.hasPendingTransition(reloaded))
        reloaded.commit_before_entry()
        reloaded.changeMap(target)
        completion(True)
        self.assertEqual("two", campaign.state(reloaded).scenario())
        self.assertEqual(100, restored.gold)
        self.assertEqual(["sword"], restored.item_type_ids())
        self.assertEqual([("one", "completed")], campaign.state(reloaded).history())
        self.assertFalse(campaign.hasPendingTransition(reloaded))

    def testQueuedPreparationRejectsAReplacementSourceBeforeCarryover(self):
        from tests.test_campaign_driver import FakeMap

        game, old, store = self.begin()
        _target, before_entry, completion = game.pending
        replacement = FakePlayer(800)
        campaign.CampaignStateStore(replacement).begin("replacement", "other")
        game.map = FakeMap(replacement)
        with self.assertRaisesRegex(campaign.CampaignError, "source adventure changed"):
            before_entry()
        completion(False)
        self.assertEqual(800, replacement.gold)
        self.assertEqual("other", campaign.state(game).scenario())
        self.assertEqual(500, old.gold)
        self.assertEqual("one", store.scenario())
        self.assertTrue(old.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))

    def testSaveDuringDestinationEntryFinalizesWithoutReplayingTheTransition(self):
        from tests.test_campaign_driver import FakeMap

        game, player, store = self.begin()
        game.map.getMapName = lambda: "mapOne"
        # A newly prepared source records its map so destination saves validate ownership.
        pending = json.loads(player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
        pending["sourceMap"] = "mapOne"
        player.setStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY, json.dumps(pending, sort_keys=True))
        game.pending[2](False)
        game.pending = None
        self.assertTrue(campaign.retryPending(game))
        target, before_entry, completion = game.pending
        briefing = before_entry()
        next(briefing)
        with self.assertRaises(StopIteration):
            briefing.send(None)
        game.commit_before_entry()
        game.changeMap(target)
        game.map = FakeMap(player)
        game.map.getMapName = lambda: "mapTwo"
        saved = reloadPlayer(player)
        saved_pending = json.loads(saved.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
        self.assertEqual("entry", saved_pending["stage"])
        self.assertEqual("two", saved_pending["scenario"])
        self.assertEqual("one", saved_pending["sourceScenario"])
        self.assertEqual("mapTwo", saved_pending["sourceMap"])
        completion(False)
        self.assertEqual("two", store.scenario(), "an attached destination is already committed")
        reloaded = FlowGame(saved)
        reloaded.map.getMapName = lambda: "mapTwo"
        saved.checkQuests = lambda: None
        retry = campaign.retryPendingFlow(reloaded)
        self.assertEqual("gui.checkQuests", next(retry)["operation"])
        with self.assertRaises(StopIteration) as stopped:
            retry.send(None)
        self.assertTrue(stopped.exception.value)
        self.assertIsNone(reloaded.pending)
        self.assertEqual([], reloaded.map_changes)
        self.assertEqual([], reloaded.gui_handler.screens)
        self.assertEqual(100, saved.gold)
        self.assertEqual(["sword"], saved.item_type_ids())
        self.assertEqual([("one", "completed")], campaign.state(reloaded).history())
        self.assertFalse(campaign.hasPendingTransition(reloaded))
        self.assertFalse(campaign.retryPending(reloaded))

    def testStaleBriefingCannotRollBackAPlayerTransferredToAnotherActiveMap(self):
        from tests.test_campaign_driver import FakeMap

        game, player, store = self.begin()
        _target, before_entry, completion = game.pending
        briefing = before_entry()
        next(briefing)
        game.map = FakeMap(player)
        player.addGold(300)
        with self.assertRaisesRegex(campaign.CampaignError, "source adventure changed"):
            briefing.send(None)
        completion(False)
        self.assertEqual(800, player.gold)
        self.assertEqual("one", store.scenario())
        self.assertEqual([], store.history())
        self.assertEqual([], game.gui_handler.queued_messages)

    def testSavedSourceMapMetadataRejectsAForeignAdventureWithTheSamePlayer(self):
        from tests.test_campaign_driver import FakeMap

        game, player = self.session()
        game.map.getMapName = lambda: "mapOne"
        campaign.prepareCompletion(game, "completed")
        pending = player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY)
        replacement = FakeMap(player)
        replacement.getMapName = lambda: "unrelatedMap"
        game.map = replacement
        self.assertFalse(campaign.hasPendingTransition(game))
        self.assertFalse(campaign.retryPending(game))
        self.assertEqual(pending, player.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
        self.assertEqual([], game.map_changes)

    def testCommittedEntryCanAcceptTheDestinationOutcomeDuringItsQuestBarrier(self):
        for during_retry in (False, True):
            with self.subTest(during_retry=during_retry):
                game, player, store = self.begin()
                target, prepare, _completion = game.pending
                list(prepare())
                game.commit_before_entry()
                game.changeMap(target)
                restored = reloadPlayer(player)
                reloaded = FlowGame(restored)
                outcome = []

                def completeDestination():
                    flow = campaign.complete_scenarioFlow(reloaded, "completed")
                    outcome.append(flow)
                    self.assertEqual("Chapter II", next(flow)["args"][0])

                if during_retry:
                    restored.checkQuests = completeDestination
                    retry = campaign.retryPendingFlow(reloaded)
                    self.assertEqual("gui.checkQuests", next(retry)["operation"])
                    restored.checkQuests()
                    with self.assertRaises(StopIteration):
                        retry.send(None)
                else:
                    completeDestination()
                self.addCleanup(outcome[0].close)
                pending = json.loads(restored.getStringProperty(campaign.CAMPAIGN_PENDING_PROPERTY))
                self.assertEqual("outcome", pending["stage"])
                self.assertEqual("two", pending["scenario"])
                self.assertEqual("", pending["targetScenario"])
                self.assertEqual([("one", "completed")], campaign.state(reloaded).history())
                self.assertEqual("Trial Campaign", outcome[0].send(None)["args"][0])
                with self.assertRaises(StopIteration):
                    outcome[0].send(None)
                self.assertEqual([("one", "completed"), ("two", "completed")], campaign.state(reloaded).history())


if __name__ == "__main__":
    unittest.main()
