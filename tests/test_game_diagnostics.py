# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import game_diagnostics

ROOT = Path(__file__).resolve().parents[1]


class GameDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nouraajd-diagnostics-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.environment = mock.patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.closeSession)

    def closeSession(self):
        session = game_diagnostics.currentSession()
        if session is not None:
            session.close()

    def startSession(self, **kwargs):
        with redirect_stderr(io.StringIO()):
            return game_diagnostics.startSession(
                repo_root=self.root, build_dir=self.root / "build", entrypoint="test", **kwargs
            )

    def nativeModule(self):
        def configure(enabled=True, output_path=None, max_records=1000, retain_recent=False):
            raise AssertionError("Trace configuration must not be reset after native import")

        module = SimpleNamespace(
            __file__="/compiled/_game.so",
            configure_playtest_trace=configure,
            configure_playtest_trace_from_env=mock.Mock(
                side_effect=AssertionError("A fresh native import must keep its startup trace")
            ),
            set_logger_sink=mock.Mock(),
            playtest_trace_enabled=lambda: True,
        )

        def logger(message):
            sink, path = module.set_logger_sink.call_args.args
            if sink == "file":
                with Path(path).open("a", encoding="utf-8") as output:
                    output.write(message + "\n")

        module.logger = logger
        return module

    def testDisabledModeDoesNotCreateFilesOrChangeHooks(self):
        original_hook = sys.excepthook
        original_environment = dict(os.environ)
        self.assertIsNone(self.startSession())
        self.assertEqual([], list(self.root.iterdir()))
        self.assertIs(original_hook, sys.excepthook)
        self.assertEqual(original_environment, dict(os.environ))

    def testEnvironmentOptInAndCliDirectoryPrecedence(self):
        os.environ.update(GAME_DEBUG="true", GAME_DEBUG_DIR="environment-output")
        session = self.startSession(debug_dir="cli-output")
        self.assertEqual(self.root / "cli-output", session.runDir.parent)
        self.assertTrue(all(path.exists() for path in session.paths.values()))
        self.assertEqual(str(session.paths["gameplay"]), os.environ["GAME_PLAYTEST_TRACE_FILE"])
        self.assertEqual("1", os.environ["GAME_PLAYTEST_TRACE_RETAIN_RECENT"])
        self.assertIs(session, game_diagnostics.currentSession())
        session.close()
        self.assertIsNone(game_diagnostics.currentSession())
        self.assertEqual("true", os.environ["GAME_DEBUG"])
        self.assertNotIn("GAME_PLAYTEST_TRACE", os.environ)
        self.assertIsNone(self.startSession(debug=False))

    def testDistinctRunsNeverAppendToEarlierBundle(self):
        first = self.startSession(debug=True)
        first.record("first_run")
        first.close()
        second = self.startSession(debug=True)
        self.assertNotEqual(first.runDir, second.runDir)
        second.record("second_run")
        second.close()
        self.assertNotIn("second_run", first.paths["runtime"].read_text(encoding="utf-8"))
        self.assertNotIn("first_run", second.paths["runtime"].read_text(encoding="utf-8"))

    def testLoggingHooksAndEnvironmentAreRestoredWithoutRootChanges(self):
        root_logger = logging.getLogger()
        root_handlers = list(root_logger.handlers)
        target = logging.getLogger("game_diagnostics")
        original_level, original_propagation = target.level, target.propagate
        original_hook, original_thread_hook = sys.excepthook, threading.excepthook
        original_environment = dict(os.environ)
        session = self.startSession(debug=True)
        self.assertEqual(root_handlers, root_logger.handlers)
        self.assertIsNot(original_hook, sys.excepthook)
        session.close()
        self.assertIs(original_hook, sys.excepthook)
        self.assertIs(original_thread_hook, threading.excepthook)
        self.assertEqual(original_environment, dict(os.environ))
        self.assertEqual(original_level, target.level)
        self.assertEqual(original_propagation, target.propagate)
        self.assertEqual(root_handlers, root_logger.handlers)
        self.assertFalse(any(isinstance(handler, game_diagnostics._RuntimeHandler) for handler in target.handlers))

    def testBoundedContextRedactsSecretsAndDoesNotCallRepr(self):
        class HostileValue:
            def __repr__(self):
                raise AssertionError("Debug summaries must not call arbitrary repr")

        session = self.startSession(debug=True)
        session.record(
            "bounded_context",
            data={"token": "do-not-store", "authorization": "bearer-secret", "value": HostileValue()},
            large="x" * 2000,
        )
        session.close()
        text = session.paths["runtime"].read_text(encoding="utf-8")
        self.assertNotIn("do-not-store", text)
        self.assertNotIn("bearer-secret", text)
        self.assertNotIn("x" * 2000, text)
        self.assertIn("<redacted>", text)
        self.assertIn("<HostileValue>", text)

    def testNativeDefaultsAndExplicitSinkAreRecordedWithoutTraceReset(self):
        session = self.startSession(debug=True)
        native = self.nativeModule()
        self.assertTrue(session.applyNative(native))
        native.set_logger_sink.assert_called_once_with("file", str(session.paths["native"]))
        self.assertTrue(session.configureTrace(native))
        self.assertEqual("tail", session.manifest["channels"]["gameplay"]["retention"])
        self.assertTrue(session.applyNative(native, sink="disabled"))
        self.assertEqual("disabled", session.manifest["channels"]["native"]["status"])
        session.finish()
        session.close()
        manifest = json.loads(session.paths["manifest"].read_text(encoding="utf-8"))
        self.assertEqual("completed", manifest["outcome"])
        self.assertEqual("/compiled/_game.so", manifest["nativeModule"])

    def testExplicitPlaytestEnvironmentIsPreserved(self):
        os.environ.update(GAME_PLAYTEST_TRACE="0", GAME_PLAYTEST_TRACE_FILE="authored.jsonl")
        session = self.startSession(debug=True)
        native = self.nativeModule()
        native.playtest_trace_enabled = lambda: False
        self.assertFalse(session.configureTrace(native))
        self.assertEqual("0", os.environ["GAME_PLAYTEST_TRACE"])
        self.assertEqual("authored.jsonl", os.environ["GAME_PLAYTEST_TRACE_FILE"])
        self.assertNotIn("GAME_PLAYTEST_TRACE_RETAIN_RECENT", os.environ)
        self.assertEqual("environment", session.manifest["channels"]["gameplay"]["source"])
        self.assertEqual("disabled", session.manifest["channels"]["gameplay"]["status"])

    def testPreloadedNativeModuleAppliesEnvironmentOnceAndKeepsLaterHistory(self):
        native = self.nativeModule()
        state = {"enabled": False, "events": []}

        def configureFromEnvironment():
            state["enabled"] = True
            state["target"] = os.environ["GAME_PLAYTEST_TRACE_FILE"]
            state["events"].clear()

        native.playtest_trace_enabled = lambda: state["enabled"]
        native.configure_playtest_trace_from_env = mock.Mock(side_effect=configureFromEnvironment)
        with mock.patch.dict(sys.modules, {"_game": native}):
            session = self.startSession(debug=True)
            self.assertFalse(state["enabled"])
            self.assertTrue(session.configureTrace(native))
            self.assertEqual(str(session.paths["gameplay"]), state["target"])
            state["events"].append("gameplay_after_configuration")
            self.assertTrue(session.applyNative(native))
            self.assertTrue(session.configureTrace(native))
            self.assertTrue(session.applyNative(native))
            self.assertTrue(session.configureTrace(native))
            native.configure_playtest_trace_from_env.assert_called_once_with()
            self.assertEqual(["gameplay_after_configuration"], state["events"])

    def testFreshNativeImportPreservesStartupHistory(self):
        native = self.nativeModule()
        startup_events = ["native_import_event"]
        native.configure_playtest_trace_from_env = mock.Mock(side_effect=startup_events.clear)
        with mock.patch.dict(sys.modules):
            sys.modules.pop("_game", None)
            session = self.startSession(debug=True)
            sys.modules["_game"] = native
            self.assertTrue(session.configureTrace(native))
            self.assertTrue(session.configureTrace(native))
            native.configure_playtest_trace_from_env.assert_not_called()
            self.assertEqual(["native_import_event"], startup_events)

    def testNewSessionRedirectsTheSamePreloadedModuleToItsOwnTrace(self):
        native = self.nativeModule()
        configured_targets = []
        native.configure_playtest_trace_from_env = mock.Mock(
            side_effect=lambda: configured_targets.append(os.environ["GAME_PLAYTEST_TRACE_FILE"])
        )
        with mock.patch.dict(sys.modules, {"_game": native}):
            first = self.startSession(debug=True)
            self.assertTrue(first.configureTrace(native))
            first.close()
            second = self.startSession(debug=True)
            self.assertTrue(second.configureTrace(native))
            self.assertTrue(second.configureTrace(native))
            self.assertNotEqual(first.runDir, second.runDir)
            self.assertEqual([str(first.paths["gameplay"]), str(second.paths["gameplay"])], configured_targets)
            self.assertEqual(2, native.configure_playtest_trace_from_env.call_count)

    def testPreloadedModuleReceivesExplicitTraceEnvironmentUnchanged(self):
        native = self.nativeModule()
        expected = {
            "GAME_PLAYTEST_TRACE": "0",
            "GAME_PLAYTEST_TRACE_FILE": "authored-history.jsonl",
            "GAME_PLAYTEST_TRACE_RETAIN_RECENT": "0",
        }
        os.environ.update(expected)
        observed = []
        native.configure_playtest_trace_from_env = mock.Mock(
            side_effect=lambda: observed.append({key: os.environ[key] for key in expected})
        )
        native.playtest_trace_enabled = lambda: False
        with mock.patch.dict(sys.modules, {"_game": native}):
            session = self.startSession(debug=True)
            self.assertFalse(session.configureTrace(native))
            self.assertFalse(session.configureTrace(native))
            native.configure_playtest_trace_from_env.assert_called_once_with()
            self.assertEqual([expected], observed)
            self.assertEqual("environment", session.manifest["channels"]["gameplay"]["source"])
            self.assertEqual("disabled", session.manifest["channels"]["gameplay"]["status"])

    def testFailedPreloadedTraceConfigurationDoesNotRetryOrClaimSuccess(self):
        native = self.nativeModule()
        native.configure_playtest_trace_from_env = mock.Mock(side_effect=RuntimeError("native configuration failed"))
        with mock.patch.dict(sys.modules, {"_game": native}), redirect_stderr(io.StringIO()):
            session = self.startSession(debug=True)
            self.assertFalse(session.configureTrace(native))
            self.assertFalse(session.configureTrace(native))
            native.configure_playtest_trace_from_env.assert_called_once_with()
            self.assertEqual("unavailable", session.manifest["channels"]["gameplay"]["status"])

    def testUnavailableDirectoryDoesNotPreventApplicationStartup(self):
        blocker = self.root / "file"
        blocker.write_text("retained", encoding="utf-8")
        warnings = io.StringIO()
        with redirect_stderr(warnings):
            session = game_diagnostics.startSession(
                repo_root=self.root,
                build_dir=self.root,
                entrypoint="test",
                debug=True,
                debug_dir=blocker,
            )
            native = self.nativeModule()
            self.assertFalse(session.applyNative(native))
            self.assertIs(session, game_diagnostics.currentSession())
            game_tree = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
            bootstrap_guard = next(
                node
                for node in game_tree.body
                if isinstance(node, ast.If)
                and any(
                    isinstance(child, ast.Attribute) and child.attr == "currentSession" for child in ast.walk(node.test)
                )
            )
            bootstrap = compile(ast.Module(body=[bootstrap_guard], type_ignores=[]), str(ROOT / "res/game.py"), "exec")
            namespace = {"_game_diagnostics": game_diagnostics, "set_logger_sink": native.set_logger_sink}
            exec(bootstrap, namespace)
            native.set_logger_sink.assert_called_once_with("stderr", None)
            self.assertEqual("1", os.environ["GAME_PLAYTEST_TRACE"])
            self.assertEqual("", os.environ["GAME_PLAYTEST_TRACE_FILE"])
            self.assertEqual("1", os.environ["GAME_PLAYTEST_TRACE_RETAIN_RECENT"])
            self.assertTrue(session.configureTrace(self.nativeModule()))
            self.assertEqual("memory_only", session.manifest["channels"]["gameplay"]["status"])
            session.record("ignored")
            session.close()
            exec(bootstrap, namespace)
            native.set_logger_sink.assert_called_with("disabled", None)
        self.assertEqual("retained", blocker.read_text(encoding="utf-8"))
        self.assertEqual(1, warnings.getvalue().count("Debug diagnostics (startup)"))
        self.assertNotIn("GAME_DEBUG", os.environ)

    def testRuntimeAndManifestFailuresWarnOnceAndPreserveOriginalException(self):
        session = self.startSession(debug=True)
        handler = next(
            handler for _, handler in session._handlers if isinstance(handler, game_diagnostics._RuntimeHandler)
        )
        warnings = io.StringIO()
        with redirect_stderr(warnings), mock.patch.object(handler.stream, "write", side_effect=OSError("disk full")):
            session.record("first_failure")
            session.record("second_failure")
        self.assertEqual(1, warnings.getvalue().count("Debug diagnostics (runtime)"))
        self.assertEqual("unavailable", session.manifest["channels"]["runtime"]["status"])
        self.assertTrue(
            all(
                handler not in target.handlers
                for target, handler in session._handlers
                if isinstance(handler, game_diagnostics._RuntimeHandler)
            )
        )
        with redirect_stderr(warnings), mock.patch.object(Path, "write_text", side_effect=OSError("read only")):
            session.updateManifest(test="first")
            session.updateManifest(test="second")
            try:
                raise ValueError("original gameplay failure")
            except ValueError as error:
                session.finish(status="failed", error=error)
        self.assertEqual(1, warnings.getvalue().count("Debug diagnostics (manifest)"))
        self.assertEqual("ValueError", session.manifest["errorType"])
        self.assertEqual("failed", session.manifest["outcome"])

    def testMalformedPythonMessagesAndExceptionTracebacksKeepRuntimeLoggingActive(self):
        for source in ("message", "exception"):
            with self.subTest(source=source):
                session = self.startSession(debug=True)
                warnings = io.StringIO()
                try:
                    with redirect_stderr(warnings):
                        if source == "message":
                            logging.getLogger("game_diagnostics").warning("python-message-\ud800-\u0142\U0001f5fa")
                        else:
                            try:
                                raise ValueError("python-exception-\ud800-\u0142\U0001f5fa")
                            except ValueError as error:
                                session.recordException("malformed_exception", error)
                        session.record("after_malformed_" + source)
                    self.assertEqual("active", session.manifest["channels"]["runtime"]["status"])
                    text = session.paths["runtime"].read_text(encoding="utf-8")
                    self.assertIn("after_malformed_" + source, text)
                    self.assertIn(r"\ud800", text)
                    self.assertIn("\u0142\U0001f5fa", text)
                    self.assertEqual("", warnings.getvalue())
                finally:
                    session.close()

    def testPlayCapturesImportFailureBeforeGameBootstrap(self):
        tree = ast.parse((ROOT / "play.py").read_text(encoding="utf-8"))
        tree.body = tree.body[:-1]
        namespace = {"__file__": str(self.root / "play.py"), "__name__": "play_fixture"}
        exec(compile(tree, str(ROOT / "play.py"), "exec"), namespace)
        namespace["_bootstrap"] = lambda: None
        namespace["_find_build_dir"] = lambda root: self.root / "build"
        native = self.nativeModule()

        def importModule(name):
            self.assertTrue(game_diagnostics.currentSession().paths["runtime"].exists())
            self.assertEqual("1", os.environ["GAME_PLAYTEST_TRACE"])
            if name == "_game":
                return native
            raise ImportError("original game bootstrap failure")

        stdout = io.StringIO()
        with mock.patch("importlib.import_module", side_effect=importModule), redirect_stderr(io.StringIO()):
            with redirect_stdout(stdout), self.assertRaisesRegex(ImportError, "original game bootstrap failure"):
                namespace["main"](["--debug"])
        self.assertEqual("", stdout.getvalue())
        run = next((self.root / "build/logs/debug").iterdir())
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("failed", manifest["outcome"])
        self.assertIn("original game bootstrap failure", (run / "runtime.log").read_text(encoding="utf-8"))
        self.assertIsNone(game_diagnostics.currentSession())

    def testDialogFailureLogsTracebackAndKeepsFailClosedResult(self):
        tree = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
        dialog = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CDialog")
        report_failure = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_reportDialogFailure"
        )
        messages = []
        import traceback

        namespace = {
            "CDialogBase2": object,
            "_game_diagnostics": game_diagnostics,
            "_traceback": traceback,
            "record_playtest_trace": lambda *args, **kwargs: None,
            "playtest_object_ref": lambda obj: {"type": "BrokenDialog"},
            "logger": messages.append,
        }
        exec(
            compile(ast.Module(body=[report_failure, dialog], type_ignores=[]), str(ROOT / "res/game.py"), "exec"),
            namespace,
        )
        reporter = namespace["_reportDialogFailure"]
        self.assertIs(game_diagnostics, reporter.__defaults__[0])
        self.assertIs(traceback, reporter.__defaults__[1])
        self.assertNotIn("_game_diagnostics", reporter.__code__.co_names)
        self.assertNotIn("_traceback", reporter.__code__.co_names)

        class BrokenDialog(namespace["CDialog"]):
            def brokenAction(self):
                raise RuntimeError("original action failure")

            def brokenCondition(self):
                raise ValueError("original condition failure")

        instance = BrokenDialog()
        session = self.startSession(debug=True)
        self.assertFalse(instance.invokeAction("brokenAction"))
        self.assertFalse(instance.invokeCondition("brokenCondition"))
        session.close()
        text = session.paths["runtime"].read_text(encoding="utf-8")
        for message in ("original action failure", "original condition failure", "Traceback", "brokenAction"):
            self.assertIn(message, text)
            self.assertIn(message, "\n".join(messages))

        class BrokenStringError(Exception):
            def __str__(self):
                raise RuntimeError("exception text failed")

        class BrokenStringDialog(namespace["CDialog"]):
            def brokenAction(self):
                raise BrokenStringError()

        self.assertFalse(BrokenStringDialog().invokeAction("brokenAction"))

    def testOneFileFailureKeepsOtherChannelsWorking(self):
        original_touch = Path.touch

        def touch(path, *args, **kwargs):
            if path.name == "gameplay.jsonl":
                raise PermissionError("gameplay file blocked")
            return original_touch(path, *args, **kwargs)

        with mock.patch.object(Path, "touch", touch):
            session = self.startSession(debug=True)
        self.assertTrue(session.paths["native"].exists())
        session.record("remaining_channel_works")
        self.assertIn("remaining_channel_works", session.paths["runtime"].read_text(encoding="utf-8"))
        self.assertEqual("1", os.environ["GAME_PLAYTEST_TRACE"])
        self.assertEqual("", os.environ["GAME_PLAYTEST_TRACE_FILE"])
        self.assertTrue(session.configureTrace(self.nativeModule()))
        self.assertEqual("memory_only", session.manifest["channels"]["gameplay"]["status"])
        self.assertTrue(session.applyNative(self.nativeModule()))

    def testNativeFileFailureFallsBackToStderr(self):
        session = self.startSession(debug=True)
        native = self.nativeModule()
        with redirect_stderr(io.StringIO()), mock.patch.object(Path, "open", side_effect=PermissionError("blocked")):
            self.assertFalse(session.applyNative(native))
        native.set_logger_sink.assert_called_once_with("stderr", None)
        self.assertEqual("stderr", session.manifest["channels"]["native"]["effectiveSink"])

    def testSilentNativeFileFallbackIsDetectedByMarkerVerification(self):
        session = self.startSession(debug=True)
        native = self.nativeModule()
        self.assertTrue(session.applyNative(native))
        native.logger = mock.Mock()
        with redirect_stderr(io.StringIO()):
            self.assertFalse(session.applyNative(native))
        self.assertTrue(native.logger.called)
        native.set_logger_sink.assert_called_with("stderr", None)
        self.assertEqual("unavailable", session.manifest["channels"]["native"]["status"])
        self.assertEqual("stderr", session.manifest["channels"]["native"]["effectiveSink"])

    def testNativeModuleWithoutMarkerApiIsReportedAsUnverified(self):
        session = self.startSession(debug=True)
        native = self.nativeModule()
        del native.logger
        self.assertTrue(session.applyNative(native))
        self.assertEqual("unverified", session.manifest["channels"]["native"]["status"])

    def testExplicitTracePathValueIsResolvedFromRuntimeWorkingDirectory(self):
        for target in ("authored-history.jsonl", "True", "On", "Enabled"):
            with self.subTest(target=target):
                os.environ["GAME_PLAYTEST_TRACE"] = target
                session = self.startSession(debug=True)
                try:
                    session.configureTrace(self.nativeModule())
                    channel = session.manifest["channels"]["gameplay"]
                    self.assertEqual(target, channel["target"])
                    self.assertEqual(str(Path(target).resolve()), channel["path"])
                finally:
                    session.close()


if __name__ == "__main__":
    unittest.main()
