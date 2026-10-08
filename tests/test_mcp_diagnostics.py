# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

from concurrent.futures import ThreadPoolExecutor
import io
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import mcp


class McpDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.server = mcp.EngineMcpServer(Path.cwd(), Path.cwd())
        self.records = []
        self.server._emit_log = lambda **fields: self.records.append(fields)
        self.server.exports["echo"] = mcp.ExportedCallable("echo", "test", "echo", lambda value=None: value, "()")

    def call(self, tool, arguments=None, *, request_id=7, session_id=None):
        return self.server._call_tool(
            {"name": tool, "arguments": arguments or {}},
            transport="http" if session_id else "stdio",
            session_id=session_id,
            request_id=request_id,
        )

    def toolRecords(self):
        return [record["data"] for record in self.records if record["logger_name"] == "tools"]

    def testEveryToolBranchHasOneCorrelatedCompletion(self):
        success = {"isError": False, "structuredContent": {"ok": True}}
        with (
            patch.object(self.server, "_simulation_run", return_value=success),
            patch.object(self.server, "_map_design_brief", return_value=success),
        ):
            for name, arguments in (
                ("engine_list", {}),
                ("engine_call", {"name": "echo", "args": ["value"]}),
                ("engine_handle_call", {"handle": "missing", "method": "getName"}),
                ("engine_release_handles", {"handles": []}),
                ("simulation_run", {"map": "test"}),
                ("map_design_brief", {"map_name": "test"}),
            ):
                self.call(name, arguments)
        records = self.toolRecords()
        self.assertEqual(12, len(records))
        for start, end in zip(records[::2], records[1::2]):
            self.assertEqual("tool call started", start["message"])
            self.assertEqual(start["invocation"], end["invocation"])
            self.assertEqual(7, end["requestId"])
            self.assertGreaterEqual(end["elapsedMs"], 0)
            self.assertIn("isError", end)
        self.assertEqual("echo", records[2]["name"])
        self.assertEqual("getName", records[4]["method"])
        self.assertTrue(records[5]["isError"])
        self.assertEqual(6, len({record["invocation"] for record in records}))

    def testProtocolAndUnexpectedErrorsCompleteBeforePropagating(self):
        with self.assertRaises(mcp.ProtocolError):
            self.call("unknown")
        with self.assertRaises(mcp.ProtocolError):
            self.server._call_tool({"name": "engine_call", "arguments": []}, "stdio", None, request_id=8)
        with patch.object(self.server, "_dispatch_tool", side_effect=RuntimeError("unexpected")):
            with self.assertRaises(RuntimeError):
                self.call("engine_list")
        records = self.toolRecords()
        self.assertEqual(6, len(records))
        self.assertEqual(-32602, records[1]["error"]["code"])
        self.assertEqual(8, records[3]["requestId"])
        self.assertEqual("RuntimeError", records[5]["error"]["type"])
        self.assertTrue(all(record["isError"] for record in records[1::2]))

    def testReturnedEngineExceptionIsLoggedAsFailure(self):
        def fail():
            raise ValueError("synthetic engine failure")

        self.server.exports["fail"] = mcp.ExportedCallable("fail", "test", "fail", fail, "()")
        result = self.call("engine_call", {"name": "fail"})
        self.assertTrue(result["isError"])
        completion = self.toolRecords()[-1]
        self.assertEqual("tool call failed", completion["message"])
        self.assertEqual("synthetic engine failure", completion["error"])
        self.assertIn("ValueError: synthetic engine failure", completion["traceback"])
        self.assertEqual("error", self.records[-1]["level"])

    def testFailingDiagnosticHandlersPreserveResultsAndOriginalExceptions(self):
        with (
            patch.object(self.server, "_emit_log", side_effect=OSError("log channel unavailable")),
            patch.object(mcp.logger, "debug", side_effect=OSError("debug channel unavailable")),
            patch.object(mcp.logger, "isEnabledFor", return_value=True),
        ):
            self.assertFalse(self.call("engine_list")["isError"])
            with self.assertRaises(mcp.ProtocolError) as raised:
                self.call("unknown")
            self.assertEqual(-32602, raised.exception.code)

    def testConcurrentSessionsAndReusedRequestIdsHaveUniqueInvocations(self):
        sessions = [
            self.server._handle_initialize(1, {"protocolVersion": mcp.LATEST_PROTOCOL_VERSION}, "http").session_id
            for _ in range(2)
        ]
        barrier = threading.Barrier(4)

        def echo(value):
            barrier.wait(timeout=5)
            return value

        self.server.exports["echo"].callable_obj = echo
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    self.call, "engine_call", {"name": "echo", "args": [index]}, session_id=sessions[index % 2]
                )
                for index in range(4)
            ]
            self.assertEqual(list(range(4)), [future.result()["structuredContent"]["result"] for future in futures])
        records = self.toolRecords()
        starts = [record for record in records if record["message"] == "tool call started"]
        self.assertEqual(4, len({record["invocation"] for record in starts}))
        self.assertEqual(2, len({record["session"] for record in starts}))
        self.assertTrue(all(record["requestId"] == 7 for record in starts))
        serialized = json.dumps(records)
        for session_id in sessions:
            self.assertNotIn(session_id, serialized)
        for start in starts:
            matches = [record for record in records if record["invocation"] == start["invocation"]]
            self.assertEqual(2, len(matches))
            self.assertEqual(matches[0]["session"], matches[1]["session"])

    def testRequestIdFlowsFromJsonRpcWithoutInspectingEngineObjects(self):
        self.server.stdio_state = mcp.ConnectionState("stdio", mcp.LATEST_PROTOCOL_VERSION, initialized=True)
        response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": "client-9", "method": "tools/call", "params": {"name": "engine_list"}},
            "stdio",
            None,
        )
        self.assertEqual("client-9", response.response["id"])
        self.assertEqual("client-9", self.toolRecords()[-1]["requestId"])

    def testPreviewIsBoundedRedactedAndNeverCallsReprOrGetters(self):
        class Dangerous:
            def __repr__(self):
                raise AssertionError("repr must not run")

            def __getattribute__(self, name):
                raise AssertionError("getters must not run")

        cycle = []
        cycle.append(cycle)
        value = {
            "authorization": "bearer-secret",
            "nested": {"session_id": "session-secret", "api_key": "api-secret", "password": "password-secret"},
            "object": Dangerous(),
            "cycle": cycle,
            "unicode": "\U0001f5fa\u0142" * 5000,
            "wide": ["\u2603" * 1000] * 2000,
        }
        result = self.server._redact_trace_value(value)
        encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.assertLessEqual(len(encoded), mcp.MAX_DIAGNOSTIC_BYTES)
        self.assertEqual(encoded.decode("utf-8").encode("utf-8"), encoded)
        for secret in ("bearer-secret", "session-secret", "api-secret", "password-secret"):
            self.assertNotIn(secret.encode(), encoded)
        self.assertIn(b"<redacted>", encoded)
        with (
            patch.object(self.server, "_dispatch_tool", return_value={"isError": False}),
            self.assertLogs(mcp.logger, "DEBUG"),
        ):
            self.call("engine_list", value)

    def testStructuredResultPreviewDoesNotLeakDuplicateSerializedSecrets(self):
        result = {
            "content": [{"type": "text", "text": '{"token": "duplicate-secret"}'}],
            "structuredContent": {"token": "duplicate-secret"},
        }
        rendered = json.dumps(self.server._redact_trace_value(result))
        self.assertNotIn("duplicate-secret", rendered)
        self.assertIn("structuredContent", rendered)

    def testRawTraceIsIndependentAndRedactsTopLevelSessionId(self):
        with self.assertNoLogs(mcp.logger, "DEBUG"):
            self.server._trace_message(transport="http", direction="recv", payload={"ok": True})
        self.server.trace_messages = True
        with self.assertLogs(mcp.logger, "DEBUG") as captured:
            self.server._trace_message(
                transport="http",
                direction="recv",
                session_id="real-session-secret",
                payload={"token": "real-token-secret", "text": "\u0141\U0001f5fa" * 2000},
            )
        rendered = "\n".join(captured.output)
        self.assertNotIn("real-session-secret", rendered)
        self.assertNotIn("real-token-secret", rendered)
        payload = json.loads(captured.records[0].getMessage().removeprefix("trace "))
        self.assertEqual("<redacted>", payload["sessionId"])
        self.assertLessEqual(len(json.dumps(payload, ensure_ascii=False).encode("utf-8")), mcp.MAX_DIAGNOSTIC_BYTES)

    def testFailedPythonLogChannelKeepsProtocolNotificationsUsable(self):
        server = mcp.EngineMcpServer(Path.cwd(), Path.cwd(), trace_messages=True)
        server.stdio_state = mcp.ConnectionState("stdio", mcp.LATEST_PROTOCOL_VERSION, initialized=True)
        stdout = io.StringIO()
        with (
            patch.object(mcp.sys, "stdout", stdout),
            patch.object(mcp.logger, "log", side_effect=OSError("unavailable")),
            patch.object(mcp.logger, "debug", side_effect=OSError("unavailable")),
        ):
            server._emit_log("stdio", None, "info", "tools", {"message": "still available"})
        notification = json.loads(stdout.getvalue())
        self.assertEqual("notifications/message", notification["method"])
        self.assertEqual("still available", notification["params"]["data"]["message"])

    def testDebugLoggingLeavesStdioStdoutAsJsonRpc(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        root = logging.getLogger()
        old_handlers, old_level = root.handlers[:], root.level
        old_server_level = mcp.logger.level
        root.handlers = []
        server = mcp.EngineMcpServer(Path.cwd(), Path.cwd(), trace_messages=True)
        try:
            with patch.object(mcp.sys, "stdout", stdout), patch.object(mcp.sys, "stderr", stderr):
                mcp.configure_logging("DEBUG", trace_messages=True)
                server._trace_message(transport="stdio", direction="recv", payload={"id": 3})
                result = server._call_tool({"name": "engine_list"}, "stdio", None, request_id=3)
                server._write_stdio_message({"jsonrpc": "2.0", "id": 3, "result": result})
            self.assertEqual(1, len(stdout.getvalue().splitlines()))
            self.assertEqual(3, json.loads(stdout.getvalue())["id"])
            self.assertIn("tool call completed", stderr.getvalue())
            self.assertIn("trace", stderr.getvalue())
        finally:
            for handler in root.handlers:
                handler.close()
            root.handlers, root.level = old_handlers, old_level
            mcp.logger.setLevel(old_server_level)

    def testBuildOutputUsesStderrOnlyForStdio(self):
        for stdio in (False, True):
            with self.subTest(stdio=stdio):
                stdout, stderr = io.StringIO(), io.StringIO()

                def run(command, **options):
                    self.assertEqual("cmake", command[0])
                    self.assertTrue(options["check"])
                    print("synthetic-build-progress", file=options.get("stdout"))

                with (
                    patch.object(mcp.sys, "stdout", stdout),
                    patch.object(mcp.sys, "stderr", stderr),
                    patch.object(mcp.subprocess, "run", side_effect=run),
                ):
                    self.server.build_extension(stdio=stdio)
                self.assertEqual("" if stdio else "synthetic-build-progress\n", stdout.getvalue())
                self.assertEqual("synthetic-build-progress\n" if stdio else "", stderr.getvalue())

    def testStdioBuildFlagIsForwardedByStartup(self):
        builder = unittest.mock.Mock()
        server = types.SimpleNamespace(
            build_extension=builder,
            import_modules=lambda: None,
            inspect_and_export=lambda: None,
            serve_stdio=lambda: None,
        )
        with (
            patch.object(mcp.sys, "argv", ["mcp.py", "--stdio", "--build", "--native-log-sink", "disabled"]),
            patch.dict(os.environ, {}, clear=True),
            patch.object(mcp.game_diagnostics, "startSession", return_value=None),
            patch.object(mcp, "configure_logging"),
            patch.object(mcp, "EngineMcpServer", return_value=server),
        ):
            self.assertEqual(0, mcp.main())
        builder.assert_called_once_with(stdio=True)

    def testStdioRejectsNativeAndGameplayStdout(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "reserves stdout"):
                mcp.validate_stdio_diagnostics("stdout")
            for settings in (
                {"GAME_PLAYTEST_TRACE": "stdout"},
                {"GAME_PLAYTEST_TRACE": "1", "GAME_PLAYTEST_TRACE_FILE": "stdout"},
            ):
                with patch.dict(os.environ, settings, clear=True):
                    with self.assertRaisesRegex(ValueError, "reserves stdout"):
                        mcp.validate_stdio_diagnostics("disabled")
            with patch.dict(os.environ, {"GAME_PLAYTEST_TRACE": "0", "GAME_PLAYTEST_TRACE_FILE": "stdout"}, clear=True):
                mcp.validate_stdio_diagnostics("disabled")

    def testNativeAndTraceApplyBeforeGameWithNativeRestoreAfterwards(self):
        events = []
        manifests = []
        diagnostics = types.SimpleNamespace(
            applyNative=lambda module, **settings: events.append(("native", settings)),
            configureTrace=lambda module: events.append(("trace", {})),
            updateManifest=lambda **fields: manifests.append(fields),
        )
        native = types.SimpleNamespace(__file__="compiled/Release/_game.pyd")
        game = types.SimpleNamespace(__file__="resources/game.py")

        def importModule(name):
            events.append((name, {}))
            return native if name == "_game" else game

        server = mcp.EngineMcpServer(
            Path.cwd(), Path.cwd(), diagnostics=diagnostics, native_log_sink="disabled", build_config="Release"
        )
        with patch.object(mcp.importlib, "import_module", side_effect=importModule), patch.object(mcp.os, "chdir"):
            server.import_modules()
        self.assertEqual(["_game", "native", "trace", "game", "native"], [event[0] for event in events])
        self.assertEqual("disabled", events[1][1]["sink"])
        self.assertEqual("resources/game.py", manifests[0]["gameModule"])
        self.assertEqual("compiled/Release/_game.pyd", manifests[0]["nativeModule"])
        self.assertEqual("Release", manifests[0]["buildConfig"])
        self.assertEqual(str(Path.cwd()), manifests[0]["workingDirectory"])
        self.assertEqual([str(Path.cwd() / "Release")], manifests[0]["extensionSearchDirs"])

    def testUnavailableManifestChannelDoesNotFailModuleImport(self):
        diagnostics = types.SimpleNamespace(
            applyNative=lambda module, **settings: None,
            configureTrace=lambda module: None,
            updateManifest=unittest.mock.Mock(side_effect=OSError("unavailable manifest")),
        )
        server = mcp.EngineMcpServer(Path.cwd(), Path.cwd(), diagnostics=diagnostics)
        with patch.object(mcp.importlib, "import_module", return_value=object()), patch.object(mcp.os, "chdir"):
            server.import_modules()
        self.assertIsNotNone(server.game_module)

    def testDebugStartupPreservesExplicitSettingsAndDoesNotEnableRawTrace(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-diagnostics-") as directory:
            root = Path(directory)
            calls = []
            session = types.SimpleNamespace(
                nativePath=root / "run" / "native.log",
                updateManifest=lambda **fields: calls.append(("manifest", fields)),
                finish=lambda **fields: calls.append(("finish", fields)),
                close=lambda: calls.append(("close", {})),
            )
            server = types.SimpleNamespace(
                import_modules=lambda: calls.append(("import", {})),
                inspect_and_export=lambda: None,
                serve_stdio=lambda: None,
            )
            argv = [
                "mcp.py",
                "--stdio",
                "--repo-root",
                directory,
                "--debug",
                "--log-level",
                "INFO",
                "--native-log-sink",
                "disabled",
            ]
            with (
                patch.object(mcp.sys, "argv", argv),
                patch.dict(os.environ, {}, clear=True),
                patch.object(
                    mcp.game_diagnostics,
                    "startSession",
                    side_effect=lambda **fields: calls.append(("start", fields)) or session,
                ),
                patch.object(mcp, "configure_logging") as configure,
                patch.object(mcp, "EngineMcpServer", return_value=server) as constructor,
            ):
                self.assertEqual(0, mcp.main())
            configure.assert_called_once_with("INFO", log_sink="stderr", trace_messages=False)
            self.assertEqual("disabled", constructor.call_args.kwargs["native_log_sink"])
            self.assertIsNone(constructor.call_args.kwargs["native_log_path"])
            self.assertFalse(constructor.call_args.kwargs["trace_messages"])
            self.assertTrue(calls[0][1]["debug"])
            self.assertLess([name for name, _ in calls].index("start"), [name for name, _ in calls].index("import"))
            self.assertEqual(("finish", {"status": "complete"}), calls[-2])
            self.assertEqual("close", calls[-1][0])

    def testDebugStartupFailureFinishesAndClosesSession(self):
        session = types.SimpleNamespace(nativePath=Path("unused"), updateManifest=lambda **fields: None)
        session.finish = unittest.mock.Mock()
        session.close = unittest.mock.Mock()
        with (
            patch.object(mcp.sys, "argv", ["mcp.py", "--stdio", "--debug", "--native-log-sink", "stdout"]),
            patch.object(mcp.game_diagnostics, "startSession", return_value=session),
            patch.object(mcp, "configure_logging"),
        ):
            with self.assertRaises(ValueError):
                mcp.main()
        self.assertEqual("failed", session.finish.call_args.kwargs["status"])
        self.assertIsInstance(session.finish.call_args.kwargs["error"], ValueError)
        session.close.assert_called_once_with()

    def runRealDebugStartup(self, *arguments):
        original_server = mcp.EngineMcpServer
        stdout, stderr = io.StringIO(), io.StringIO()
        root_logger = logging.getLogger()
        old_handlers, old_level = root_logger.handlers[:], root_logger.level
        old_server_level = mcp.logger.level
        root_logger.handlers = []

        def server(**settings):
            instance = original_server(**settings)
            instance.import_modules = lambda: None
            instance.inspect_and_export = lambda: None

            def serve():
                instance._call_tool({"name": "engine_list"}, "stdio", None, request_id=9)
                mcp.logger.info("explicit-info-marker")
                mcp.logger.warning("visible-warning-marker")
                mcp.logger.error("visible-error-marker")

            instance.serve_stdio = serve
            return instance

        try:
            with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-console-") as directory:
                argv = [
                    "mcp.py",
                    "--stdio",
                    "--debug",
                    "--repo-root",
                    directory,
                    "--debug-dir",
                    str(Path(directory) / "runs"),
                    *arguments,
                ]
                with (
                    patch.object(mcp.sys, "argv", argv),
                    patch.object(mcp.sys, "stdout", stdout),
                    patch.object(mcp.sys, "stderr", stderr),
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(mcp, "EngineMcpServer", side_effect=server),
                ):
                    self.assertEqual(0, mcp.main())
                runs = list((Path(directory) / "runs").iterdir())
                self.assertEqual(1, len(runs))
                return (runs[0] / "runtime.log").read_text(encoding="utf-8"), stdout.getvalue(), stderr.getvalue()
        finally:
            for handler in root_logger.handlers:
                handler.close()
            root_logger.handlers, root_logger.level = old_handlers, old_level
            mcp.logger.setLevel(old_server_level)

    def testDefaultDebugKeepsVerboseFileAndBriefConsole(self):
        runtime, stdout, stderr = self.runRealDebugStartup()
        self.assertEqual("", stdout)
        self.assertIn("Debug logs:", stderr)
        self.assertIn("visible-warning-marker", stderr)
        self.assertIn("visible-error-marker", stderr)
        for marker in (
            "tool call started",
            "tool call completed",
            "tool arguments",
            "tool result",
            "explicit-info-marker",
        ):
            self.assertIn(marker, runtime)
            self.assertNotIn(marker, stderr)

    def testExplicitLogLevelControlsFileAndConsole(self):
        for level in ("INFO", "ERROR"):
            with self.subTest(level=level):
                runtime, stdout, stderr = self.runRealDebugStartup("--log-level", level)
                self.assertEqual("", stdout)
                self.assertIn("visible-error-marker", runtime)
                self.assertIn("visible-error-marker", stderr)
                self.assertNotIn("tool arguments", runtime)
                self.assertNotIn("tool arguments", stderr)
                if level == "INFO":
                    self.assertIn("explicit-info-marker", runtime)
                    self.assertIn("explicit-info-marker", stderr)
                else:
                    self.assertNotIn("explicit-info-marker", runtime)
                    self.assertNotIn("explicit-info-marker", stderr)
                    self.assertNotIn("visible-warning-marker", runtime)
                    self.assertNotIn("visible-warning-marker", stderr)

    def testExplicitRawTracingKeepsVerboseConsole(self):
        runtime, stdout, stderr = self.runRealDebugStartup("--trace-messages")
        self.assertEqual("", stdout)
        self.assertIn("tool arguments", runtime)
        self.assertIn("tool arguments", stderr)

    def testUnavailableNativeDirectoryFallsBackWithoutBlockingStartup(self):
        calls = []
        session = types.SimpleNamespace(
            nativePath=Path("unavailable") / "run" / "native.log",
            updateManifest=lambda **fields: calls.append(fields),
            finish=lambda **fields: None,
            close=lambda: None,
        )
        server = types.SimpleNamespace(
            import_modules=lambda: None, inspect_and_export=lambda: None, serve_stdio=lambda: None
        )
        with (
            patch.object(mcp.sys, "argv", ["mcp.py", "--stdio", "--debug"]),
            patch.dict(os.environ, {}, clear=True),
            patch.object(mcp.game_diagnostics, "startSession", return_value=session),
            patch.object(mcp, "configure_logging"),
            patch.object(mcp.Path, "mkdir", side_effect=PermissionError("read only")),
            patch.object(mcp, "EngineMcpServer", return_value=server) as constructor,
            self.assertLogs(mcp.logger, "WARNING"),
        ):
            self.assertEqual(0, mcp.main())
        self.assertEqual("stderr", constructor.call_args.kwargs["native_log_sink"])
        self.assertIsNone(constructor.call_args.kwargs["native_log_path"])
        self.assertTrue(any(fields.get("nativeFileUnavailable") for fields in calls))


if __name__ == "__main__":
    unittest.main()
