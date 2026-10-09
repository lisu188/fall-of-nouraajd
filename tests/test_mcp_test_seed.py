# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

import mcp

ROOT = Path(__file__).resolve().parents[1]


class McpTestSeedTest(unittest.TestCase):
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


class McpTestSeedRuntimeTest(unittest.TestCase):
    def testEachNativeRandomSourceReplaysWithinThisPlatform(self):
        import test as harness

        if not any(
            list(path.glob("_game*.pyd")) + list(path.glob("_game*.so"))
            for path in (harness.build_dir, *harness.extension_dirs)
        ):
            self.skipTest("Current native _game extension required for native random-source replay")
        program = """
import sys
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
def sample(seed):
    n._seedRandomForTests(seed)
    return ([n.randint(0, 2147483647) for _ in range(64)], [player.getDmg(True) for _ in range(128)])
for seed in (0, 17, 4294967295):
    first, second = sample(seed), sample(seed)
    assert first == second, (seed, 'native random sources did not replay')
    assert len(set(first[0])) > 1 and len(set(first[1])) > 1, 'degenerate random-source oracle'
    assert first[0] != sample((seed + 1) & 0xffffffff)[0]
print('vstd::rng and std::rand: deterministic within platform')
"""
        result = subprocess.run(
            [sys.executable, "-c", program, str(ROOT), str(harness.build_dir), harness.build_config or ""],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.assertEqual(0, result.returncode, result.stdout[-4096:] + result.stderr[-4096:])
        self.assertIn("std::rand: deterministic", result.stdout)
