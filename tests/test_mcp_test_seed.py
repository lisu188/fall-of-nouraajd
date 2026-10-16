# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import mcp

ROOT = Path(__file__).resolve().parents[1]


class McpTestSeedTest(unittest.TestCase):
    def testTraceHealthExportRequiresExplicitTraceOptInAndStdioAndExcludesAllMutationHooks(self):
        mutations = (
            "configure_playtest_trace",
            "configure_playtest_trace_from_env",
            "clear_playtest_trace",
            "get_playtest_trace_records",
            "drain_playtest_trace_records",
            "record_playtest_trace_json",
        )
        for stdio in (False, True):
            for enabled in ("", "0", "false", "FALSE", "off", "disabled", "1", "true", "trace.jsonl"):
                with self.subTest(stdio=stdio, enabled=enabled), patch.dict(os.environ, GAME_PLAYTEST_TRACE=enabled):
                    getter = Mock(return_value=True)
                    server = mcp.EngineMcpServer(ROOT, ROOT)
                    server._game_module = types.SimpleNamespace(
                        playtest_trace_output_available=getter, **{name: Mock() for name in mutations}
                    )
                    server.game_module = types.SimpleNamespace(playtest_trace_output_available=lambda: "spoof")
                    server.inspect_and_export(stdio=stdio)
                    expected = stdio and enabled.lower() not in {"", "0", "false", "off", "disabled"}
                    name = "playtest_trace_output_available"
                    self.assertEqual(expected, name in server.exports)
                    self.assertNotIn(name, mcp.MCP_ALLOWED_EXPORTS)
                    self.assertFalse(set(mutations) & set(server.exports))
                    if expected:
                        self.assertEqual(True, server._engine_call({"name": name})["structuredContent"]["result"])
                        getter.assert_called_once_with()
                    else:
                        with self.assertRaisesRegex(mcp.ProtocolError, "Callable not exported"):
                            server._engine_call({"name": name})
                        getter.assert_not_called()

    def testTraceHealthExportIsRemovedWhenReinspectionDisablesTheScope(self):
        server = mcp.EngineMcpServer(ROOT, ROOT)
        getter = Mock(return_value=True)
        server._game_module = types.SimpleNamespace(playtest_trace_output_available=getter)
        server.game_module = types.SimpleNamespace()
        name = "playtest_trace_output_available"
        for stdio, enabled in ((False, "1"), (True, "0")):
            with self.subTest(stdio=stdio, enabled=enabled):
                with patch.dict(os.environ, GAME_PLAYTEST_TRACE="1"):
                    server.inspect_and_export(stdio=True)
                self.assertIn(name, server.exports)
                with patch.dict(os.environ, GAME_PLAYTEST_TRACE=enabled):
                    server.inspect_and_export(stdio=stdio)
                self.assertNotIn(name, server.exports)
                with self.assertRaisesRegex(mcp.ProtocolError, "Callable not exported"):
                    server._engine_call({"name": name})
        getter.assert_not_called()

    def testMainPassesTheActualTransportToScopedTraceHealthExports(self):
        for stdio in (False, True):
            args = types.SimpleNamespace(
                repo_root=str(ROOT),
                build_dir=str(ROOT),
                debug=False,
                debug_dir=None,
                log_level=None,
                trace_messages=False,
                native_log_sink="disabled",
                native_log_file=None,
                stdio=stdio,
                allow_origin=[],
                build_config=None,
                test_seed=None,
                build=False,
                host="127.0.0.1",
                port=0,
            )
            server = Mock()
            with (
                self.subTest(stdio=stdio),
                patch.dict(os.environ, GAME_PLAYTEST_TRACE=""),
                patch.object(mcp, "parse_args", return_value=args),
                patch.object(mcp.game_diagnostics, "startSession", return_value=None),
                patch.object(mcp, "configure_logging"),
                patch.object(mcp, "EngineMcpServer", return_value=server),
            ):
                self.assertEqual(0, mcp.main())
                server.inspect_and_export.assert_called_once_with(stdio=stdio)

    def traceHealthDriver(self, path, *, result=True):
        from tests.gameplay_branch_driver import GameplayBranchDriver
        from tests.gameplay_branch_types import RouteCase

        case = RouteCase("trace-health", "unit", ("test",), ("unit.branch",), lambda d: None)
        harness = types.SimpleNamespace(_mcp_engine_call=Mock(return_value=result))
        driver = GameplayBranchDriver(self, harness, {"proc": object()}, case, "Warrior", ROOT)
        driver.trace_path = path
        return driver

    def testTraceHealthRequiresLiteralTrueAndPermanentlyLatchesRpcOrOutputFailures(self):
        for result in (False, 0, 1, "true", None, [], {}):
            with self.subTest(result=result):
                driver = self.traceHealthDriver(Path("actual.trace.jsonl"), result=result)
                with self.assertRaisesRegex(AssertionError, "Native trace output unavailable"):
                    driver.assertNativeTraceOutput()
                driver.harness._mcp_engine_call.return_value = True
                with self.assertRaisesRegex(AssertionError, "Native trace output unavailable"):
                    driver.assertNativeTraceOutput()
                driver.harness._mcp_engine_call.assert_called_once_with(
                    driver.session, "playtest_trace_output_available", [], timeout=90
                )
        driver = self.traceHealthDriver(Path("actual.trace.jsonl"))
        driver.harness._mcp_engine_call.side_effect = OSError("actual native diagnostic RPC unavailable")
        with self.assertRaisesRegex(AssertionError, "Native trace output unavailable"):
            driver.assertNativeTraceOutput()
        driver.harness._mcp_engine_call.side_effect = None
        with self.assertRaisesRegex(AssertionError, "Native trace output unavailable"):
            driver.assertNativeTraceOutput()
        self.assertEqual(1, driver.harness._mcp_engine_call.call_count)

    def testStoppedNativeWriterFailsEvenWithValidStaleRecordsAndCannotResumeIntoASuccess(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actual.trace.jsonl"
            path.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
            driver = self.traceHealthDriver(path)
            driver.assertNativeCombatOutcomes()
            self.assertEqual(1, driver._combat_trace_seq)
            driver.harness._mcp_engine_call.return_value = False
            with self.assertRaisesRegex(AssertionError, "Native trace output unavailable"):
                driver.assertNativeCombatOutcomes()
            self.assertEqual(1, driver._combat_trace_seq)
            driver.harness._mcp_engine_call.return_value = True
            with path.open("a", encoding="utf-8") as output:
                output.write(json.dumps({"seq": 2, "event": "movement"}) + "\n")
            with self.assertRaisesRegex(AssertionError, "Native trace output unavailable"):
                driver.assertNativeCombatOutcomes()
            self.assertEqual(1, driver._combat_trace_seq)
            self.assertEqual(2, driver.harness._mcp_engine_call.call_count)

    def testUint32BoundsAndInvalidSpellings(self):
        self.assertEqual(0, mcp.parseTestSeed("0"))
        self.assertEqual(0xFFFFFFFF, mcp.parseTestSeed("4294967295"))
        for value in ("-1", "4294967296", "1.0", "0x10", "1_0", "+1", "", "nan", "１２"):
            with self.subTest(value=value), self.assertRaisesRegex(argparse.ArgumentTypeError, "unsigned 32-bit"):
                mcp.parseTestSeed(value)

    def testSeedRequiresStdioAndIsOptional(self):
        with patch.object(sys, "argv", ["mcp.py", "--stdio"]):
            self.assertIsNone(mcp.parse_args().test_seed)
        with patch.object(sys, "argv", ["mcp.py", "--stdio", "--test-seed", "25"]):
            self.assertEqual(25, mcp.parse_args().test_seed)
        with patch.object(sys, "argv", ["mcp.py", "--test-seed", "25"]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                mcp.parse_args()
            self.assertEqual(2, failure.exception.code)

    def testNativeSeedPrecedesGameBootstrapAndOrdinaryStartupDoesNotSeed(self):
        for seed in (None, 0, 4294967295):
            events = []
            native = types.SimpleNamespace(
                _seedRandomForTests=lambda value: events.append(("seed", value)), set_logger_sink=lambda *args: None
            )

            def importModule(name):
                events.append(("import", name))
                return native if name == "_game" else types.SimpleNamespace()

            server = mcp.EngineMcpServer(ROOT, ROOT, test_seed=seed)
            with patch.object(mcp.os, "chdir"), patch.object(server, "_insert_import_path"), patch.object(
                mcp.importlib, "import_module", side_effect=importModule
            ):
                server.import_modules()
            expected = [("import", "_game")]
            if seed is not None:
                expected.append(("seed", seed))
            self.assertEqual(expected + [("import", "game")], events)

    def testPrivateSeedHookCannotBecomeAnMcpExport(self):
        server = mcp.EngineMcpServer(ROOT, ROOT)
        server._export_module_callables(types.SimpleNamespace(_seedRandomForTests=lambda value: None), "_game")
        self.assertNotIn("_seedRandomForTests", server.exports)
        self.assertNotIn("_seedRandomForTests", mcp.MCP_ALLOWED_EXPORTS)

    def testPrivateSeedHookSeedsBothSharedLibraryScopesThroughAnExportedCoreBridge(self):
        module = (ROOT / "src/core/CModule.cpp").read_text(encoding="utf-8")
        core = (ROOT / "src/handler/CRngHandler.cpp").read_text(encoding="utf-8")
        header = (ROOT / "src/handler/CRngHandler.h").read_text(encoding="utf-8")
        hook = module.split('"_seedRandomForTests",', 1)[1].split('py::arg("seed")', 1)[0]
        self.assertIn("CRngHandler::seedRandomForTests(seed);", hook)
        self.assertIn("vstd::rng().seed(seed);", hook)
        self.assertNotIn("std::srand", hook, "The process random source must be seeded once by the core bridge")
        bridge = core.split("void CRngHandler::seedRandomForTests(std::uint32_t seed)", 1)[1].split("}", 1)[0]
        self.assertIn("vstd::rng().seed(seed);", bridge)
        self.assertEqual(1, bridge.count("std::srand(seed);"))
        self.assertIn("static GAME_CORE_EXPORT void seedRandomForTests(std::uint32_t seed);", header)
        self.assertNotIn('.def("seedRandomForTests"', module)
        self.assertNotIn("seedRandomForTests", mcp.MCP_ALLOWED_EXPORTS)
        self.assertTrue(all("seedRandomForTests" not in methods for methods in mcp.MCP_ALLOWED_HANDLE_METHODS.values()))


class McpTestSeedRuntimeTest(unittest.TestCase):
    def testEachNativeRandomSourceReplaysWithinThisPlatform(self):
        import test as harness

        if not any(
            list(path.glob("_game*.pyd")) + list(path.glob("_game*.so"))
            for path in (harness.build_dir, *harness.extension_dirs)
        ):
            self.skipTest("Current native _game extension required for native random-source replay")
        program = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import mcp
server = mcp.EngineMcpServer(Path(sys.argv[1]), Path(sys.argv[2]),
    build_config=sys.argv[3] or None, native_log_sink='disabled', test_seed=0)
server.import_modules()
n = server._game_module
game = n.CGameLoader.loadGame()
n.CGameLoader.startGameWithPlayer(game, 'test', 'Warrior', 'humanRace')
player = game.getMap().getPlayer()
rng = game.getRngHandler()
def sample(seed):
    recipient = game.createObject('Pritz')
    n._seedRandomForTests(seed)
    module_draws = [n.randint(0, 2147483647) for _ in range(64)]
    process_draws = [player.getDmg(True) for _ in range(128)]
    core_draws = []
    for _ in range(32):
        before = {item.getName() for item in recipient.getItems()}
        rng.addRandomLoot(recipient, 8)
        core_draws.append(sorted(item.getTypeId() for item in recipient.getItems() if item.getName() not in before))
    return (module_draws, process_draws, core_draws)
replays = {}
for seed in (0, 17, 4294967295):
    first, second = sample(seed), sample(seed)
    assert first == second, (seed, 'native random sources did not replay')
    assert all(len({tuple(draw) if isinstance(draw, list) else draw for draw in source}) > 1 for source in first), \
        'degenerate module/process/core random-source oracle'
    different = sample(seed ^ 0xA5A5A5A5)
    assert all(left != right for left, right in zip(first, different)), 'a native random source ignored its seed'
    replays[str(seed)] = first
print('NATIVE_SEED_REPLAY=' + json.dumps(replays, sort_keys=True))
"""
        replays = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-c", program, str(ROOT), str(harness.build_dir), harness.build_config or ""],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(0, result.returncode, result.stdout[-4096:] + result.stderr[-4096:])
            payloads = [
                line.removeprefix("NATIVE_SEED_REPLAY=")
                for line in result.stdout.splitlines()
                if line.startswith("NATIVE_SEED_REPLAY=")
            ]
            self.assertEqual(1, len(payloads), "The actual native replay proof must be emitted once")
            replays.append(json.loads(payloads[0]))
        self.assertEqual(
            replays[0], replays[1], "Fresh processes did not replay module, process and game_core RNG draws"
        )
