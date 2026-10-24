# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deferred real-extension wait checks; source-only runs do not provide native timing evidence."""

import unittest

from tests import test_python_callback_lifecycle as callback_lifecycle


class WaitStateRuntimeTest(unittest.TestCase):
    runChild = callback_lifecycle.PythonCallbackLifecycleTest.runChild

    def testStrictSetterAndActualNativeFlowRejectInvalidWaitArguments(self):
        output = self.runChild("""
            instance = game.CGameLoader.loadGame()
            foreign = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'empty', 'Warrior')
            state = instance.createObject('CWaitState')
            assert isinstance(state, game.CWaitState)
            try:
                for value in (True, False, 1.5, '4', None, -1, 60001, 10 ** 100):
                    try:
                        state.setRemainingMilliseconds(value)
                    except (TypeError, ValueError, OverflowError, RuntimeError):
                        pass
                    else:
                        raise AssertionError(('invalid duration accepted', value))
                    assert state.getRemainingMilliseconds() == 0
                # The generic numeric-property bridge retains its existing integer contract.
                state.setNumericProperty('remainingMilliseconds', 60000)
                assert state.getRemainingMilliseconds() == 60000
                state.setRemainingMilliseconds(0)
                events = []
                def wait(value):
                    try:
                        result = yield {'operation': 'gui.waitMilliseconds', 'args': (value,), 'kwargs': {}}
                        events.append(result)
                    except RuntimeError as failure:
                        events.append(str(failure))
                    finally:
                        events.append('closed')
                instance.runUiFlowLater(lambda: wait(state))
                for _ in range(20):
                    loop.run()
                    if events:
                        break
                assert events == [True, 'closed'], events
                wrong = (True, 1.5, 'state', None, instance.createObject('CItem'), foreign.createObject('CWaitState'))
                for value in wrong:
                    events.clear()
                    instance.runUiFlowLater(lambda value=value: wait(value))
                    for _ in range(20):
                        loop.run()
                        if events:
                            break
                    assert len(events) == 2 and isinstance(events[0], str) and events[1] == 'closed', events
                print('strict native wait duration and token contracts passed', flush=True)
            finally:
                foreign.getContext().shutdown()
                instance.getContext().shutdown()
            """)
        self.assertIn("strict native wait duration and token contracts passed", output)

    def testRunningCoordinatorWaitSavesRemainingTimeAndReloadsPaused(self):
        output = self.runChild("""
            import json
            import os
            from pathlib import Path
            import time
            instance = game.CGameLoader.loadGame()
            restored = None
            completed = False
            slot = 'native-wait-countdown-' + str(os.getpid()) + '-' + str(time.time_ns())
            save_path = None
            events = []
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'empty', 'Warrior')
                world = instance.getMap()
                coordinator = instance.createObject('CBuilding')
                coordinator.setName('unitWaitCoordinator')
                world.addObject(coordinator)
                state = instance.createObject('CWaitState')
                state.setRemainingMilliseconds(60000)
                coordinator.setObjectProperty('pendingWait', state)
                def countdown():
                    events.append('entered')
                    try:
                        result = yield {'operation': 'gui.waitMilliseconds', 'args': (state,), 'kwargs': {}}
                        events.append(result)
                    finally:
                        events.append('closed')
                instance.runUiFlowLater(countdown)
                loop.run()
                assert events == ['entered'], events
                try:
                    state.setRemainingMilliseconds(0)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('a running native wait accepted mutation')
                before = state.getRemainingMilliseconds()
                assert 0 < before <= 60000
                assert game.CMapLoader.saveWithResult(world, slot)
                save_path = Path(instance.getResourcesProvider().getPath('save/' + slot + '.json'))
                document = json.loads(save_path.read_text(encoding='utf-8'))
                snapshots = []
                def visit(value):
                    if isinstance(value, dict):
                        if value.get('class') == 'CWaitState':
                            snapshots.append(value['properties']['remainingMilliseconds'])
                        for child in value.values():
                            visit(child)
                    elif isinstance(value, list):
                        for child in value:
                            visit(child)
                visit(document)
                assert len(snapshots) == 1, snapshots
                saved = snapshots[0]
                assert 0 < saved <= before and state.getRemainingMilliseconds() <= saved
                restored = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(restored, slot)
                owner = restored.getMap().getObjectByName('unitWaitCoordinator')
                loaded = owner.getObjectProperty('pendingWait')
                assert isinstance(loaded, game.CWaitState) and loaded is not state
                assert loaded.getGame() is restored and loaded.getRemainingMilliseconds() == saved
                time.sleep(0.03)
                assert loaded.getRemainingMilliseconds() == saved
                loaded.setRemainingMilliseconds(0)
                instance.getContext().shutdown()
                assert events == ['entered', 'closed'], events
                completed = True
                print('native running wait snapshot restored paused without offline catchup', flush=True)
            finally:
                if restored is not None:
                    restored.getContext().shutdown()
                instance.getContext().shutdown()
                if completed and save_path is not None:
                    save_path.unlink(missing_ok=True)
                    Path(str(save_path) + '.bak').unlink(missing_ok=True)
            """)
        self.assertIn("native running wait snapshot restored paused without offline catchup", output)
