# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import contextlib
import io
import json
import os
import random
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import traceback
import unittest
from time import monotonic
from unittest.mock import Mock, patch

import mcp

from tests.cpp_bindings import readBindingSources, registrationBody

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
        module = readBindingSources(ROOT)
        core = (ROOT / "src/core/CRuntimeBridge.cpp").read_text(encoding="utf-8")
        header = (ROOT / "src/core/CRuntimeBridge.h").read_text(encoding="utf-8")
        game = (ROOT / "src/core/CGame.cpp").read_text(encoding="utf-8")
        self.assertEqual(1, module.count('"_seedRandomForTests"'), "Bind the private startup hook exactly once")
        hook = module.split('"_seedRandomForTests",', 1)[1].split('py::arg("seed")', 1)[0]
        self.assertIn("seedModuleRandomForTests(seed);", hook)
        runtime = (ROOT / "src/core/CModuleRuntime.cpp").read_text(encoding="utf-8")
        adapter = registrationBody(runtime, "seedModuleRandomForTests")
        self.assertIn("CRuntimeBridge::seedRandomForTests(seed);", adapter)
        self.assertIn("vstd::rng().seed(seed);", adapter)
        self.assertLess(
            adapter.index("CRuntimeBridge::seedRandomForTests(seed);"), adapter.index("vstd::rng().seed(seed);")
        )
        self.assertNotIn("std::srand", adapter, "The process random source must be seeded once by the core bridge")
        bridge = core.split("void CRuntimeBridge::seedRandomForTests(std::uint32_t seed)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("vstd::rng().seed(seed);", bridge)
        self.assertEqual(1, bridge.count("std::srand(seed);"))
        self.assertIn("static void seedRandomForTests(std::uint32_t seed);", header)
        self.assertIn("!event_loop_instance()->isMainThread()", bridge)
        name_owners = [
            owner for owner in ("CUtil", "CSerialization") if owner + "::seedGeneratedNamesForTests(seed);" in bridge
        ]
        self.assertEqual(1, len(name_owners), "One canonical core name owner must guard startup seeding")
        name_owner = name_owners[0]
        guard_call = name_owner + "::seedGeneratedNamesForTests(seed);"
        self.assertLess(bridge.index("!event_loop_instance()->isMainThread()"), bridge.index(guard_call))
        self.assertLess(bridge.index(guard_call), bridge.index("vstd::rng().seed(seed);"))
        serialization = (ROOT / f"src/core/{name_owner}.cpp").read_text(encoding="utf-8")
        guard = serialization.split(f"void {name_owner}::seedGeneratedNamesForTests(std::uint32_t seed)", 1)[1]
        guard = guard.split("\n}\n", 1)[0]
        self.assertIn("state.sessionStarted || state.startupSeeded", guard)
        self.assertLess(
            guard.index("state.sessionStarted || state.startupSeeded"), guard.index("state.fixtureSeed = seed;")
        )
        self.assertIn("state.startupSeeded = true;", guard)
        self.assertIn(name_owner + "::markGameSessionStarted();", game)
        self.assertNotIn('.def("seedRandomForTests"', module)
        self.assertNotIn("seedRandomForTests", mcp.MCP_ALLOWED_EXPORTS)
        self.assertTrue(all("seedRandomForTests" not in methods for methods in mcp.MCP_ALLOWED_HANDLE_METHODS.values()))

    def runOracle(
        self, module, *, seconds_per_child=0, ignored_source=None, degenerate_source=None, engine_owner=False
    ):
        launches, children = [], []
        self.launchedChildren = launches
        clock = [0.0]

        def runChild(command, **kwargs):
            self.assertTrue(kwargs["capture_output"], "subprocess.run must drain both child pipes")
            self.assertTrue(kwargs["text"])
            self.assertLessEqual(kwargs["timeout"], 90)
            launches.append({"command": command, "timeout": kwargs["timeout"]})
            child = {
                "seeded": False,
                "started": False,
                "seedCalls": 0,
                "counts": [0, 0, 0],
                "ownerActive": False,
                "dispatches": [],
                "releases": [],
            }
            children.append(child)
            generators = [None, None, None]

            def requireOwner():
                if engine_owner:
                    self.assertTrue(child["ownerActive"], "Native sampling crossed the engine owner boundary")

            def seedNative(seed):
                requireOwner()
                child["seedCalls"] += 1
                if child["seeded"] or child["started"]:
                    raise RuntimeError("Test random seeding must run once before the first game session is created.")
                child["seeded"] = True
                child["seed"] = seed
                for index in range(3):
                    generators[index] = random.Random((0 if ignored_source == index else seed) ^ (index + 1))

            def drawModule(lower, upper):
                requireOwner()
                child["counts"][0] += 1
                if degenerate_source == 0:
                    return child["seed"]
                return generators[0].randint(lower, upper)

            def drawProcess(allow_crit):
                requireOwner()
                child["counts"][1] += 1
                if degenerate_source == 1:
                    return child["seed"]
                return generators[1].randrange(1000)

            def addLoot(recipient, scale):
                requireOwner()
                self.assertEqual(8, scale)
                child["counts"][2] += 1
                name = "owned-" + str(child["counts"][2])
                identity = "loot-" + str(child["seed"] if degenerate_source == 2 else generators[2].randrange(1000))
                recipient.items.append(Item(name, identity))

            class NativeObject:
                def __del__(self):
                    child["releases"].append((type(self).__name__, child["ownerActive"]))

            class Item(NativeObject):
                def __init__(self, name, identity):
                    self.name, self.identity = name, identity

                def getName(self):
                    requireOwner()
                    return self.name

                def getTypeId(self):
                    requireOwner()
                    return self.identity

            class Player(NativeObject):
                def getDmg(self, allow_crit):
                    return drawProcess(allow_crit)

            class Map(NativeObject):
                def __init__(self):
                    self.player = Player()

                def getPlayer(self):
                    requireOwner()
                    return self.player

            class Rng(NativeObject):
                def addRandomLoot(self, recipient, scale):
                    addLoot(recipient, scale)

            class Recipient(NativeObject):
                def __init__(self):
                    self.items = []

                def getItems(self):
                    requireOwner()
                    return self.items

            class Game(NativeObject):
                def __init__(self):
                    self.game_map, self.rng = Map(), Rng()

                def getMap(self):
                    requireOwner()
                    return self.game_map

                def getRngHandler(self):
                    requireOwner()
                    return self.rng

                def createObject(self, identity):
                    requireOwner()
                    self_case.assertEqual("Pritz", identity)
                    return Recipient()

            self_case = self

            def loadGame():
                requireOwner()
                self.assertTrue(child["seeded"], "Seed before game creation")
                child["started"] = True
                return Game()

            def startGameWithPlayer(*args):
                requireOwner()

            class EngineOwner:
                def run(self, callback):
                    self_case.assertFalse(child["ownerActive"])
                    child["dispatches"].append(callback.__name__)
                    child["ownerActive"] = True
                    try:
                        return callback()
                    finally:
                        child["ownerActive"] = False

            native = types.SimpleNamespace(
                _seedRandomForTests=seedNative,
                randint=drawModule,
                CGameLoader=types.SimpleNamespace(loadGame=loadGame, startGameWithPlayer=startGameWithPlayer),
            )

            class EngineMcpServer:
                def __init__(self, *args, test_seed=None, **kwargs):
                    self._game_module = native
                    self.test_seed = test_seed
                    if engine_owner:
                        self._engine_owner = EngineOwner()

                def import_modules(self):
                    callback = lambda: seedNative(self.test_seed)
                    if engine_owner:
                        self._engine_owner.run(callback)
                    else:
                        callback()

            fake_mcp = types.SimpleNamespace(EngineMcpServer=EngineMcpServer)
            stdout, stderr = io.StringIO(), io.StringIO()
            returncode = 0
            with (
                patch.dict(sys.modules, {"mcp": fake_mcp}),
                patch.object(sys, "argv", ["-c", *command[3:]]),
                patch.object(sys, "path", list(sys.path)),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                try:
                    exec(command[2], {"__name__": "__main__"})
                except Exception:
                    traceback.print_exc()
                    returncode = 1
            clock[0] += seconds_per_child
            return subprocess.CompletedProcess(command, returncode, stdout.getvalue(), stderr.getvalue())

        with tempfile.TemporaryDirectory(prefix="seed-oracle-mock-", dir=ROOT) as temporary:
            build = Path(temporary)
            (build / "_game.mock.so").write_bytes(b"")
            harness = types.SimpleNamespace(build_dir=build, extension_dirs=(), build_config="")
            instance = module.McpTestSeedRuntimeTest("testEachNativeRandomSourceReplaysWithinThisPlatform")
            with (
                patch.dict(sys.modules, {"test": harness}),
                patch.object(module.subprocess, "run", side_effect=runChild),
                patch.object(module, "monotonic", lambda: clock[0], create=True),
            ):
                instance.testEachNativeRandomSourceReplaysWithinThisPlatform()
        return launches, children

    def testFreshChildrenHonorOneTimePreBootstrapSeedAndRetainAllSamples(self):
        module = sys.modules[__name__]
        launches, children = self.runOracle(module)
        self.assertEqual(12, len(launches))
        self.assertTrue(all(child["seedCalls"] == 1 for child in children))
        self.assertTrue(all(child["counts"] == [64, 128, 32] for child in children))
        expected = {seed for primary in (0, 17, 4294967295) for seed in (primary, primary ^ 0xA5A5A5A5)}
        self.assertEqual(expected, {child["seed"] for child in children})
        self.assertTrue(all(sum(child["seed"] == seed for child in children) == 2 for seed in expected))

    def testAllChildrenShareTheOriginalOverallDeadline(self):
        module = sys.modules[__name__]
        with self.assertRaisesRegex(AssertionError, "original 180-second"):
            self.runOracle(module, seconds_per_child=20)
        self.assertEqual([90] * 5 + [80, 60, 40, 20], [launch["timeout"] for launch in self.launchedChildren])

    def testNativeOracleSamplesAndReleasesNativeStateOnTheEngineOwner(self):
        launches, children = self.runOracle(sys.modules[__name__], engine_owner=True)
        self.assertEqual(12, len(launches))
        for child in children:
            self.assertEqual(1, child["seedCalls"])
            self.assertEqual([64, 128, 32], child["counts"])
            self.assertEqual(1, child["dispatches"].count("sampleSources"))
            self.assertEqual(
                {"Game", "Map", "Player", "Rng", "Recipient", "Item"}, {kind for kind, _active in child["releases"]}
            )
            self.assertTrue(
                all(active for _kind, active in child["releases"]),
                "Native oracle objects must be released before returning from the owner callback",
            )

    def testEveryNativeSourceMustObserveDifferentSeeds(self):
        module = sys.modules[__name__]
        for source in range(3):
            with self.subTest(source=source), self.assertRaisesRegex(AssertionError, "ignored its seed"):
                self.runOracle(module, ignored_source=source)

    def testEveryNativeSourceMustRemainNondegenerate(self):
        module = sys.modules[__name__]
        for source in range(3):
            with self.subTest(source=source), self.assertRaisesRegex(AssertionError, "degenerate"):
                self.runOracle(module, degenerate_source=source)


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
seed = int(sys.argv[4])
server = mcp.EngineMcpServer(Path(sys.argv[1]), Path(sys.argv[2]),
    build_config=sys.argv[3] or None, native_log_sink='disabled', test_seed=seed)
server.import_modules()
n = server._game_module
def sampleSources():
    game = player = rng = recipient = None
    try:
        game = n.CGameLoader.loadGame()
        n.CGameLoader.startGameWithPlayer(game, 'test', 'Warrior', 'humanRace')
        player = game.getMap().getPlayer()
        rng = game.getRngHandler()
        recipient = game.createObject('Pritz')
        module_draws = [n.randint(0, 2147483647) for _ in range(64)]
        process_draws = [player.getDmg(True) for _ in range(128)]
        core_draws = []
        for _ in range(32):
            before = {item.getName() for item in recipient.getItems()}
            rng.addRandomLoot(recipient, 8)
            core_draws.append(sorted(item.getTypeId() for item in recipient.getItems() if item.getName() not in before))
        return module_draws, process_draws, core_draws
    finally:
        recipient = player = rng = game = None
owner = getattr(server, '_engine_owner', None)
samples = owner.run(sampleSources) if owner is not None else sampleSources()
print('NATIVE_SEED_REPLAY=' + json.dumps(samples, sort_keys=True))
"""
        seeds = (0, 17, 4294967295)
        deadline = monotonic() + 180
        replays = []
        for _ in range(2):
            draws = {}
            for seed in seeds:
                for sample_seed in (seed, seed ^ 0xA5A5A5A5):
                    remaining = deadline - monotonic()
                    self.assertGreater(remaining, 0, "The original 180-second native replay budget was exhausted")
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            program,
                            str(ROOT),
                            str(harness.build_dir),
                            harness.build_config or "",
                            str(sample_seed),
                        ],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        timeout=min(90, remaining),
                    )
                    self.assertEqual(0, result.returncode, result.stdout[-4096:] + result.stderr[-4096:])
                    payloads = [
                        line.removeprefix("NATIVE_SEED_REPLAY=")
                        for line in result.stdout.splitlines()
                        if line.startswith("NATIVE_SEED_REPLAY=")
                    ]
                    self.assertEqual(1, len(payloads), "The actual native replay proof must be emitted once")
                    sample = json.loads(payloads[0])
                    self.assertEqual([64, 128, 32], [len(source) for source in sample])
                    self.assertTrue(
                        all(
                            len({tuple(draw) if isinstance(draw, list) else draw for draw in source}) > 1
                            for source in sample
                        ),
                        "degenerate module/process/core random-source oracle",
                    )
                    draws[sample_seed] = sample
                self.assertTrue(
                    all(left != right for left, right in zip(draws[seed], draws[seed ^ 0xA5A5A5A5])),
                    "a native random source ignored its seed",
                )
            replays.append(draws)
        self.assertEqual(
            replays[0], replays[1], "Fresh processes did not replay module, process and game_core RNG draws"
        )
        self.assertLessEqual(monotonic(), deadline, "The original 180-second native replay budget was exhausted")
