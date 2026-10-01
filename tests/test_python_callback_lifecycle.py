# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = """
import sys
try:
    import play
except ModuleNotFoundError as error:
    if error.name == '_game':
        raise SystemExit(77)
    raise
import _game as game
game.set_logger_sink('disabled')
loop = game.event_loop.instance()
"""


class PythonCallbackLifecycleTest(unittest.TestCase):
    def runChild(self, code):
        environment = os.environ.copy()
        with tempfile.TemporaryDirectory(prefix="nouraajd-callback-lifecycle-") as temporary:
            environment.update(
                SDL_VIDEODRIVER="dummy",
                SDL_AUDIODRIVER="dummy",
                SDL_RENDER_DRIVER="software",
                LIBGL_ALWAYS_SOFTWARE="1",
                GAME_UI_PREFERENCES_PATH=str(Path(temporary) / "preferences.json"),
            )
            result = subprocess.run(
                [sys.executable, "-c", BOOTSTRAP + textwrap.dedent(code)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
        if result.returncode == 77:
            self.skipTest("The compiled _game module is unavailable.")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def testPendingPlainCallbackDoesNotCrashAtProcessExit(self):
        output = self.runChild("""
            assert loop.invoke(lambda: print('unexpected execution', flush=True))
            del loop
            print('queued', flush=True)
            """)
        self.assertIn("queued", output)
        self.assertNotIn("unexpected execution", output)

    def testPendingCallbacksReleaseCapturesBeforePythonFinalizes(self):
        output = self.runChild("""
            class Payload:
                def __del__(self):
                    print('released', sys.is_finalizing(), flush=True)
            payload = Payload()
            assert loop.invoke(lambda captured=payload: print('unexpected execution', flush=True))
            del payload
            del loop
            print('queued', flush=True)
            """)
        self.assertIn("queued", output)
        self.assertIn("released False", output)
        self.assertNotIn("unexpected execution", output)

    def testExecutedNestedAndThrowingCallbacksReleaseTheirCaptures(self):
        output = self.runChild("""
            import gc
            import weakref
            events = []
            class Callback:
                def __call__(self):
                    events.append('first')
                    assert loop.invoke(lambda: events.append('nested'))
                    raise RuntimeError('deliberate callback failure')
            callback = Callback()
            reference = weakref.ref(callback)
            assert loop.invoke(callback)
            del callback
            assert loop.invoke(lambda: events.append('second'))
            loop.run()
            assert events == ['first', 'second'], events
            gc.collect()
            assert reference() is None
            loop.run()
            assert events == ['first', 'second', 'nested'], events
            loop.run()
            assert events == ['first', 'second', 'nested'], events
            print('normal dispatch preserved', flush=True)
            """)
        self.assertIn("normal dispatch preserved", output)

    def testCompletedCallbackCapturesDoNotAccumulate(self):
        output = self.runChild("""
            import gc
            import weakref
            calls = []
            references = []
            class Callback:
                def __call__(self):
                    calls.append(1)
            for batch in range(4):
                for index in range(50):
                    callback = Callback()
                    references.append(weakref.ref(callback))
                    assert loop.invoke(callback)
                del callback
                loop.run()
                gc.collect()
                assert all(reference() is None for reference in references)
                assert len(calls) == (batch + 1) * 50
            print('200 captures released across four batches', flush=True)
            """)
        self.assertIn("200 captures released across four batches", output)

    def testShutdownIsIdempotentAndRejectsReentrantScheduling(self):
        output = self.runChild("""
            import atexit
            import gc
            import weakref
            events = []
            class Callback:
                def __call__(self):
                    events.append('unexpected execution')
                def __del__(self):
                    events.append(('rescheduled', loop.invoke(lambda: events.append('unexpected nested'))))
            callback = Callback()
            reference = weakref.ref(callback)
            assert loop.invoke(callback)
            del callback
            atexit._run_exitfuncs()
            atexit._run_exitfuncs()
            gc.collect()
            assert reference() is None
            assert events == [('rescheduled', False)], events
            assert not loop.invoke(lambda: events.append('unexpected late'))
            loop.run()
            assert events == [('rescheduled', False)], events
            print('shutdown canceled pending callbacks', flush=True)
            """)
        self.assertIn("shutdown canceled pending callbacks", output)

    def testPendingTransitionCapturesReleaseBeforePythonFinalizes(self):
        output = self.runChild("""
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            class Payload:
                def __del__(self):
                    print('transition released', sys.is_finalizing(), flush=True)
            payload = Payload()
            assert instance.changeMapWithPreparation(
                'ritual', lambda captured=payload: print('unexpected preparation', flush=True),
                lambda success, captured=payload: print('unexpected completion', flush=True))
            del payload
            print('transition queued', flush=True)
            """)
        self.assertIn("transition queued", output)
        self.assertIn("transition released False", output)
        self.assertNotIn("unexpected preparation", output)
        self.assertNotIn("unexpected completion", output)

    def testCompletedRejectedAndFailedTransitionCapturesRelease(self):
        output = self.runChild("""
            import gc
            import weakref
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            source = instance.getMap()
            events = []
            references = []
            class Callback:
                def __init__(self, label):
                    self.label = label
                    references.append(weakref.ref(self))
                def __call__(self, *args):
                    events.append((self.label, *args))
            assert instance.changeMapWithPreparation(
                'missingPreparedMap', Callback('prepareMissing'), Callback('missing'))
            assert not instance.changeMapWithPreparation(
                'ritual', Callback('prepareRejected'), Callback('rejected'))
            for index in range(10):
                loop.run()
            gc.collect()
            assert events == [('rejected', False), ('missing', False)], events
            assert instance.getMap() == source
            assert all(reference() is None for reference in references)
            assert instance.changeMapWithPreparation('ritual', Callback('prepare'), Callback('completed'))
            for index in range(10):
                loop.run()
            gc.collect()
            assert events[-2:] == [('prepare',), ('completed', True)], events
            assert instance.getMap().mapName == 'ritual'
            assert all(reference() is None for reference in references)
            print('transition captures released', flush=True)
            """)
        self.assertIn("transition captures released", output)

    def testContextShutdownCancelsTransitionWithoutPreparing(self):
        output = self.runChild("""
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            events = []
            assert instance.changeMapWithPreparation(
                'ritual', lambda: events.append('unexpected preparation'),
                lambda success: events.append(('completed', success)))
            instance.getContext().shutdown()
            for index in range(10):
                loop.run()
            assert events == [('completed', False)], events
            assert instance.getMap() is None
            print('transition canceled on shutdown', flush=True)
            """)
        self.assertIn("transition canceled on shutdown", output)

    def testSaveResourceScopeDoesNotReattachMapAfterPluginShutdown(self):
        output = self.runChild("""
            from pathlib import Path
            import shutil
            import uuid
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            source = instance.getMap()
            context = instance.getContext()
            provider = instance.getResourcesProvider()
            resource_root = Path(provider.getPath('config/items.json')).parent.parent
            nonce = uuid.uuid4().hex
            map_name = 'unitShutdownScope' + nonce
            map_directory = resource_root / 'maps' / map_name
            map_directory.mkdir()
            save_path = None
            try:
                (map_directory / 'script.py').write_text(
                    'def load(self, context):\\n    context.getContext().shutdown()\\n', encoding='utf-8')
                slot = 'unit-shutdown-scope-' + nonce
                source.mapName = map_name
                game.CMapLoader.save(source, slot)
                save_path = Path(provider.getPath('save/' + slot + '.json'))
                assert save_path.is_file()
                source.mapName = 'test'
                try:
                    game.CGameLoader.loadSavedGame(instance, slot)
                except RuntimeError:
                    pass
                assert not context.isActive(), 'fixture plugin must close its game context'
                assert instance.getMap() is None, 'scope unwinding must not reattach the previous closed map'
                print('closed map stayed detached after save restore', flush=True)
            finally:
                if save_path is not None:
                    save_path.unlink(missing_ok=True)
                    Path(str(save_path) + '.bak').unlink(missing_ok=True)
                shutil.rmtree(map_directory)
            """)
        self.assertIn("closed map stayed detached after save restore", output)

    def testShutdownDuringPreparationDoesNotAttachDestination(self):
        output = self.runChild("""
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            source = instance.getMap()
            events = []
            def prepare():
                assert instance.getMap() == source
                events.append('prepared')
                instance.getContext().shutdown()
            assert instance.changeMapWithPreparation(
                'ritual', prepare, lambda success: events.append(('completed', success)))
            for index in range(10):
                loop.run()
            assert events == ['prepared', ('completed', False)], events
            assert instance.getMap() is None
            print('preparation shutdown preserved', flush=True)
            """)
        self.assertIn("preparation shutdown preserved", output)


if __name__ == "__main__":
    unittest.main()
