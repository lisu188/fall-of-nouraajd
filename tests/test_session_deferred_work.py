# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import gc
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "res"))

from tests.test_nouraajd_quest_journal import loadQuestClasses
from tests import test_octobogz_hunt as hunt_tests


class Session:
    def __init__(self):
        self.pending = []
        self.active = True
        self.handler = SimpleNamespace(showChoice=Mock(return_value="demoSet"), notify=Mock())

    def getMap(self):
        return None

    def getGuiHandler(self):
        return self.handler

    def createWeakResolver(self):
        reference = weakref.ref(self)

        def resolve():
            owner = reference()
            if owner is None:
                raise RuntimeError("The session was destroyed")
            return owner

        return resolve

    def post(self, callback):
        if not self.active:
            raise RuntimeError("The session was closed")
        self.pending.append(callback)

    runUiFlowLater = post

    def shutdown(self):
        self.active = False
        self.pending.clear()


class Player:
    def __init__(self, session):
        self.session = weakref.ref(session)

    def getGame(self):
        return self.session()

    def isPlayer(self):
        return True


class SessionDeferredWorkTest(unittest.TestCase):
    def artifactModule(self):
        from tests.hook_flow_support import installHookFlows

        legacy = []
        module = ModuleType("game")
        module.register = lambda _context: lambda cls: cls
        module.event_loop = SimpleNamespace(instance=lambda: SimpleNamespace(invoke=legacy.append))
        installHookFlows(module)
        from ui import flowGame, uiGame

        module.flowGame, module.uiGame = flowGame, uiGame
        specification = importlib.util.spec_from_file_location(
            "session_artifact_sets", ROOT / "res/plugins/artifact_sets.py"
        )
        artifacts = importlib.util.module_from_spec(specification)
        with patch.dict(sys.modules, {"game": module}):
            specification.loader.exec_module(artifacts)
        return artifacts, legacy

    def testCancelledArtifactOfferReleasesItsPlayerWithoutRunningAfterShutdown(self):
        artifacts, legacy = self.artifactModule()
        artifacts.maybe_offer_assembly = Mock()
        session = Session()
        player = Player(session)
        reference = weakref.ref(player)
        event = SimpleNamespace(getCause=lambda: player)
        artifacts._schedule_assembly_offer(event)
        del event, player
        session.shutdown()
        gc.collect()
        self.assertIsNone(reference(), "cancelled session work must release its queued gameplay captures")
        for callback in legacy:
            callback()
        artifacts.maybe_offer_assembly.assert_not_called()
        self.assertEqual([], legacy, "first-party artifact work must use the owning session queue")

    def testCancelledArtifactOfferNeverExecutesAfterShutdown(self):
        artifacts, legacy = self.artifactModule()
        artifacts.maybe_offer_assembly = Mock()
        session = Session()
        player = Player(session)
        artifacts._schedule_assembly_offer(SimpleNamespace(getCause=lambda: player))
        session.shutdown()
        for callback in legacy:
            callback()
        artifacts.maybe_offer_assembly.assert_not_called()
        self.assertEqual([], legacy)

    def testArtifactChoiceFlowYieldsAndPreservesAssemblyBehavior(self):
        artifacts, legacy = self.artifactModule()
        definition = {"id": "demoSet", "label": "Demo set"}
        runtime = SimpleNamespace(
            completed_sets=lambda _player: [definition],
            _has_cursed_piece=lambda *_args: False,
            assemblyDetail=lambda *_args, **_kwargs: "The existing equipment preview.",
            assemble=Mock(return_value=True),
        )
        artifacts.get_runtime = lambda: runtime
        session = Session()
        player = Player(session)
        flow = artifacts.maybeOfferAssemblyFlow(player)
        self.addCleanup(flow.close)
        request = next(flow)
        self.assertEqual("gui.showChoice", request["operation"])
        self.assertEqual("Assemble artifact", request["args"][0])
        session.handler.showChoice.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send("demoSet")
        runtime.assemble.assert_called_once_with(session, player, definition)
        session.handler.notify.assert_called_once_with("The pieces fuse into the Demo set.")
        artifacts.maybe_offer_assembly(player)
        self.assertEqual(1, session.handler.showChoice.call_count, "the public Python adapter stays synchronous")
        self.assertEqual([], legacy)

    def testSuspendedArtifactChoiceDoesNotOwnItsNativeGame(self):
        artifacts, _legacy = self.artifactModule()
        artifacts.get_runtime = lambda: SimpleNamespace(
            completed_sets=lambda _player: [{"id": "demoSet", "label": "Demo set"}],
            _has_cursed_piece=lambda *_args: False,
            assemblyDetail=lambda *_args, **_kwargs: "Preview",
        )
        session = Session()
        player = Player(session)
        reference = weakref.ref(session)
        flow = artifacts.maybeOfferAssemblyFlow(player)
        next(flow)
        del session
        gc.collect()
        self.assertIsNone(reference(), "a suspended artifact modal must not retain its game context owner")
        flow.close()

    def testHuntRecoveryUsesTheSessionQueue(self):
        fixture = hunt_tests.OctobogzHuntTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        owned = []
        fixture.game.post.side_effect = owned.append
        fixture.director.start(fixture.game_map)
        actor = fixture.game_map.getObjectByName("octobogzScout")
        fixture.director.actorRemoved(actor)
        self.assertEqual(1, len(owned), "hunt recovery belongs to the actor's game context")
        self.assertEqual([], fixture.pending, "hunt recovery must not escape to the process-global queue")
        fixture.director.synchronize = Mock()
        owned.clear()
        fixture.pump()
        fixture.director.synchronize.assert_not_called()

    def testLoadedMapMigrationUsesAWeakSessionCallback(self):
        session = Session()
        reference = weakref.ref(session)
        legacy = []
        loadQuestClasses(context=session, pending=legacy)
        self.assertEqual(1, len(session.pending), "save-load migration must use the owning game context queue")
        self.assertEqual([], legacy)
        callback = session.pending.pop()
        del session
        gc.collect()
        self.assertIsNone(reference(), "a saved-map migration callback must not keep the native game alive")
        with self.assertRaises(RuntimeError):
            callback()


if __name__ == "__main__":
    unittest.main()
