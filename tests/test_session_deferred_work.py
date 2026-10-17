# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
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
    def testQuestDeathFixtureDrainsActualLoadSynchronizationBeforeRemovingItsFirstActor(self):
        fixture = hunt_tests.OctobogzHuntTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.game_map.player.setStringProperty("nouraajdVictorState", "already-synchronized")
        callback_tree = ast.parse((ROOT / "res/maps/nouraajd/script.py").read_text(encoding="utf-8"))
        callback = next(
            node
            for node in ast.walk(callback_tree)
            if isinstance(node, ast.FunctionDef) and node.name == "syncLoadedVictorState"
        )
        callback_namespace = {
            "resolveContext": lambda: fixture.game,
            "_get_quest_system": Mock(side_effect=AssertionError("This fixture already synchronized Victor")),
        }
        exec(
            compile(ast.Module(body=[callback], type_ignores=[]), "actual_loaded_map_sync", "exec"), callback_namespace
        )
        events, pumps = [], []

        def synchronizeLoadedMap():
            events.append("loaded-map-sync")
            callback_namespace["syncLoadedVictorState"]()

        fixture.pending.append(synchronizeLoadedMap)

        def runSnapshot():
            snapshot = list(fixture.pending)
            fixture.pending.clear()
            for work in snapshot:
                work()

        def pump(iterations):
            pumps.append(iterations)
            for _ in range(iterations):
                runSnapshot()

        def removeAtNativeSuspensionBoundary(actor):
            name = actor.getName()
            events.append("remove:" + name)
            fixture.game_map.objects.pop(name)
            if isinstance(actor, hunt_tests.Actor):
                actor.effects.clear()
            if name == "cave2" and fixture.game_map.getBoolProperty("octobogzHuntCleared"):
                fixture.game_map.completed += 1
            # Native removal erases the object before its missing onDestroyFlow lookup suspends.
            # A ready load callback can therefore run before the trigger sees the original actor.
            runSnapshot()
            for trigger in list(fixture.game_map.triggers.values()):
                if trigger.getStringProperty("object") == name:
                    trigger.trigger(actor, None)
            actor.game_map = None

        fixture.game_map.removeObject = removeAtNativeSuspensionBoundary
        source = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        complete = next(
            node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "completeOctobogzFixture"
        )
        namespace = {"json": __import__("json"), "pump_event_loop": pump}
        exec(compile(ast.Module(body=[complete], type_ignores=[]), "actual_quest_death_fixture", "exec"), namespace)
        namespace["completeOctobogzFixture"](fixture.game_map)
        self.assertEqual("loaded-map-sync", events[0], "Load synchronization must finish before the first removal")
        self.assertEqual(
            [3, 3, 3, 3], pumps, "Keep the existing three post-death pumps and one initialization boundary"
        )
        self.assertEqual(1, fixture.game_map.added.count("octobogzScout"), "The original Scout must never be recreated")
        self.assertEqual({"dead"}, {record["status"] for record in fixture.state()["slots"].values()})
        self.assertEqual(1, fixture.game_map.completed)

    def testCancelledTownPortalFrameReleasesItsPlayerWithoutOwningTheSession(self):
        from tests.test_first_party_hook_flows import objectClasses

        classes, _api = objectClasses()
        session = Session()

        class PortalPlayer(Player):
            def getMap(self):
                return SimpleNamespace(getEntryX=lambda: 12, getEntryY=lambda: 8, getEntryZ=lambda: 2)

        player = PortalPlayer(session)
        player_reference, session_reference = weakref.ref(player), weakref.ref(session)
        flow = classes["TownPortalScroll"]().onUseFlow(SimpleNamespace(getCause=lambda: player))
        request = next(flow)
        self.assertEqual("gui.itemMoveTo", request["operation"])
        del request, player, session
        gc.collect()
        self.assertIsNone(session_reference())
        self.assertIsNotNone(player_reference(), "the pending operation must retain its exact actor")
        flow.close()
        self.assertIsNone(flow.gi_frame, "cancellation must close the suspended generator frame")
        # CPython 3.12 can retain arguments in the closed generator; native CScriptFlow also destroys its owner.
        del flow
        gc.collect()
        self.assertIsNone(player_reference(), "cancelling before movement must release the pending actor")

    def testPairedWaypointGuardSpansSuspensionWithoutBlockingAnotherActor(self):
        from tests.test_first_party_hook_flows import objectClasses

        classes, _api = objectClasses()
        first, paired = classes["WayPoint"](), classes["WayPoint"]()
        destination = SimpleNamespace(x=4, y=5, z=1)
        first.getExit = paired.getExit = lambda: destination
        actor, other_actor = Mock(), Mock()
        event = SimpleNamespace(getCause=lambda: actor)
        flow = first.onEnterFlow(event)
        self.addCleanup(flow.close)
        request = next(flow)
        self.assertEqual({"operation": "gui.moveTo", "args": (actor, 4, 5, 1), "kwargs": {}}, request)
        nested = paired.onEnterFlow(event)
        self.addCleanup(nested.close)
        with self.assertRaises(StopIteration):
            next(nested)
        other = paired.onEnterFlow(SimpleNamespace(getCause=lambda: other_actor))
        self.addCleanup(other.close)
        self.assertEqual(other_actor, next(other)["args"][0])
        other.close()
        with self.assertRaises(StopIteration):
            flow.send(None)
        reentry = paired.onEnterFlow(event)
        self.addCleanup(reentry.close)
        self.assertEqual(actor, next(reentry)["args"][0])

    def testCancelledWaypointFrameReleasesItsRecursionGuardForLaterMovement(self):
        from tests.test_first_party_hook_flows import objectClasses

        for cancellation in ("close", "throw"):
            with self.subTest(cancellation=cancellation):
                classes, _api = objectClasses()
                first, paired = classes["WayPoint"](), classes["WayPoint"]()
                first.getExit = paired.getExit = lambda: SimpleNamespace(x=4, y=5, z=1)
                actor = Mock()
                event = SimpleNamespace(getCause=lambda: actor)
                flow = first.onEnterFlow(event)
                self.addCleanup(flow.close)
                next(flow)
                nested = paired.onEnterFlow(event)
                self.addCleanup(nested.close)
                with self.assertRaises(StopIteration):
                    next(nested)
                if cancellation == "close":
                    flow.close()
                else:
                    with self.assertRaisesRegex(RuntimeError, "cancelled arrival"):
                        flow.throw(RuntimeError("cancelled arrival"))
                self.assertIsNone(flow.gi_frame)
                retry = paired.onEnterFlow(event)
                self.addCleanup(retry.close)
                self.assertEqual(actor, next(retry)["args"][0])

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
