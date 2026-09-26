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


if __name__ == "__main__":
    unittest.main()
