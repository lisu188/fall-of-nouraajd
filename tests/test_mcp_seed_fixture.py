# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import mcp_seed_fixture

ROOT = Path(__file__).resolve().parents[1]


class McpSeedFixtureTest(unittest.TestCase):
    def fixtureModule(
        self, *, seed_hook=True, owner_thread=True, seed_error=None, import_error=None, legacy_import=False
    ):
        events = []
        loop = SimpleNamespace() if legacy_import else SimpleNamespace(isMainThread=lambda: owner_thread)
        native = SimpleNamespace(event_loop=SimpleNamespace(instance=lambda: loop))
        if seed_hook is True:

            def seed(seed_value):
                if not owner_thread:
                    raise RuntimeError("The private seed hook requires the engine owner thread")
                events.append(("seed", seed_value))
                if seed_error is not None:
                    raise seed_error

            native._seedRandomForTests = seed
        elif seed_hook is not False:
            native._seedRandomForTests = seed_hook

        class Server:
            def _importModules(self):
                events.append("import")
                if import_error is not None:
                    raise import_error
                self._game_module = native

        if legacy_import:
            Server.import_modules = Server._importModules
            del Server._importModules

        def main():
            events.append(("argv", sys.argv.copy()))
            server = Server()
            import_modules = getattr(server, "_importModules", None) or server.import_modules
            import_modules()
            events.append("loadGame")
            import_modules()
            events.append("loadSavedGame")
            print('{"jsonrpc":"2.0","id":1,"result":{}}')
            print("native diagnostics", file=sys.stderr)
            return 7

        return SimpleNamespace(EngineMcpServer=Server, main=main), events

    def testSeedsExactlyOnceBeforeTheFirstLoaderAndNeverAtReload(self):
        module, events = self.fixtureModule()
        original_import = module.EngineMcpServer._importModules
        original_argv = sys.argv
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = mcp_seed_fixture.runSeededMcp(100, ["--stdio"], mcp_module=module)
        self.assertEqual(7, result)
        self.assertEqual(["import", ("seed", 100), "loadGame", "import", "loadSavedGame"], events[1:])
        self.assertIs(original_import, module.EngineMcpServer._importModules)
        self.assertIs(original_argv, sys.argv)
        self.assertEqual('{"jsonrpc":"2.0","id":1,"result":{}}\n', stdout.getvalue())
        self.assertEqual('MCP fixture random seed {"seed": 100}\nnative diagnostics\n', stderr.getvalue())

    def testLegacySynchronousBootstrapSeedsOnceWithoutAddingPublicBindings(self):
        module, events = self.fixtureModule(legacy_import=True)
        original_import = module.EngineMcpServer.import_modules
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            mcp_seed_fixture.runSeededMcp(100, [], mcp_module=module)
        self.assertEqual(["import", ("seed", 100), "loadGame", "import", "loadSavedGame"], events[1:])
        self.assertIs(original_import, module.EngineMcpServer.import_modules)
        self.assertFalse(hasattr(module.EngineMcpServer, "_importModules"))

    def testLegacyBootstrapPropagatesPrivateOwnerGuardBeforeLoading(self):
        module, events = self.fixtureModule(legacy_import=True, owner_thread=False)
        with self.assertRaisesRegex(RuntimeError, "engine owner thread"):
            mcp_seed_fixture.runSeededMcp(100, [], mcp_module=module)
        self.assertEqual(["import"], events[1:])

    def testForwardsNormalMcpArgumentsWithoutChangingPathsOrValues(self):
        module, events = self.fixtureModule()
        arguments = [
            "--stdio",
            "--repo-root",
            str(ROOT),
            "--build-dir",
            "build directory",
            "--native-log-sink",
            "file",
            "--native-log-file",
            "logs/native log.txt",
            "--build-config",
            "Release",
        ]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            mcp_seed_fixture.main([*arguments, "--fixture-seed", "100"], mcp_module=module)
        self.assertEqual(("argv", [str(ROOT / "mcp.py"), *arguments]), events[0])

    def testMissingOrNoncallablePrivateSeedHookFailsBeforeLoading(self):
        for seed_hook in (False, "not a callback"):
            with self.subTest(seed_hook=seed_hook):
                module, events = self.fixtureModule(seed_hook=seed_hook)
                original_import = module.EngineMcpServer._importModules
                with self.assertRaisesRegex(RuntimeError, "rebuild the current test binary"):
                    mcp_seed_fixture.runSeededMcp(100, [], mcp_module=module)
                self.assertEqual(["import"], events[1:])
                self.assertIs(original_import, module.EngineMcpServer._importModules)

    def testWrongThreadFailsBeforeSeedingOrLoading(self):
        module, events = self.fixtureModule(owner_thread=False)
        with self.assertRaisesRegex(RuntimeError, "engine owner thread"):
            mcp_seed_fixture.runSeededMcp(100, [], mcp_module=module)
        self.assertEqual(["import"], events[1:])

    def testImportAndSeedExceptionsPropagateWithoutLoadingOrFallback(self):
        for failure_stage in ("import_error", "seed_error"):
            with self.subTest(failure_stage=failure_stage):
                failure = ValueError("expected failure")
                module, events = self.fixtureModule(**{failure_stage: failure})
                original_argv = sys.argv
                original_import = module.EngineMcpServer._importModules
                with self.assertRaises(ValueError) as caught:
                    mcp_seed_fixture.runSeededMcp(100, [], mcp_module=module)
                self.assertIs(failure, caught.exception)
                self.assertNotIn("loadGame", events)
                self.assertNotIn("loadSavedGame", events)
                self.assertIs(original_argv, sys.argv)
                self.assertIs(original_import, module.EngineMcpServer._importModules)

    def testInvalidSeedsFailBeforeImportingOrStartingMcp(self):
        for seed in (-1, 1 << 32, True, 1.5, "100", None):
            with self.subTest(seed=seed):
                module, events = self.fixtureModule()
                with self.assertRaises(ValueError):
                    mcp_seed_fixture.runSeededMcp(seed, [], mcp_module=module)
                self.assertEqual([], events)

    def testCliRejectsMissingMalformedAndOutOfRangeSeeds(self):
        for arguments in ([], ["--fixture-seed", "bad"], ["--fixture-seed", "-1"], ["--fixture-seed", str(1 << 32)]):
            with self.subTest(arguments=arguments):
                module, events = self.fixtureModule()
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    mcp_seed_fixture.main(arguments, mcp_module=module)
                self.assertEqual(2, caught.exception.code)
                self.assertEqual([], events)

    def testProductionMcpKeepsUnseededDefaultsAndRejectsFixtureOnlyOption(self):
        import mcp

        with patch.object(sys, "argv", ["mcp.py", "--stdio"]):
            options = mcp.parse_args()
        self.assertNotIn("fixture_seed", vars(options))
        with patch.object(sys, "argv", ["mcp.py", "--fixture-seed", "100"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                mcp.parse_args()
        self.assertEqual(2, caught.exception.code)
        self.assertNotIn("_seedRandomForTests", (ROOT / "mcp.py").read_text(encoding="utf-8"))

    def testRunnerOnlySelectsTheTestLauncherForAnExplicitFixtureSeed(self):
        tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "McpServerTest")
        method = next(
            node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "_start_stdio_mcp_process"
        )
        namespace = {
            "REPO_ROOT": ROOT,
            "build_dir": ROOT / "cmake-build-gcc15-release",
            "build_config": "Release",
            "Path": Path,
            "sys": sys,
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), "<exact-mcp-startup>", "exec"), namespace)
        commands = []

        def start(command, **kwargs):
            commands.append((command, kwargs))
            return SimpleNamespace()

        fixture = SimpleNamespace(assertTrue=self.assertTrue, _start_stdio_process=start)
        namespace[method.name](fixture)
        namespace[method.name](fixture, fixture_seed=100)
        default, seeded = commands
        self.assertEqual(str(ROOT / "mcp.py"), default[0][1])
        self.assertNotIn("--fixture-seed", default[0])
        self.assertEqual(str(ROOT / "tests" / "mcp_seed_fixture.py"), seeded[0][1])
        seed_index = seeded[0].index("--fixture-seed")
        self.assertEqual(["--fixture-seed", "100"], seeded[0][seed_index : seed_index + 2])
        self.assertEqual(default[0][2:], seeded[0][2:seed_index] + seeded[0][seed_index + 2 :])
        self.assertEqual(default[1], seeded[1])

    def testWalkthroughRestartClosesTheOldProcessAndEnvironmentBeforeStarting(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        case = unittest.TestCase()
        events = []
        case.addCleanup(events.append, "environment stopped")
        case.addCleanup(events.append, "old process closed")
        case.setUp = lambda: events.append("fresh seeded process started")
        OctobogzMcpWalkthroughTest.restartMcpSession(case)
        self.assertEqual(["old process closed", "environment stopped", "fresh seeded process started"], events)

    def walkthroughStartup(self, tails, *, clock=(0, 1), poll_result=None):
        from tests import test_octobogz_mcp as walkthrough

        starts = []
        tail_values = iter(tails)
        last_tail = tails[-1]
        process = SimpleNamespace(pid=12345, poll=lambda: poll_result)

        class Harness:
            def _start_stdio_mcp_process(self, *args, **kwargs):
                starts.append((args, kwargs))
                return process

            def _mcp_process_tail_text(self, proc, stream):
                if proc is not process or stream != "stderr":
                    raise AssertionError("The seed receipt must come from the active process's stderr")
                return next(tail_values, last_tail)

        def setUp(case):
            case.harness = Harness()
            case.process = case.harness._start_stdio_mcp_process()

        harness = SimpleNamespace(TEST_OUTPUT_DIR=ROOT / "test", McpServerTest=Harness)
        output = io.StringIO()
        with (
            patch.dict(sys.modules, {"test": harness}),
            patch.object(walkthrough.dialogue_mcp.DialogueMcpWalkthroughTest, "setUp", new=setUp),
            patch.object(walkthrough, "perf_counter", side_effect=clock),
            patch.object(walkthrough, "sleep") as sleep,
            redirect_stdout(output),
        ):
            case = walkthrough.OctobogzMcpWalkthroughTest("runTest")
            case.setUp()
        return starts, output.getvalue(), sleep.call_count

    def testWalkthroughStartupPublishesTheObservedReceiptAndWaitsForItsCompleteLine(self):
        starts, output, sleeps = self.walkthroughStartup(
            ['MCP fixture random seed {"seed":', 'MCP fixture random seed {"seed": 100}\n']
        )
        self.assertEqual(1, len(starts))
        self.assertEqual(100, starts[0][1]["fixture_seed"])
        self.assertIn("native_log_file", starts[0][1])
        self.assertIn("MCP hunt fixture startup {'pid': 12345, 'receipt': {'seed': 100}}", output)
        self.assertEqual(1, sleeps)

    def testWalkthroughStartupFailsClosedOnMissingWrongDuplicateMalformedAndExitedReceipts(self):
        for tails, clock, poll_result, error in (
            (["other log\n"], (0, 6), None, AssertionError),
            (['MCP fixture random seed {"seed": 101}\n'], (0,), None, AssertionError),
            (['MCP fixture random seed {"seed": 100}\n' * 2], (0,), None, AssertionError),
            (["MCP fixture random seed invalid\n"], (0,), None, ValueError),
            (["other log\n"], (0,), 1, AssertionError),
        ):
            with self.subTest(tails=tails, poll_result=poll_result), self.assertRaises(error):
                self.walkthroughStartup(tails, clock=clock, poll_result=poll_result)

    def testWalkthroughRestartPropagatesErrorsWithoutStartingAfterFailedCleanup(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        events = []
        case = SimpleNamespace(
            assertTrue=self.assertTrue, doCleanups=lambda: False, setUp=lambda: events.append("start")
        )
        with self.assertRaises(AssertionError):
            OctobogzMcpWalkthroughTest.restartMcpSession(case)
        self.assertEqual([], events)
        failure = RuntimeError("cleanup sentinel")

        def fail():
            raise failure

        case.doCleanups = fail
        with self.assertRaises(RuntimeError) as caught:
            OctobogzMcpWalkthroughTest.restartMcpSession(case)
        self.assertIs(failure, caught.exception)
        self.assertEqual([], events)
        case.doCleanups = lambda: events.append("closed") or True
        case.setUp = fail
        with self.assertRaises(RuntimeError) as caught:
            OctobogzMcpWalkthroughTest.restartMcpSession(case)
        self.assertIs(failure, caught.exception)
        self.assertEqual(["closed"], events)

    def testClassLoopRestartsBeforeTheSecondScenarioAndPreservesItsCombinedWitnesses(self):
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce"
        )
        loop = next(node for node in method.body if isinstance(node, ast.For))
        self.assertIsInstance(loop.body[0], ast.If, "Each class must select an isolated process before its scenario")
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "restartMcpSession"
                for node in ast.walk(loop.body[0])
            )
        )
        isolated_loop = copy.deepcopy(loop)
        isolated_loop.body = [
            copy.deepcopy(loop.body[0]),
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr="loadClass", ctx=ast.Load()),
                    args=[ast.Name(id="player_class", ctx=ast.Load())],
                    keywords=[],
                )
            ),
        ]
        events = []
        case = SimpleNamespace(
            restartMcpSession=lambda: events.append("fresh process"),
            loadClass=lambda name: events.append(name),
        )
        executable = ast.fix_missing_locations(ast.Module(body=[isolated_loop], type_ignores=[]))
        exec(compile(executable, "<actual-class-isolation-loop>", "exec"), {"self": case})
        self.assertEqual(["Warrior", "fresh process", "Sorcerer"], events)
        for name in ("phase_observations", "manual_phase_observations"):
            assignments = [
                node
                for node in ast.walk(method)
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Attribute) and target.attr == name for target in node.targets)
            ]
            self.assertEqual(1, len(assignments))
            self.assertLess(assignments[0].lineno, loop.lineno)
        self.assertNotIn("_seedRandomForTests", ast.get_source_segment(source, method))


if __name__ == "__main__":
    unittest.main()
