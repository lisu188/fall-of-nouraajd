# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts.check_binding_exceptions import runChecks


class BindingExceptionPreflightTest(unittest.TestCase):
    def makeGame(self, events, *, property_error=None):
        class DynamicObject:
            def __setattr__(self, name, value):
                events.append(("property", name, value))
                raise property_error or TypeError("Unsupported CGameObject property type")

        context = mock.Mock()
        context.shutdown.side_effect = lambda: events.append("shutdown")

        def createObject(name):
            events.append(("create", name))
            return DynamicObject()

        game_instance = SimpleNamespace(createObject=createObject, getContext=lambda: context)

        def loadGame():
            events.append("load")
            return game_instance

        def jsonify(value):
            events.append(("jsonify", value))
            raise TypeError("jsonify() expects a CGameObject instance")

        def setLogger(sink, path):
            events.append(("logger", sink, path))
            if sink != "disabled":
                raise ValueError("invalid logger configuration")

        return SimpleNamespace(
            CGameLoader=SimpleNamespace(loadGame=loadGame), jsonify=jsonify, set_logger_sink=setLogger
        )

    def testSequenceRepeatsEveryBoundaryAndFlushesProgressBeforeCalls(self):
        events = []
        game = self.makeGame(events)
        output = mock.Mock()
        output.write.side_effect = lambda text: events.append(("output", text))
        output.flush.side_effect = lambda: events.append("flush")
        runChecks(game, output=output)
        calls = [
            event for event in events if event != "flush" and not (isinstance(event, tuple) and event[0] == "output")
        ]
        self.assertEqual(
            [("jsonify", {})] * 32
            + [("logger", "unit-test-invalid-sink", None)] * 32
            + [("logger", "file", None)] * 32
            + ["load", ("create", "CGameObject")]
            + [("property", "unsupported_dynamic_value", [])] * 32
            + ["shutdown", ("logger", "disabled", None)],
            calls,
        )
        for index, event in enumerate(events):
            if (
                isinstance(event, tuple)
                and event[0] in {"jsonify", "logger", "create", "property"}
                or event
                in (
                    "load",
                    "shutdown",
                )
            ):
                self.assertEqual("flush", events[index - 1], event)
        output.write.assert_any_call("binding exception preflight: complete")

    def testUnexpectedExceptionPropagatesAfterContextAndLoggerCleanup(self):
        events = []
        failure = RuntimeError("unexpected native failure")
        game = self.makeGame(events, property_error=failure)
        with self.assertRaises(RuntimeError) as raised:
            runChecks(game, repetitions=1, output=io.StringIO())
        self.assertIs(failure, raised.exception)
        self.assertEqual(["shutdown", ("logger", "disabled", None)], events[-2:])
        self.assertEqual(1, sum(isinstance(event, tuple) and event[0] == "property" for event in events))

    def testMissingExceptionFailsAndStillDisablesLogger(self):
        events = []
        game = self.makeGame(events)
        game.jsonify = lambda value: None
        with self.assertRaisesRegex(AssertionError, r"jsonify\(\{\}\) did not raise TypeError"):
            runChecks(game, output=io.StringIO())
        self.assertEqual([("logger", "disabled", None)], events)

    def testObjectCreationFailureStillShutsDownLoadedContext(self):
        events = []
        game = self.makeGame(events)
        game_instance = game.CGameLoader.loadGame()
        events.clear()
        game.CGameLoader.loadGame = lambda: game_instance
        game_instance.createObject = mock.Mock(side_effect=LookupError("factory failed"))
        with self.assertRaisesRegex(LookupError, "factory failed"):
            runChecks(game, repetitions=1, output=io.StringIO())
        self.assertEqual(["shutdown", ("logger", "disabled", None)], events[-2:])

    def testInvalidRepetitionCountDoesNotRunNativeCalls(self):
        game = mock.Mock()
        with self.assertRaisesRegex(ValueError, "repetitions must be positive"):
            runChecks(game, repetitions=0)
        self.assertEqual([], game.mock_calls)

    def testWindowsPreflightRunsBeforeRequiredNativeAndPythonChecks(self):
        from scripts.ci_change_classifier import classifyPaths

        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/build.yml").read_text(encoding="utf-8")
        windows = workflow[workflow.index("  windows:\n") :]
        smoke = windows[windows.index("      - name: Smoke test game imports\n") :]
        smoke = smoke[: smoke.index("      - name: sccache stats after build\n")]
        self.assertIn('PYTHONFAULTHANDLER: "1"', smoke)
        self.assertIn("PYTHONMALLOC: debug", smoke)
        self.assertIn("python scripts/check_binding_exceptions.py\n          if errorlevel 1 exit /b 1", smoke)
        self.assertLess(windows.index("python scripts/check_binding_exceptions.py"), windows.index("test (c++)"))
        self.assertLess(
            windows.index("python scripts/check_binding_exceptions.py"), windows.index("test (python gameplay)")
        )
        classification = classifyPaths([".github/workflows/build.yml", "scripts/check_binding_exceptions.py"])
        self.assertTrue(classification.authorityChange)
        self.assertTrue(classification.humanReviewRequired)
        self.assertTrue(classification.nativeNeeded)
        self.assertTrue(classification.coverageNeeded)


if __name__ == "__main__":
    unittest.main()
