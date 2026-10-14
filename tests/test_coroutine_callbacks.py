# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import builtins
import gc
import importlib
from importlib.machinery import EXTENSION_SUFFIXES
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

ROOT = Path(__file__).resolve().parents[1]


class NativeCoroutineCallbackTest(unittest.TestCase):
    requireCurrentNativeBinary = False

    def setUp(self):
        self.enterContext(
            patch.dict(
                os.environ,
                SDL_VIDEODRIVER="dummy",
                SDL_AUDIODRIVER="dummy",
                SDL_RENDER_DRIVER="software",
                LIBGL_ALWAYS_SOFTWARE="1",
            )
        )
        explicit = os.environ.get("GAME_BUILD_DIR")
        if explicit:
            build = (ROOT / explicit).resolve()
        else:
            preferred = "cmake-build-clangcl20-release" if os.name == "nt" else "cmake-build-gcc15-release"
            build = next(
                (
                    ROOT / name
                    for name in (
                        preferred,
                        preferred.replace("-release", "-debug"),
                        "cmake-build-release",
                        "cmake-build-debug",
                    )
                    if (ROOT / name).is_dir()
                ),
                ROOT / preferred,
            )
        config = os.environ.get("GAME_BUILD_CONFIG")
        candidates = (
            [build / config, build]
            if config
            else [build, *(build / name for name in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"))]
        )
        binaries = [path / ("_game" + suffix) for path in candidates for suffix in EXTENSION_SUFFIXES]
        if not any(path.is_file() for path in binaries):
            if self.requireCurrentNativeBinary:
                self.fail(f"Required current native coroutine callback binary is missing from {build}")
            self.skipTest(f"No current compiled _game binary for native coroutine callback tests in {build}")
        import test as harness

        self.api = harness.load_game_module()
        self.native = importlib.import_module("_game")
        self.assertIn(Path(self.native.__file__).resolve(), [path.resolve() for path in binaries])
        if not callable(getattr(self.api.CGame, "runUiFlowLater", None)):
            if self.requireCurrentNativeBinary:
                self.fail("The selected _game binary lacks the current runUiFlowLater binding")
            self.skipTest("The local compiled _game binary predates the current coroutine callback API")
        self.ui = importlib.import_module("ui")
        self.loop = self.api.event_loop.instance()
        self.assertTrue(self.loop.isMainThread(), "Native callbacks must run on the engine owner thread")
        self.games = []
        self.flow_refs = []
        self.addCleanup(self.cleanupSessions)
        original = self.ui.UiFlow.fromCallback

        def recordFlow(callback):
            flow = original(callback)
            self.flow_refs.append(weakref.ref(flow))
            return flow

        self.enterContext(patch.object(self.ui.UiFlow, "fromCallback", new=staticmethod(recordFlow)))
        self.game = self.newGame(gui=True)
        self.gui = self.game.getGui()
        self.player = self.game.getMap().getPlayer()

    def newGame(self, *, gui=False):
        owner = self.api.CGameLoader.loadGame()
        self.games.append(owner)
        self.api.CGameLoader.startGameWithPlayer(owner, "empty", "Warrior")
        if gui:
            self.api.CGameLoader.loadGui(owner)
            self.assertIsNotNone(owner.getGui())
        return owner

    def cleanupSessions(self):
        for owner in reversed(self.games):
            owner.getContext().shutdown()
        for _ in range(8):
            self.loop.run()
        self.games.clear()
        gc.collect()

    def pumpUntil(self, ready, message):
        deadline = time.monotonic() + 5
        for _ in range(512):
            if ready():
                return
            self.loop.run()
            if time.monotonic() >= deadline:
                break
            time.sleep(0.001)
        self.assertTrue(ready(), message)

    def settle(self):
        for _ in range(8):
            self.loop.run()
        gc.collect()

    def panel(self, type_name):
        return next((child for child in self.gui.getChildren() if child.getType() == type_name), None)

    def awaitPanel(self, type_name):
        self.pumpUntil(lambda: self.panel(type_name) is not None, "Native flow did not open " + type_name)
        return self.panel(type_name)

    def assertFlowsReleased(self):
        self.settle()
        self.assertTrue(self.flow_refs, "The test must drive a real native-owned UiFlow")
        self.assertTrue(all(reference() is None for reference in self.flow_refs), "Completed native flow owners leaked")

    def makeState(self, identity, text, options=()):
        state = self.game.createObject("CDialogState")
        state.setStringProperty("stateId", identity)
        state.setStringProperty("text", text)
        state.setOptions(set(options))
        return state

    def makeOption(self, *, action="", next_state="EXIT", condition=""):
        option = self.game.createObject("CDialogOption")
        option.setNumericProperty("number", 0)
        option.setStringProperty("text", "Continue")
        option.setStringProperty("action", action)
        option.setStringProperty("condition", condition)
        option.setStringProperty("nextStateId", next_state)
        return option

    def makeDialog(self, dialog=None, *, action="", next_state="EXIT", condition=""):
        dialog = dialog or self.game.createObject("CDialog")
        option = self.makeOption(action=action, next_state=next_state, condition=condition)
        dialog.setStates(
            {
                self.makeState("ENTRY", "Original entry", [option]),
                self.makeState("AFTER", "Action completed", [self.makeOption()]),
            }
        )
        return dialog, option

    def openDialogLater(self, dialog, events):
        ui = self.ui

        def callback():
            try:
                events.append("outer started")
                yield ui.uiRequest("gui.showDialog", dialog)
                events.append("outer returned")
            finally:
                events.append("outer closed")

        self.game.runUiFlowLater(callback)
        return self.awaitPanel("CGameDialogPanel")

    def testNativeFailingTransitionCommitReleasesItsCapturedSecondSessionBeforeAnotherSpawn(self):
        owner = self.newGame()
        source = owner.getMap()
        source_player = source.getPlayer()
        source_coords = source_player.getCoords()
        source_scope = owner.getResourcesProvider().getActiveScope()
        second = self.newGame()
        self.assertIs(second, self.games.pop())
        second_context = second.getContext()
        second_reference = weakref.ref(second)
        resolve_second = second.createWeakResolver()
        events = []

        def prepare():
            events.append("prepared")

        def commit(retained=second):
            self.assertTrue(retained.getContext().isActive())
            events.append("commit failed")
            raise RuntimeError("native transition commit lifetime sentinel")

        accepted = owner.changeMapWithPreparationFlow(
            "test", prepare, lambda success: events.append(("completed", success)), commit
        )
        self.assertTrue(accepted)
        del second, prepare, commit
        self.assertIsNotNone(second_reference(), "The queued commit must own its Python captures before execution")
        self.pumpUntil(lambda: ("completed", False) in events, "The failing commit did not reject its transition")
        self.assertEqual(["prepared", "commit failed", ("completed", False)], events)
        self.assertIs(owner.getMap(), source)
        self.assertIs(source.getPlayer(), source_player)
        self.assertEqual(source_coords, source_player.getCoords())
        self.assertEqual(source_scope, owner.getResourcesProvider().getActiveScope())
        self.assertFalse(owner.getSceneManager().isTransitionPending())
        # Pump completion continuations without spawning work that could prune the owner's finished tasks.
        self.pumpUntil(
            lambda: second_reference() is None,
            "The detached transition retained its Python exception frame until an unrelated task was spawned",
        )
        gc.collect()
        self.assertFalse(second_context.isActive(), "Releasing the captured second game must finish its teardown")
        with self.assertRaises(RuntimeError):
            resolve_second()
        self.assertTrue(owner.getContext().isActive())
        self.assertFlowsReleased()

    def testNativeDialogTokenKeepsExactObjectAcrossItsPanelAndReleasesTheFlowRegistry(self):
        dialog, _ = self.makeDialog()
        events = []
        panel = self.openDialogLater(dialog, events)
        self.assertIs(panel.getObjectProperty("dialog"), dialog)
        self.assertEqual(["outer started"], events)
        self.assertEqual({}, self.flow_refs[0]().objectArguments)
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.pumpUntil(lambda: "outer closed" in events, "Dialog close did not resume its native flow")
        self.assertEqual(["outer started", "outer returned", "outer closed"], events)
        self.assertIsNone(self.panel("CGameDialogPanel"))
        self.assertFlowsReleased()

    def testNativeWrongSubclassAndForeignGameTokensReinjectErrorsAndReleaseArguments(self):
        foreign = self.newGame()
        wrong_type = self.game.createObject("LesserLifePotion")
        foreign_dialog = foreign.createObject("CDialog")
        for argument, expected in ((wrong_type, "CDialog"), (foreign_dialog, "game session")):
            with self.subTest(expected=expected):
                errors, events = [], []
                ui = self.ui

                def callback():
                    try:
                        yield ui.uiRequest("gui.showDialog", argument)
                        events.append("unexpected success")
                    except RuntimeError as error:
                        errors.append(str(error))
                    finally:
                        events.append("closed")

                self.game.runUiFlowLater(callback)
                self.pumpUntil(lambda: events, "Invalid native token did not return an error to Python")
                self.assertEqual(["closed"], events)
                self.assertEqual(1, len(errors))
                self.assertIn(expected, errors[0])
                self.assertIsNone(self.panel("CGameDialogPanel"))
                self.assertFlowsReleased()

    def testNativeMissingAndStaleTokensReinjectErrorsWithoutRetainingUntakenObjects(self):
        for stale in (False, True):
            with self.subTest(stale=stale):
                dialog, _ = self.makeDialog()
                errors, events, tokens = [], [], []
                ui = self.ui
                original_advance = ui.UiFlow.advance

                def advance(flow, answer, failure=None):
                    result = original_advance(flow, answer, failure)
                    if result is not None:
                        request = json.loads(result)
                        if request["operation"] == "showDialog":
                            tokens.append(request["args"][0]["__nativeObject"])
                            if not stale or len(tokens) == 2:
                                request["args"][0]["__nativeObject"] = tokens[0] if stale else "missing_token"
                            result = json.dumps(request)
                    return result

                def callback():
                    try:
                        if stale:
                            yield ui.uiRequest("gui.showDialog", dialog)
                        yield ui.uiRequest("gui.showDialog", dialog)
                        events.append("unexpected success")
                    except RuntimeError as error:
                        errors.append(str(error))
                    finally:
                        events.append("closed")

                with patch.object(ui.UiFlow, "advance", new=advance):
                    self.game.runUiFlowLater(callback)
                    if stale:
                        self.awaitPanel("CGameDialogPanel").close()
                    self.pumpUntil(lambda: events, "Missing/stale native token did not settle its Python flow")
                self.assertEqual(["closed"], events)
                self.assertEqual(1, len(errors))
                self.assertIn(tokens[0] if stale else "missing_token", errors[0])
                self.assertIsNone(self.panel("CGameDialogPanel"))
                self.assertFlowsReleased()

    def installQuest(self, *, precommit=False, fail_before=False, fail_after=False):
        api, ui = self.api, self.ui
        events = []
        state = {"phase": "initial", "failBefore": fail_before}

        class CallbackQuest(api.CQuest):
            def isCompleted(quest):
                return True

            def onCompleteFlow(quest):
                player = quest.getGame().getMap().getPlayer()
                try:
                    events.append("entered")
                    if state["failBefore"]:
                        state["failBefore"] = False
                        raise RuntimeError("precommit callback sentinel")
                    if precommit:
                        state["phase"] = "before commit"
                        yield ui.uiRequest("gui.showCampaignScreen", "Before commit", "Wait", "Continue")
                    player.addGold(7)
                    events.append("reward")
                    player.checkQuests()
                    yield ui.uiRequest("gui.checkQuests", player)
                    yield ui.uiRequest("gui.questCommitted")
                    state["phase"] = "committed"
                    events.append("committed")
                    if fail_after:
                        raise RuntimeError("committed callback sentinel")
                    yield ui.uiRequest("gui.showCampaignScreen", "Reward receipt", "Gold +7", "Continue")
                    state["phase"] = "receipt closed"
                    events.append("receipt closed")
                finally:
                    events.append("hook closed")

            def captureJournal(quest, completed):
                events.append(("journal", completed, state["phase"]))
                quest.setStringProperty("capturedPhase", state["phase"])

        self.game.getObjectHandler().registerType("CallbackQuest", CallbackQuest)
        quest = self.game.createObject("CallbackQuest")
        self.player.setQuests({quest})
        self.player.setCompletedQuests(set())
        return quest, state, events

    def checkQuestsLater(self):
        ui, player = self.ui, self.player

        def callback():
            yield ui.uiRequest("gui.checkQuests", player)

        self.game.runUiFlowLater(callback)

    def testNativeQuestRewardsCommitJournalAfterReceiptAndSuppressReentrantChecks(self):
        quest, state, events = self.installQuest()
        gold_before = self.player.getGold()
        self.checkQuestsLater()
        receipt = self.awaitPanel("CGameCampaignPanel")
        self.assertEqual("Reward receipt", receipt.getTitle())
        self.assertEqual(["entered", "reward", "committed"], events)
        self.assertEqual(gold_before + 7, self.player.getGold())
        self.assertIn(quest, self.player.getQuests())
        self.assertNotIn(quest, self.player.getCompletedQuests())
        receipt.clickAction()
        self.pumpUntil(lambda: quest in self.player.getCompletedQuests(), "Quest did not commit after receipt closure")
        self.assertNotIn(quest, self.player.getQuests())
        self.assertEqual("receipt closed", quest.getStringProperty("capturedPhase"))
        self.assertEqual(1, events.count("reward"))
        self.assertEqual([("journal", True, "receipt closed")], [entry for entry in events if isinstance(entry, tuple)])
        self.player.checkQuests()
        self.assertEqual(1, events.count("reward"))
        self.assertFlowsReleased()

    def testQueuedShutdownSkipsCallbackBodyAndReward(self):
        events = []
        ui, player = self.ui, self.player
        gold_before = player.getGold()

        def callback():
            events.append("unexpected reward")
            player.addGold(7)
            yield ui.uiRequest("gui.questCommitted")

        self.game.runUiFlowLater(callback)
        self.game.getContext().shutdown()
        self.settle()
        self.assertEqual([], events)
        self.assertEqual(gold_before, player.getGold())
        self.assertFalse(self.game.getContext().isActive())
        self.assertFlowsReleased()

    def testNativePrecommitShutdownLeavesQuestActiveAndAvoidsUnsafeJournalHooks(self):
        quest, state, events = self.installQuest(precommit=True)
        gold_before = self.player.getGold()
        self.checkQuestsLater()
        self.assertEqual("Before commit", self.awaitPanel("CGameCampaignPanel").getTitle())
        self.game.getContext().shutdown()
        self.settle()
        self.assertEqual(gold_before, self.player.getGold())
        self.assertIn(quest, self.player.getQuests())
        self.assertNotIn(quest, self.player.getCompletedQuests())
        self.assertEqual(["entered", "hook closed"], events)
        self.assertFlowsReleased()

    def testNativeCommittedShutdownKeepsCompletionWithoutCallingInactiveJournalHooks(self):
        quest, state, events = self.installQuest()
        gold_before = self.player.getGold()
        self.checkQuestsLater()
        self.awaitPanel("CGameCampaignPanel")
        self.game.getContext().shutdown()
        self.settle()
        self.assertEqual(gold_before + 7, self.player.getGold())
        self.assertNotIn(quest, self.player.getQuests())
        self.assertIn(quest, self.player.getCompletedQuests())
        self.assertEqual(["entered", "reward", "committed", "hook closed"], events)
        self.assertFlowsReleased()

    def testNativeQuestShutdownHonorsItsYieldedCommitWithoutResumingPython(self):
        api, ui = self.api, self.ui
        events = []

        class ShutdownCommitQuest(api.CQuest):
            def isCompleted(quest):
                return True

            def onCompleteFlow(quest):
                player = quest.getGame().getMap().getPlayer()
                try:
                    player.addGold(7)
                    events.append("reward")
                    quest.getGame().getContext().shutdown()
                    yield ui.uiRequest("gui.questCommitted")
                    events.append("unexpected inactive resume")
                finally:
                    events.append("hook closed")

            def captureJournal(quest, completed):
                events.append("unexpected inactive journal")

        self.game.getObjectHandler().registerType("ShutdownCommitQuest", ShutdownCommitQuest)
        quest = self.game.createObject("ShutdownCommitQuest")
        self.player.setQuests({quest})
        self.player.setCompletedQuests(set())
        gold_before = self.player.getGold()
        self.checkQuestsLater()
        self.pumpUntil(lambda: quest in self.player.getCompletedQuests(), "Cancelled explicit reward did not settle")
        self.assertFalse(self.game.getContext().isActive())
        self.assertEqual(gold_before + 7, self.player.getGold())
        self.assertNotIn(quest, self.player.getQuests())
        self.assertEqual(["reward", "hook closed"], events)
        self.assertFlowsReleased()

    def testNativeCommittedCallbackFailureCannotGrantTheQuestRewardTwice(self):
        quest, state, events = self.installQuest(fail_after=True)
        gold_before = self.player.getGold()
        self.checkQuestsLater()
        self.pumpUntil(lambda: "hook closed" in events, "Committed callback failure did not settle")
        self.settle()
        self.assertEqual(gold_before + 7, self.player.getGold())
        self.assertIn(quest, self.player.getCompletedQuests())
        self.assertNotIn(quest, self.player.getQuests())
        self.player.checkQuests()
        self.assertEqual(1, events.count("reward"))
        self.assertEqual([("journal", True, "committed")], [entry for entry in events if isinstance(entry, tuple)])
        self.assertFlowsReleased()

    def testNativePrecommitFailureReleasesCheckGuardForOneSuccessfulRetry(self):
        quest, state, events = self.installQuest(fail_before=True)
        gold_before = self.player.getGold()
        self.checkQuestsLater()
        self.pumpUntil(lambda: events == ["entered", "hook closed"], "Precommit callback failure did not settle")
        self.assertIn(quest, self.player.getQuests())
        self.assertEqual(gold_before, self.player.getGold())
        self.checkQuestsLater()
        self.awaitPanel("CGameCampaignPanel").clickAction()
        self.pumpUntil(lambda: quest in self.player.getCompletedQuests(), "Failed quest guard blocked a later retry")
        self.assertEqual(1, events.count("reward"))
        self.assertEqual(gold_before + 7, self.player.getGold())
        self.assertFlowsReleased()

    def testNativeLegacyQuestShutdownStopsCompletionAndAllLaterQuestPredicates(self):
        api = self.api
        for shutdown_at in ("predicate", "completion"):
            with self.subTest(shutdown_at=shutdown_at):
                if shutdown_at == "completion":
                    self.game = self.newGame()
                    self.player = self.game.getMap().getPlayer()
                events = []

                class LegacyShutdownQuest(api.CQuest):
                    def isCompleted(quest):
                        events.append(("predicate", quest.getName()))
                        if shutdown_at == "predicate":
                            quest.getGame().getContext().shutdown()
                        return True

                    def onComplete(quest):
                        events.append(("completion", quest.getName()))
                        quest.getGame().getContext().shutdown()

                    def captureJournal(quest, completed):
                        events.append(("unexpected inactive journal", quest.getName()))

                self.game.getObjectHandler().registerType("LegacyShutdownQuest", LegacyShutdownQuest)
                first = self.game.createObject("LegacyShutdownQuest")
                second = self.game.createObject("LegacyShutdownQuest")
                self.player.setQuests({first, second})
                self.checkQuestsLater()
                self.pumpUntil(
                    lambda: not self.game.getContext().isActive(), "Legacy quest callback did not close its context"
                )
                self.settle()
                self.assertEqual(1, sum(event[0] == "predicate" for event in events))
                self.assertEqual(int(shutdown_at == "completion"), sum(event[0] == "completion" for event in events))
                self.assertFalse(any(event[0] == "unexpected inactive journal" for event in events))
                self.assertEqual(int(shutdown_at == "completion"), len(self.player.getCompletedQuests()))
                self.assertFlowsReleased()

    def installActionDialog(self, *, error=False, condition_callback=None):
        api, ui = self.api, self.ui
        events = []
        state = {"error": error}

        class CallbackDialog(api.CDialog):
            def getActionFlow(dialog, action):
                if action != "choose":
                    raise AssertionError("Unexpected native dialog action")
                return dialog.chooseFlow

            def invokeAction(dialog, action):
                raise AssertionError("Native dialog flow must not invoke its synchronous fallback")

            def invokeCondition(dialog, condition):
                return condition_callback(condition) if condition_callback is not None else True

            def chooseFlow(dialog):
                try:
                    events.append("action started")
                    yield ui.uiRequest("gui.showCampaignScreen", "Dialog action", "Wait", "Continue")
                    if state["error"]:
                        raise RuntimeError("dialog callback sentinel")
                    events.append("action returned")
                finally:
                    events.append("action closed")

        self.game.getObjectHandler().registerType("CallbackDialog", CallbackDialog)
        return (
            *self.makeDialog(self.game.createObject("CallbackDialog"), action="choose", next_state="AFTER"),
            events,
            state,
        )

    def historyStates(self):
        return [entry["state"] for entry in json.loads(self.player.getStringProperty("uiDialogueHistory") or "[]")]

    def testNativeDialogDuplicateInputIsIgnoredAndClosingSourceCannotReviveItsPanel(self):
        dialog, option, events, state = self.installActionDialog()
        outer = []
        panel = self.openDialogLater(dialog, outer)
        panel.keyboardEvent(self.gui, 768, ord("1"))
        receipt = self.awaitPanel("CGameCampaignPanel")
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.settle()
        self.assertEqual(["action started"], events)
        panel.close()
        self.pumpUntil(lambda: "outer closed" in outer, "Closing the outgoing dialog did not release its owner")
        receipt.clickAction()
        self.pumpUntil(lambda: "action closed" in events, "Nested action did not settle after source-panel close")
        self.assertIsNone(panel.getParent())
        self.assertIsNone(self.panel("CGameDialogPanel"))
        self.assertNotIn("AFTER", self.historyStates())
        self.assertFlowsReleased()

    def testNativeDialogTransitionWhileAwaitingActionCannotReviveOutgoingState(self):
        dialog, option, events, state = self.installActionDialog()
        panel = self.openDialogLater(dialog, [])
        panel.keyboardEvent(self.gui, 768, ord("1"))
        receipt = self.awaitPanel("CGameCampaignPanel")
        old_map = self.game.getMap()
        self.game.changeMap("test")
        self.pumpUntil(lambda: self.game.getMap() is not old_map, "Queued transition did not change the active map")
        if receipt.getParent() is not None:
            receipt.clickAction()
        self.pumpUntil(lambda: "action closed" in events, "Stale dialog action did not finish its callback")
        self.settle()
        self.assertIsNone(panel.getParent())
        self.assertIsNone(self.panel("CGameDialogPanel"))
        self.assertNotIn("AFTER", self.historyStates())
        self.assertFlowsReleased()

    def testNativeConditionlessDialogIgnoresInputAfterATransitionHasAlreadyBeenQueued(self):
        dialog, option, events, state = self.installActionDialog()
        self.assertEqual("", option.getStringProperty("condition"))
        panel = self.openDialogLater(dialog, [])
        old_map = self.game.getMap()
        self.game.changeMap("test")
        self.assertTrue(self.game.getSceneManager().isTransitionPending())
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.assertEqual(
            [], events, "A conditionless option must not start its old action after a transition is queued"
        )
        self.pumpUntil(lambda: self.game.getMap() is not old_map, "Queued transition did not complete")
        self.assertIsNone(panel.getParent())
        self.assertIsNone(self.panel("CGameCampaignPanel"))
        self.assertNotIn("AFTER", self.historyStates())
        self.assertFlowsReleased()

    def testNativeDialogCallbackErrorsKeepStateClosedToProgressAndPermitRetry(self):
        dialog, option, events, state = self.installActionDialog(error=True)
        panel = self.openDialogLater(dialog, [])
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.awaitPanel("CGameCampaignPanel").clickAction()
        self.pumpUntil(lambda: "action closed" in events, "Failing dialog callback did not settle")
        self.assertIs(panel.getParent(), self.gui)
        self.assertNotIn("AFTER", self.historyStates())
        state["error"] = False
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.awaitPanel("CGameCampaignPanel").clickAction()
        self.pumpUntil(lambda: "AFTER" in self.historyStates(), "Dialog selection guard did not permit a retry")
        self.assertEqual(2, events.count("action started"))
        self.assertEqual(1, events.count("action returned"))
        panel.close()
        self.assertFlowsReleased()

    def testNativeDialogAfterConditionCannotOverwriteItsReplacementDialog(self):
        replacement, _ = self.makeDialog()
        panels = []

        def replace(condition):
            if condition != "replace":
                raise AssertionError("Unexpected dialog after-condition")
            panels[0].setObjectProperty("dialog", replacement)
            return True

        dialog, option, events, state = self.installActionDialog(condition_callback=replace)
        option.setStringProperty("afterCondition", "replace")
        option.setStringProperty("afterStateId", "STALE")
        panel = self.openDialogLater(dialog, [])
        panels.append(panel)
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.awaitPanel("CGameCampaignPanel").clickAction()
        self.pumpUntil(lambda: "action closed" in events, "Dialog after-condition did not finish")
        self.settle()
        self.assertIs(panel.getObjectProperty("dialog"), replacement)
        self.assertIs(panel.getParent(), self.gui)
        self.assertNotIn("STALE", self.historyStates())
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.pumpUntil(
            lambda: panel.getParent() is None, "Replacement ENTRY state was overwritten by stale continuation"
        )
        self.assertFlowsReleased()

    def testNativeDialogPreconditionReentryCannotRunItsOldActionOnAReplacementDialog(self):
        replacement, _ = self.makeDialog()
        panels = []
        condition_state = {"armed": False, "calls": 0}

        def replace(condition):
            if condition != "replaceBefore":
                raise AssertionError("Unexpected dialog precondition")
            if condition_state["armed"]:
                condition_state["calls"] += 1
                # keyboardEvent and getOption inspect visibility before selectOptionAsync checks it.
                if condition_state["calls"] == 3:
                    panels[0].setObjectProperty("dialog", replacement)
            return True

        dialog, option, events, state = self.installActionDialog(condition_callback=replace)
        option.setStringProperty("condition", "replaceBefore")
        panel = self.openDialogLater(dialog, [])
        panels.append(panel)
        condition_state["armed"] = True
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.settle()
        self.assertEqual(3, condition_state["calls"])
        self.assertIs(panel.getObjectProperty("dialog"), replacement)
        self.assertIs(panel.getParent(), self.gui)
        self.assertEqual([], events, "Replacing the dialog in its condition must prevent the captured old action")
        self.assertIsNone(self.panel("CGameCampaignPanel"))
        panel.keyboardEvent(self.gui, 768, ord("1"))
        self.pumpUntil(lambda: panel.getParent() is None, "Replacement dialog did not retain its original ENTRY option")
        self.assertFlowsReleased()


class NativeCoroutineCallbackSelectionTest(unittest.TestCase):
    def runMissingBinaryCase(self, *, required, explicit):
        case = NativeCoroutineCallbackTest("testQueuedShutdownSkipsCallbackBodyAndReward")
        case.requireCurrentNativeBinary = required
        imported = []
        original_import = builtins.__import__

        def importModule(name, *args, **kwargs):
            if name in {"test", "game", "_game", "ui"}:
                imported.append(name)
                raise AssertionError("Missing-binary selection must finish before native imports")
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ), patch.object(Path, "is_file", return_value=False):
            if explicit:
                os.environ["GAME_BUILD_DIR"] = "build/missing-coroutine-callback-fixture"
            else:
                os.environ.pop("GAME_BUILD_DIR", None)
            with patch.object(builtins, "__import__", side_effect=importModule):
                result = unittest.TestResult()
                case.run(result)
        self.assertEqual([], imported)
        self.assertEqual([], result.errors)
        return result

    def testSourceDiscoverySkipsMissingExplicitBuildWithoutImportingNativeModules(self):
        result = self.runMissingBinaryCase(required=False, explicit=True)
        self.assertEqual([], result.failures)
        self.assertEqual(1, len(result.skipped))

    def testRequiredRuntimeFailsMissingBinaryWithAndWithoutAnEnvironmentOverride(self):
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                result = self.runMissingBinaryCase(required=True, explicit=explicit)
                self.assertEqual([], result.skipped)
                self.assertEqual(1, len(result.failures))
                self.assertIn("Required current native coroutine callback binary", result.failures[0][1])

    def testStaleApiSkipsSourceDiscoveryButFailsRequiredRuntime(self):
        build = ROOT / "build/stale-coroutine-callback-fixture"
        fake_harness = SimpleNamespace(load_game_module=lambda: SimpleNamespace(CGame=SimpleNamespace()))
        fake_native = SimpleNamespace(__file__=str(build / ("_game" + EXTENSION_SUFFIXES[0])))
        for required in (False, True):
            with self.subTest(required=required):
                case = NativeCoroutineCallbackTest("testQueuedShutdownSkipsCallbackBodyAndReward")
                case.requireCurrentNativeBinary = required
                with (
                    patch.dict(os.environ, {"GAME_BUILD_DIR": str(build)}),
                    patch.object(Path, "is_file", return_value=True),
                    patch.dict(sys.modules, {"test": fake_harness}),
                    patch.object(importlib, "import_module", return_value=fake_native),
                ):
                    result = unittest.TestResult()
                    case.run(result)
                self.assertEqual([], result.errors)
                self.assertEqual(int(required), len(result.failures))
                self.assertEqual(int(not required), len(result.skipped))

    def testRuntimeHarnessMarksNativeCallbackCoverageAsRequired(self):
        harness = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        runtime_class = next(
            node
            for node in ast.walk(harness)
            if isinstance(node, ast.ClassDef) and node.name == "NativeCoroutineCallbackTest"
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "requireCurrentNativeBinary"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
                for node in runtime_class.body
            ),
            "test.py runtime suites must fail when their required native callback binary is missing or stale",
        )


if __name__ == "__main__":
    unittest.main()
