# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import deque
from concurrent.futures import ThreadPoolExecutor
import http.client
import gc
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import textwrap
import threading
import time
import unittest
import weakref
from unittest.mock import patch

import mcp

ROOT = Path(__file__).resolve().parents[1]


def nativeHttpChildScript():
    return textwrap.dedent("""

        import faulthandler, json, sys, threading
        from pathlib import Path
        faulthandler.enable(file=sys.stderr, all_threads=True)
        import mcp
        server = mcp.EngineMcpServer(Path(sys.argv[1]), Path(sys.argv[2]),
                                    build_config=sys.argv[3] or None, native_log_sink='disabled')
        try:
            server.import_modules()
            server.inspect_and_export()
            httpd = mcp.EngineHttpServer(('127.0.0.1', 0), mcp.EngineHttpRequestHandler, server)
            serving = threading.Thread(target=httpd.serve_forever, daemon=True)
            serving.start()
            print('MCP_HTTP_READY ' + str(httpd.server_port), flush=True)
            sys.stdin.readline()
            # Leave the one-shot armed through native and interpreter finalization.
            faulthandler.dump_traceback_later(20, repeat=False, file=sys.stderr)
            print('MCP_HTTP_TEARDOWN_BEGIN', file=sys.stderr, flush=True)
            httpd.shutdown()
            httpd.server_close()
            serving.join()
            print('MCP_HTTP_HTTP_CLOSED', file=sys.stderr, flush=True)
        finally:
            server.close()
            print('MCP_HTTP_FIRST_SERVER_CLOSED', file=sys.stderr, flush=True)
        replacement = mcp.EngineMcpServer(Path(sys.argv[1]), Path(sys.argv[2]),
                                        build_config=sys.argv[3] or None, native_log_sink='disabled')
        try:
            replacement.import_modules()
            replacement.inspect_and_export()
            assert replacement._engine_owner is server._engine_owner
            def secondSession():
                game = replacement.game_module.CGameLoader.loadGame()
                replacement.game_module.CGameLoader.startGameWithPlayer(game, 'multilevel', 'Warrior')
                game.getMap().move()
                game.getContext().shutdown()
            replacement._engine_owner.run(secondSession)
        finally:
            replacement.close()
        print('MCP_HTTP_REOPENED', flush=True)
        print('MCP_HTTP_CLOSED', flush=True)
        threads = [{'name': t.name, 'ident': t.ident, 'daemon': t.daemon, 'alive': t.is_alive()}
                   for t in threading.enumerate()[:16]]
        print('MCP_HTTP_FINAL_THREADS ' + json.dumps(threads), file=sys.stderr, flush=True)
        print('MCP_HTTP_ENTERING_FINALIZATION', file=sys.stderr, flush=True)
        """)


def closeNativeHttpChild(proc, readers, stdout, stderr):
    timeout_error = None
    try:
        if proc.poll() is None:
            try:
                proc.stdin.write("close\n")
                proc.stdin.flush()
            except BrokenPipeError:
                pass
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired as error:
                timeout_error = error
                proc.kill()
                proc.wait(timeout=5)
    finally:
        for reader in readers:
            reader.join(timeout=5)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()
    if timeout_error is not None:
        raise AssertionError("native HTTP shutdown timed out:\n" + "".join(stdout) + "".join(stderr)) from timeout_error


def nativeBuildDirectory():
    default_build = "cmake-build-clangcl20-release" if os.name == "nt" else "cmake-build-gcc15-release"
    path = Path(os.environ.get("GAME_BUILD_DIR") or default_build)
    return (path if path.is_absolute() else ROOT / path).resolve()


class FakeLoop:
    def __init__(self):
        self.queue = queue.Queue()

    def invoke(self, callback):
        self.queue.put(callback)
        return True

    def run(self):
        for _ in range(self.queue.qsize()):
            self.queue.get_nowait()()


class HttpClient:
    def __init__(self, port):
        self.connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        self.session = None
        self.next_id = 1

    def request(self, method, params=None, *, notification=False, timeout=10):
        self.connection.timeout = timeout
        if self.connection.sock is not None:
            self.connection.sock.settimeout(timeout)
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            payload["id"] = self.next_id
            self.next_id += 1
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["MCP-Session-Id"] = self.session
            headers["MCP-Protocol-Version"] = mcp.LATEST_PROTOCOL_VERSION
        self.connection.request("POST", "/mcp", json.dumps(payload), headers)
        response = self.connection.getresponse()
        body = response.read()
        if not self.session:
            self.session = response.getheader("MCP-Session-Id")
        if notification:
            if response.status != 202 or body:
                raise AssertionError((response.status, body))
            return None
        if response.status != 200:
            raise AssertionError((response.status, body))
        result = json.loads(body)
        if "error" in result:
            raise AssertionError(result)
        return result["result"]

    def initialize(self):
        self.request("initialize", {"protocolVersion": mcp.LATEST_PROTOCOL_VERSION})
        self.request("notifications/initialized", notification=True)

    def tool(self, name, arguments, *, timeout=10):
        result = self.request("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)
        if result.get("isError"):
            raise AssertionError(result)
        return result["structuredContent"]

    def delete(self):
        self.connection.request("DELETE", "/mcp", headers={"MCP-Session-Id": self.session})
        response = self.connection.getresponse()
        body = response.read()
        if response.status != 204:
            raise AssertionError((response.status, body))

    def close(self):
        self.connection.close()


class McpEngineThreadTest(unittest.TestCase):
    def testNativeBuildDirectoryResolvesRelativeEnvironmentAgainstRepository(self):
        with patch.dict(os.environ, GAME_BUILD_DIR="relative-native-build"), patch.object(
            os, "getcwd", return_value=str(ROOT.parent)
        ):
            self.assertEqual((ROOT / "relative-native-build").resolve(), nativeBuildDirectory())

    def testRunnerKeepsMechanicsFastAndNativeHttpInGameplayAndCoverage(self):
        runner = sys.modules.get("__main__")
        if not hasattr(runner, "test_name_matches_suite"):
            import test as runner
        for class_name, selected, excluded in (
            ("McpEngineThreadTest", "fast", "gameplay"),
            ("McpHttpNativeRuntimeTest", "gameplay", "fast"),
        ):
            registered = getattr(runner, class_name)
            methods = unittest.defaultTestLoader.getTestCaseNames(registered)
            self.assertTrue(methods)
            for method in methods:
                name = f"{class_name}.{method}"
                for suite in (selected, "full", "coverage-safe"):
                    self.assertTrue(runner.test_name_matches_suite(name, suite), (name, suite))
                self.assertFalse(runner.test_name_matches_suite(name, excluded), (name, excluded))

    def testDifferentLiveHttpHandlersShareInvocationSerializationAndReleaseThread(self):
        events = []
        handlers = set()
        handler_lock = threading.Lock()

        class CGameObject:
            def __init__(self):
                self.owner = threading.get_ident()
                events.append(("created", self.owner))

            def __repr__(self):
                self.assertOwner()
                events.append(("serialized", threading.get_ident()))
                return "thread-affine-probe"

            def assertOwner(self):
                if self.owner != threading.get_ident():
                    raise RuntimeError("native engine called outside its owner thread")

            def getName(self):
                self.assertOwner()
                return str(self.owner)

            def __del__(self):
                events.append(("released", threading.get_ident()))

        class Handler(mcp.EngineHttpRequestHandler):
            def do_POST(self):
                with handler_lock:
                    handlers.add(threading.get_ident())
                super().do_POST()

        server = mcp.EngineMcpServer(ROOT, ROOT)
        server.exports["probe"] = mcp.ExportedCallable("probe", "test", "probe", CGameObject, "()")
        httpd = mcp.EngineHttpServer(("127.0.0.1", 0), Handler, server)
        serving = threading.Thread(target=httpd.serve_forever, daemon=True)
        serving.start()
        first = HttpClient(httpd.server_port)
        second = HttpClient(httpd.server_port)
        try:
            first.initialize()
            value = first.tool("engine_call", {"name": "probe"})["result"]
            second.session = first.session
            owner = second.tool("engine_handle_call", {"handle": value["__handle__"], "method": "getName"})["result"]
            self.assertEqual(str(events[0][1]), owner)
            self.assertEqual(2, len(handlers), "the first keep-alive handler must coexist with the second")
            self.assertNotIn(int(owner), handlers)
            self.assertEqual({"released": 1}, second.tool("engine_release_handles", {"handles": [value["__handle__"]]}))
            first.tool("engine_call", {"name": "probe"})
            second.delete()
            first.session = None
            first.initialize()
            first.tool("engine_call", {"name": "probe"})
        finally:
            first.close()
            second.close()
            httpd.shutdown()
            httpd.server_close()
            serving.join(timeout=5)
        self.assertEqual(3, sum(event == "released" for event, _ in events))
        self.assertEqual({events[0][1]}, {identity for _, identity in events})

    def testStdioUsesSameOwnerAndReleasesHandlesBeforeStoppingThread(self):
        released = []

        class CGameObject:
            def __init__(self):
                self.owner = threading.get_ident()

            def __del__(self):
                released.append((self.owner, threading.get_ident()))

        server = mcp.EngineMcpServer(ROOT, ROOT)
        server.exports["probe"] = mcp.ExportedCallable("probe", "test", "probe", CGameObject, "()")
        messages = [
            {"id": 1, "method": "initialize", "params": {"protocolVersion": mcp.LATEST_PROTOCOL_VERSION}},
            {"method": "notifications/initialized"},
            {"id": 2, "method": "tools/call", "params": {"name": "engine_call", "arguments": {"name": "probe"}}},
        ]
        stream = io.TextIOWrapper(
            io.BytesIO("".join(json.dumps({"jsonrpc": "2.0", **message}) + "\n" for message in messages).encode())
        )
        with patch.object(mcp.sys, "stdin", stream), patch.object(server, "_write_stdio_message"):
            server.serve_stdio()
        self.assertEqual(1, len(released))
        self.assertEqual(released[0][0], released[0][1])
        self.assertNotEqual(threading.get_ident(), released[0][0])
        self.assertTrue(
            server._engine_owner._thread.is_alive(), "the process singleton remains usable for another server"
        )

    def testCollectedServerReleasesOwnedObjectsOnPersistentEngineThread(self):
        released = []

        class CGameObject:
            def __init__(self):
                self.owner = threading.get_ident()

            def __del__(self):
                released.append((self.owner, threading.get_ident()))

        server = mcp.EngineMcpServer(ROOT, ROOT)
        owner = server._engine_owner
        server.exports["probe"] = mcp.ExportedCallable("probe", "test", "probe", CGameObject, "()")
        server._engine_call({"name": "probe"})
        reference = weakref.ref(server)
        del server
        gc.collect()
        owner.run(lambda: None)
        self.assertIsNone(reference())
        self.assertEqual([(owner._thread.ident, owner._thread.ident)], released)

    def testFullSseStreamDoesNotInterruptAnySessionOrStdioCleanup(self):
        released = []

        class CGameObject:
            def __del__(self):
                released.append(threading.get_ident())

        server = mcp.EngineMcpServer(ROOT, ROOT)
        self.addCleanup(server.close)
        server.exports["probe"] = mcp.ExportedCallable("probe", "test", "probe", CGameObject, "()")
        registries = [server._stdio_handles]
        full = queue.Queue(maxsize=1)
        full.put({"message": "occupied"})
        for index in range(2):
            session = server._handle_initialize(
                index, {"protocolVersion": mcp.LATEST_PROTOCOL_VERSION}, "http"
            ).session_id
            state = server.http_sessions[session]
            registries.append(state.handle_registry)
            if index == 0:
                state.streams["full"] = mcp.ClientStream("full", full)
        for registry in registries:
            server._engine_call({"name": "probe"}, registry)
        server.close()
        self.assertEqual([server._engine_owner._thread.ident] * 3, released)
        self.assertTrue(all(registry.closed and not registry.handles for registry in registries))
        self.assertIsNone(full.get_nowait())

    def testNativeOwnerSurvivesClosingAndReplacingServers(self):
        first = mcp.EngineMcpServer(ROOT, ROOT)
        identity = first._engine_owner.run(threading.get_ident)
        first.close()
        second = mcp.EngineMcpServer(ROOT, ROOT)
        self.addCleanup(second.close)
        self.assertIs(first._engine_owner, second._engine_owner)
        self.assertEqual(identity, second._engine_owner.run(threading.get_ident))

    def testExistingForeignNativeLoopIsRejectedWithRecoveryInstructions(self):
        owner = mcp.EngineOwner()
        self.addCleanup(owner.close, lambda: None)
        loop = FakeLoop()
        loop.isMainThread = lambda: False
        with self.assertRaisesRegex(RuntimeError, "fresh Python process"):
            owner.run(owner.attachNativeLoop, loop)
        self.assertIsNone(owner._native_loop)

    def testRejectedProgressDispatchSkipsQueuedWork(self):
        owner = mcp.EngineOwner()
        self.addCleanup(owner.close, lambda: None)
        loop = FakeLoop()
        loop.invoke = lambda callback: False
        owner.run(owner.attachNativeLoop, loop)
        entered, proceed = threading.Event(), threading.Event()
        calls = []

        def boundary():
            entered.set()
            if not proceed.wait(5):
                raise AssertionError("rejected-dispatch regression did not release its boundary")

        with ThreadPoolExecutor(max_workers=1) as caller:
            waiting = caller.submit(owner.run, boundary)
            self.assertTrue(entered.wait(5))
            try:
                with self.assertRaisesRegex(RuntimeError, "rejected MCP owner progress"):
                    owner.run(calls.append, "must not run")
            finally:
                proceed.set()
            waiting.result(timeout=5)
        owner.run(lambda: None)
        self.assertEqual([], calls)

    def testNativeBoundaryPumpsPendingReleaseWithoutPerpetualCallbacks(self):
        owner = mcp.EngineOwner()
        self.addCleanup(owner.close, lambda: None)
        loop = FakeLoop()
        owner.run(owner.attachNativeLoop, loop)
        entered, released = threading.Event(), threading.Event()
        identities = []

        def boundary():
            entered.set()
            deadline = time.monotonic() + 5
            while not released.is_set():
                if time.monotonic() >= deadline:
                    raise AssertionError("native boundary could not process concurrent release")
                loop.run()
                released.wait(0.001)
            identities.append(threading.get_ident())

        def release():
            identities.append(threading.get_ident())
            released.set()

        with ThreadPoolExecutor(max_workers=2) as callers:
            waiting = callers.submit(owner.run, boundary)
            self.assertTrue(entered.wait(5))
            callers.submit(owner.run, release).result(timeout=5)
            waiting.result(timeout=5)
        self.assertEqual([owner._thread.ident] * 2, identities)
        self.assertTrue(loop.queue.empty())

    def testNativeQueuePumpUsesBoundedSnapshotAndLateCallbacksBecomeInert(self):
        owner = mcp.EngineOwner()
        self.addCleanup(owner.close, lambda: None)
        loop = FakeLoop()
        owner.run(owner.attachNativeLoop, loop)
        events = []

        def record(index):
            events.append(index)
            if index == 0:
                owner.submit(events.append, "later")

        def boundary():
            for index in range(72):
                owner.submit(record, index)
            loop.run()
            self.assertEqual(list(range(64)), events)
            self.assertEqual(9, owner._queue.qsize())

        owner.run(boundary)
        owner.run(lambda: None)
        self.assertEqual([*range(72), "later"], events)
        self.assertLessEqual(loop.queue.qsize(), 1, "normal queued calls share one native progress ticket")
        owner.close(lambda: None)
        loop.run()
        self.assertTrue(loop.queue.empty(), "a callback left by a completed/closed boundary must not rearm")

    def testNestedNativeBoundaryCanRunReleaseAlreadyInThePumpSnapshot(self):
        owner = mcp.EngineOwner()
        self.addCleanup(owner.close, lambda: None)
        loop = FakeLoop()
        owner.run(owner.attachNativeLoop, loop)
        released = threading.Event()
        pending = []

        def nestedBoundary():
            deadline = time.monotonic() + 1
            while not released.is_set():
                if time.monotonic() >= deadline:
                    raise AssertionError("a captured release was stranded behind a nested modal boundary")
                loop.run()
                released.wait(0.001)

        def boundary():
            pending.append(owner.submit(nestedBoundary))
            pending.append(owner.submit(released.set))
            loop.run()

        owner.run(boundary)
        for future in pending:
            future.result(timeout=1)
        self.assertTrue(released.is_set())

    def testImportAndInspectionRunOnOwnerAndNestedCallsDoNotDeadlock(self):
        server = mcp.EngineMcpServer(ROOT, ROOT)
        self.addCleanup(server.close)
        identities = []
        scopes = []

        def inspectOwned(*, stdio=False):
            identities.append(threading.get_ident())
            scopes.append(stdio)

        with (
            patch.object(server, "_importModules", side_effect=lambda: identities.append(threading.get_ident())),
            patch.object(server, "_inspectAndExport", side_effect=inspectOwned),
        ):
            server.import_modules()
            server.inspect_and_export()
            server.inspect_and_export(stdio=True)
        nested = server._engine_owner.run(lambda: server._engine_owner.run(threading.get_ident))
        self.assertEqual([nested, nested, nested], identities)
        self.assertEqual([False, True], scopes)
        self.assertNotEqual(threading.get_ident(), nested)

    def testExceptionFramesReleaseOwnerOnlyObjectsBeforeForwarding(self):
        released = []
        owner = mcp.EngineOwner()
        self.addCleanup(owner.close, lambda: None)

        class Payload:
            def __del__(self):
                released.append(threading.get_ident())

        def fail():
            payload = Payload()
            raise ValueError("owner failure")

        with self.assertRaisesRegex(ValueError, "owner failure"):
            owner.run(fail)
        self.assertEqual([owner._thread.ident], released)

    def testNativeHttpChildKeepsDeferredThreadDumpArmedUntilFinalization(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        fault = SimpleNamespace(enable=Mock(), dump_traceback_later=Mock(), cancel_dump_traceback_later=Mock())
        context = SimpleNamespace(shutdown=Mock())
        game_map = SimpleNamespace(move=Mock())
        game = SimpleNamespace(getMap=lambda: game_map, getContext=lambda: context)
        loader = SimpleNamespace(loadGame=lambda: game, startGameWithPlayer=Mock())
        owner = SimpleNamespace(run=lambda callback: callback())
        servers = []

        class Server:
            def __init__(self, *args, **kwargs):
                self._engine_owner = owner
                self.game_module = SimpleNamespace(CGameLoader=loader)
                self.import_modules = Mock()
                self.inspect_and_export = Mock()
                self.close = Mock()
                servers.append(self)

        httpd = SimpleNamespace(server_port=12345, serve_forever=lambda: None, shutdown=Mock(), server_close=Mock())
        fake_mcp = SimpleNamespace(
            EngineMcpServer=Server, EngineHttpServer=lambda *args: httpd, EngineHttpRequestHandler=object
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.dict(sys.modules, {"mcp": fake_mcp, "faulthandler": fault}),
            patch.object(sys, "argv", ["child", str(ROOT), str(ROOT), ""]),
            patch.object(sys, "stdin", io.StringIO("close\n")),
            patch.object(sys, "stdout", stdout),
            patch.object(sys, "stderr", stderr),
        ):
            exec(nativeHttpChildScript(), {})
        fault.enable.assert_called_once_with(file=stderr, all_threads=True)
        fault.dump_traceback_later.assert_called_once_with(20, repeat=False, file=stderr)
        fault.cancel_dump_traceback_later.assert_not_called()
        self.assertTrue(all(server.close.call_count == 1 for server in servers))
        self.assertEqual(context.shutdown.call_count, 1)
        self.assertIn("MCP_HTTP_CLOSED", stdout.getvalue())
        self.assertIn("MCP_HTTP_TEARDOWN_BEGIN", stderr.getvalue())
        self.assertIn("MCP_HTTP_ENTERING_FINALIZATION", stderr.getvalue())
        threads_line = next(
            line for line in stderr.getvalue().splitlines() if line.startswith("MCP_HTTP_FINAL_THREADS ")
        )
        self.assertLessEqual(len(json.loads(threads_line.partition(" ")[2])), 16)

    def testNativeHttpShutdownTimeoutPreservesFailureAndClosesStreamsAfterDiagnosticsDrain(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        timeout = subprocess.TimeoutExpired(["native-child"], 30)
        proc = SimpleNamespace(
            poll=lambda: None,
            stdin=io.StringIO(),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            wait=Mock(side_effect=[timeout, -9]),
            kill=Mock(),
        )
        stdout, stderr = deque(["MCP_HTTP_CLOSED\n"], maxlen=80), deque(maxlen=80)
        reader = SimpleNamespace(join=Mock(side_effect=lambda **kwargs: stderr.append("native teardown stack\n")))
        original = TimeoutError("original modal response timed out")
        with self.assertRaisesRegex(AssertionError, "native HTTP shutdown timed out") as caught:
            try:
                raise original
            finally:
                closeNativeHttpChild(proc, [reader], stdout, stderr)
        self.assertIs(caught.exception.__cause__, timeout)
        self.assertIs(timeout.__context__, original)
        self.assertIn("native teardown stack", str(caught.exception))
        self.assertIn("MCP_HTTP_CLOSED", str(caught.exception))
        self.assertEqual([entry.kwargs for entry in proc.wait.call_args_list], [{"timeout": 30}, {"timeout": 5}])
        proc.kill.assert_called_once_with()
        reader.join.assert_called_once_with(timeout=5)
        self.assertTrue(all(stream.closed for stream in (proc.stdin, proc.stdout, proc.stderr)))

    def testNativeHttpSuccessfulShutdownKeepsThirtySecondBoundWithoutKilling(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        proc = SimpleNamespace(
            poll=lambda: None,
            stdin=io.StringIO(),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            wait=Mock(return_value=0),
            kill=Mock(),
        )
        closeNativeHttpChild(proc, [], deque(maxlen=80), deque(maxlen=80))
        proc.wait.assert_called_once_with(timeout=30)
        proc.kill.assert_not_called()
        self.assertTrue(all(stream.closed for stream in (proc.stdin, proc.stdout, proc.stderr)))

    def testCloseDrainsAcceptedCallsAndRejectsNewCalls(self):
        owner = mcp.EngineOwner()
        entered = threading.Event()
        proceed = threading.Event()
        closed = threading.Event()
        events = []

        def pending():
            entered.set()
            if not proceed.wait(5):
                raise AssertionError("shutdown regression failed to release pending work")
            events.append("call")

        def cleanup():
            events.append("cleanup")
            closed.set()

        with ThreadPoolExecutor(max_workers=2) as callers:
            call = callers.submit(owner.run, pending)
            self.assertTrue(entered.wait(5))
            closing = callers.submit(owner.close, cleanup)
            try:
                deadline = time.monotonic() + 5
                with owner._lock:
                    is_closed = owner._closed
                while not is_closed:
                    if time.monotonic() >= deadline:
                        self.fail("owner close did not reject admission before draining work")
                    closed.wait(0.001)
                    with owner._lock:
                        is_closed = owner._closed
                with self.assertRaisesRegex(RuntimeError, "has closed"):
                    owner.run(lambda: None)
            finally:
                proceed.set()
            call.result(timeout=5)
            closing.result(timeout=5)
        self.assertEqual(["call", "cleanup"], events)


class McpHttpNativeRuntimeTest(unittest.TestCase):
    def testSeparateLiveHttpConnectionsMoveAndReleaseRealSession(self):
        build_dir = nativeBuildDirectory()
        build_config = os.environ.get("GAME_BUILD_CONFIG") or None
        candidates = [build_dir, *(build_dir / name for name in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"))]
        if not any(list(path.glob("_game*.so")) or list(path.glob("_game*.pyd")) for path in candidates):
            if os.environ.get("GAME_BUILD_DIR") and os.environ.get("CI"):
                self.fail(f"Required native HTTP binary is missing from {build_dir}")
            self.skipTest("The current compiled _game module is unavailable for native HTTP validation.")
        child = nativeHttpChildScript()
        environment = os.environ.copy()
        environment.update(
            SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", SDL_RENDER_DRIVER="software", LIBGL_ALWAYS_SOFTWARE="1"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", child, str(ROOT), str(build_dir), build_config or ""],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        ready = queue.Queue()
        stdout = deque(maxlen=80)
        stderr = deque(maxlen=80)

        def drain(stream, lines):
            for line in stream:
                lines.append(line[-4096:])
                if line.startswith("MCP_HTTP_READY "):
                    ready.put(int(line.split()[1]))

        readers = [
            threading.Thread(target=drain, args=pair, daemon=True)
            for pair in ((proc.stdout, stdout), (proc.stderr, stderr))
        ]
        for reader in readers:
            reader.start()
        first = second = None
        try:
            try:
                port = ready.get(timeout=60)
            except queue.Empty:
                self.fail("native HTTP server startup timed out:\n" + "".join(stdout) + "".join(stderr))
            first, second = HttpClient(port), HttpClient(port)
            first.initialize()
            second.session = first.session
            handles = set()

            def retain(value):
                if isinstance(value, dict) and "__handle__" in value:
                    handles.add(value["__handle__"])
                return value

            def call(client, name, *args, timeout=10):
                return retain(client.tool("engine_call", {"name": name, "args": args}, timeout=timeout)["result"])

            def method(client, handle, name, *args):
                return retain(
                    client.tool("engine_handle_call", {"handle": handle["__handle__"], "method": name, "args": args})[
                        "result"
                    ]
                )

            game = call(first, "CGameLoader.loadGame", timeout=60)
            call(first, "CGameLoader.startGameWithPlayer", game, "multilevel", "Warrior", timeout=60)
            game_map = method(second, game, "getMap")
            player = method(second, game_map, "getPlayer")
            stairs = method(second, game_map, "getObjectByName", "stairsUp")
            controller = method(second, player, "getController")
            method(second, controller, "setTarget", player, method(second, stairs, "getCoords"))
            turn = method(second, game_map, "getTurn")
            before = json.loads(call(second, "jsonify", player))["properties"]
            method(second, game_map, "move")
            after = json.loads(call(second, "jsonify", player))["properties"]
            self.assertEqual(turn + 1, method(second, game_map, "getTurn"))
            self.assertNotEqual(
                [before[key] for key in ("posx", "posy", "posz")], [after[key] for key in ("posx", "posy", "posz")]
            )
            self.assertEqual(
                {"released": len(handles)}, second.tool("engine_release_handles", {"handles": sorted(handles)})
            )
            second.delete()
            handles.clear()
            first.session = None
            first.initialize()
            second.session = first.session
            game = call(first, "CGameLoader.loadGame", timeout=60)
            call(first, "CGameLoader.startGameWithPlayer", game, "multilevel", "Warrior", timeout=60)
            call(first, "CGameLoader.loadGui", game, timeout=60)
            gui = method(second, game, "getGui")
            handler = method(second, game, "getGuiHandler")
            callers = ThreadPoolExecutor(max_workers=1)
            try:
                modal = callers.submit(
                    first.request,
                    "tools/call",
                    {
                        "name": "engine_handle_call",
                        "arguments": {
                            "handle": handler["__handle__"],
                            "method": "showMessage",
                            "args": ["HTTP owner cancellation"],
                        },
                    },
                )

                def containsModal(value):
                    if isinstance(value, dict):
                        return value.get("class") == "CGameTextPanel" or any(
                            containsModal(child) for child in value.values()
                        )
                    return isinstance(value, list) and any(containsModal(child) for child in value)

                opened = False
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if containsModal(json.loads(call(second, "jsonify", gui))):
                        opened = True
                        break
                self.assertTrue(opened, "a second HTTP handler must inspect a modal while its boundary is waiting")
                self.assertEqual(
                    {"released": len(handles)}, second.tool("engine_release_handles", {"handles": sorted(handles)})
                )
                cancelled = modal.result(timeout=10)
                self.assertTrue(cancelled["isError"], cancelled)
                self.assertIn("cancel", cancelled["structuredContent"]["error"].lower())
            finally:
                callers.shutdown(wait=False, cancel_futures=True)
            second.delete()
        finally:
            for client in (first, second):
                if client is not None:
                    client.close()
            closeNativeHttpChild(proc, readers, stdout, stderr)
        self.assertEqual(0, proc.returncode, "".join(stdout) + "".join(stderr))
        self.assertIn("MCP_HTTP_CLOSED", "".join(stdout))
        self.assertIn("MCP_HTTP_REOPENED", "".join(stdout))


if __name__ == "__main__":
    unittest.main()
