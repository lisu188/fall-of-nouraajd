# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public map publication identity; native execution remains a separate CI gate."""

from pathlib import Path
from hashlib import sha256
import json
import unittest

from tests.cpp_bindings import registrationBody, registrationTokens

ROOT = Path(__file__).resolve().parents[1]


def functionBody(source, signature):
    start = source.index("{", source.index(signature))
    depth = 0
    for index in range(start, len(source)):
        depth += source[index] == "{"
        depth -= source[index] == "}"
        if depth == 0:
            return source[start + 1 : index]
    raise AssertionError("Unterminated selected function")


class GameMapBindingEpochSourceTest(unittest.TestCase):
    def testEpochIsPrivateUnsignedAndOutsideSerializedMetadata(self):
        header = (ROOT / "src/core/CGame.h").read_text(encoding="utf-8")
        self.assertIn("std::uint64_t getMapBindingEpoch() const;", header)
        self.assertIn("std::uint64_t mapBindingEpoch = 0;", header.split("  private:", 1)[1])
        self.assertNotRegex(header, r"V_PROPERTY\([^\n]*[Ee]poch")
        self.assertNotIn("setMapBindingEpoch", header)

    def testReadonlyQueryDoesNotCreateContextOrDispatchCallbacks(self):
        source = (ROOT / "src/core/CGame.cpp").read_text(encoding="utf-8")
        self.assertIn("std::uint64_t CGame::getMapBindingEpoch() const", source)
        body = functionBody(source, "std::uint64_t CGame::getMapBindingEpoch() const")
        self.assertEqual("std::lock_guard lock(*resourceMutex); return mapBindingEpoch;", " ".join(body.split()))

    def testOnlyActualPublicPublicationIncrementsBeforeSignal(self):
        source = (ROOT / "src/core/CGame.cpp").read_text(encoding="utf-8")
        body = functionBody(source, "void CGame::setMap(")
        self.assertIn("++mapBindingEpoch;", body)
        self.assertIn("++mapBindingEpoch;", functionBody(body, "if (bindingChanged)"))
        self.assertLess(body.index("bindingChanged = this->map != map;"), body.index("++mapBindingEpoch;"))
        self.assertLess(body.index("if (bindingChanged)"), body.index("++mapBindingEpoch;"))
        self.assertLess(body.index("++mapBindingEpoch;"), body.index("this->map = map;"))
        self.assertLess(body.index("this->map = map;"), body.index('signal<true>("mapBindingChanged")'))
        self.assertIn("mapBindingEpoch == std::numeric_limits<std::uint64_t>::max()", body)
        self.assertLess(body.index("throw std::overflow_error"), body.index("++mapBindingEpoch;"))
        self.assertNotIn("advanceTransitionGeneration", body)
        self.assertEqual(1, source.count("++mapBindingEpoch;"))

    def testQuietResourceScopeRetainsExistingNoPublicationContract(self):
        source = (ROOT / "src/core/CGame.cpp").read_text(encoding="utf-8")
        quiet = functionBody(source, "void CGame::setMapForResourceLoad(")
        self.assertNotIn("mapBindingEpoch", quiet)
        self.assertNotIn("signal", quiet)
        loader = (ROOT / "src/core/CLoader.cpp").read_text(encoding="utf-8")
        self.assertIn("this->game->setMapForResourceLoad(std::move(replacement));", loader)
        self.assertIn("game->setMapForResourceLoad(previous);", loader)
        tests = (ROOT / "tests/unit/test_handler.cpp").read_text(encoding="utf-8")
        scope = functionBody(tests, "void testScriptWaitSurvivesFailedSaveResourceBindingWithoutDispatchingMapChanges(")
        self.assertIn("const auto publishedEpoch = game->getMapBindingEpoch();", scope)
        self.assertIn("game->getMapBindingEpoch() == resourceEpoch", scope)

    def testNativeCasesAndBoundedOperationGuardAreActuallyWired(self):
        native = (ROOT / "tests/unit/test_core.cpp").read_text(encoding="utf-8")
        for name in (
            "testGameMapBindingEpochTracksPublicPointerChanges",
            "testGameMapBindingEpochPrecedesReentrantSignals",
            "testGameMapBindingEpochCountsActualPublicationAfterPanelReentry",
        ):
            self.assertEqual(1, native.count("void " + name + "()"))
            self.assertIn('runDiagnosedCase("' + name + '"', native)
        perf = (ROOT / "tests/unit/test_engine_hotspot_performance.cpp").read_text(encoding="utf-8")
        name = "testMapBindingEpochQueriesAndPublicationsAreBounded"
        body = functionBody(perf, "void " + name + "(")
        for expression in (
            "constexpr int CYCLES = 128;",
            "constexpr int READS_PER_CYCLE = 4;",
            "probe->callbacks == 2 * CYCLES",
            "loop->getPendingTaskCount() == pending",
            "loop->getDelayedTaskCount() == delayed",
            "context->isTransitionGenerationCurrent(generation)",
        ):
            self.assertIn(expression, body)
        self.assertEqual(1, perf.count("    " + name + "();"))

    def testPythonBindingIsGetterOnlyAndSourceSuiteIsFastOnly(self):
        source = (ROOT / "src/core/bindings/CModuleFoundation.cpp").read_text(encoding="utf-8")
        self.assertIn('.def("getMapBindingEpoch", &CGame::getMapBindingEpoch,', source)
        self.assertNotIn("setMapBindingEpoch", source)
        contract = json.loads((ROOT / "tests/fixtures/python_binding_contract.json").read_text(encoding="utf-8"))
        group = next(row for row in contract["groups"] if row["registration"] == "bindFoundationAndSession")
        self.assertEqual(
            group["registrationTokenSha256"],
            sha256(registrationTokens(registrationBody(source, "bindFoundationAndSession")).encode()).hexdigest(),
        )
        self.assertIn("mapBindingEpochReview", contract)
        runner = (ROOT / "test.py").read_text(encoding="utf-8")
        fast = runner.split("FAST_TEST_PREFIXES", 1)[1].split(")", 1)[0]
        self.assertIn('"GameMapBindingEpochSourceTest."', fast)
        self.assertNotIn('"GameMapBindingEpochRuntimeTest."', fast)
        for name in ("GameMapBindingEpochSourceTest", "GameMapBindingEpochRuntimeTest"):
            self.assertIn("class " + name + "(_" + name + "):", runner)
            self.assertIn(name + " as _" + name, runner)
            self.assertIn("del _GameMapBindingEpochSourceTest, _GameMapBindingEpochRuntimeTest", runner)

    def epochRuntimeWithoutNative(self, environment=None, *, required=False, returncode=77):
        import builtins
        import os
        from types import SimpleNamespace
        from unittest import mock

        from tests import test_python_callback_lifecycle as lifecycle

        native_imports = []
        original_import = builtins.__import__

        def deny_native(name, *args, **kwargs):
            if name in {"game", "_game"}:
                native_imports.append(name)
                raise ModuleNotFoundError("native import denied", name=name)
            return original_import(name, *args, **kwargs)

        case = GameMapBindingEpochRuntimeTest(
            "testNativePythonGetterReturnsStableIntegerWithoutAdvancingSceneGeneration"
        )
        if required:
            self.assertTrue(
                callable(getattr(case, "runChild", None)), "The runtime fixture must use the isolated harness"
            )
            run_child = case.runChild
            case.runChild = lambda code: run_child(code, required=True)
        result = unittest.TestResult()
        with mock.patch.dict(os.environ, environment or {}, clear=True), mock.patch.object(
            lifecycle.subprocess, "run", return_value=SimpleNamespace(returncode=returncode, stdout="", stderr="")
        ) as child, mock.patch("builtins.__import__", deny_native):
            case.run(result)
        self.assertEqual([], native_imports)
        self.assertEqual([], result.errors)
        self.assertEqual(1, child.call_count)
        return result, child.call_args

    def testEpochRuntimeDirectDiscoverySkipsMissingNativeWithoutParentImport(self):
        result, call = self.epochRuntimeWithoutNative()
        self.assertEqual(1, result.testsRun)
        self.assertEqual([], result.failures)
        self.assertEqual(1, len(result.skipped))
        self.assertIn("compiled _game module is unavailable", result.skipped[0][1])
        settings = call.kwargs["env"]
        self.assertEqual("dummy", settings["SDL_VIDEODRIVER"])
        self.assertEqual("dummy", settings["SDL_AUDIODRIVER"])
        self.assertEqual("software", settings["SDL_RENDER_DRIVER"])
        self.assertEqual(30, call.kwargs["timeout"])

    def testEpochRuntimeConfiguredOrRequiredMissingNativeFailsInsteadOfSkipping(self):
        for environment, required in (
            ({"GAME_BUILD_DIR": "missing-build"}, False),
            ({"GAME_BUILD_CONFIG": "Release"}, False),
            ({"GAME_MCP_BRANCH_REQUIRED": "1"}, False),
            ({}, True),
        ):
            with self.subTest(environment=environment, required=required):
                result, _call = self.epochRuntimeWithoutNative(environment, required=required)
                self.assertEqual(1, result.testsRun)
                self.assertEqual(1, len(result.failures))
                self.assertEqual([], result.skipped)
                self.assertIn("Configured native epoch runtime is unavailable", result.failures[0][1])

    def testEpochRuntimeChildRetainsAllNativeAssertionsAndReportsChildFailure(self):
        import ast
        import textwrap

        result, call = self.epochRuntimeWithoutNative(returncode=0)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual([], result.skipped)
        child = ast.parse(call.args[0][2])
        owner = next(
            node
            for node in child.body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "owner"
        )
        native = child.body[child.body.index(owner) :]
        expected = ast.parse(textwrap.dedent("""
            owner = game.CGameLoader.loadGame()
            try:
                first = owner.getMapBindingEpoch()
                self.assertIs(type(first), int)
                self.assertEqual(0, first)
                context = owner.getContext()
                generation = context.getTransitionGeneration()
                for _ in range(128):
                    self.assertEqual(first, game.CGame.getMapBindingEpoch(owner))
                self.assertTrue(context.isTransitionGenerationCurrent(generation))
                self.assertFalse(hasattr(game.CGame, "setMapBindingEpoch"))
            finally:
                owner.getContext().shutdown()
            """)).body
        self.assertEqual(
            ast.dump(ast.Module(body=expected, type_ignores=[])), ast.dump(ast.Module(body=native, type_ignores=[]))
        )
        result, _call = self.epochRuntimeWithoutNative(returncode=1)
        self.assertEqual(1, len(result.failures))
        self.assertEqual([], result.skipped)


class GameMapBindingEpochRuntimeTest(unittest.TestCase):
    def runChild(self, code, *, required=False):
        import os

        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        try:
            return PythonCallbackLifecycleTest.runChild(self, code)
        except unittest.SkipTest as error:
            if (
                required
                or os.environ.get("GAME_BUILD_DIR")
                or os.environ.get("GAME_BUILD_CONFIG")
                or os.environ.get("GAME_MCP_BRANCH_REQUIRED") == "1"
            ):
                self.fail("Configured native epoch runtime is unavailable: " + str(error))
            raise

    def testNativePythonGetterReturnsStableIntegerWithoutAdvancingSceneGeneration(self):
        self.runChild("""
            import unittest
            self = unittest.TestCase()
            owner = game.CGameLoader.loadGame()
            try:
                first = owner.getMapBindingEpoch()
                self.assertIs(type(first), int)
                self.assertEqual(0, first)
                context = owner.getContext()
                generation = context.getTransitionGeneration()
                for _ in range(128):
                    self.assertEqual(first, game.CGame.getMapBindingEpoch(owner))
                self.assertTrue(context.isTransitionGenerationCurrent(generation))
                self.assertFalse(hasattr(game.CGame, "setMapBindingEpoch"))
            finally:
                owner.getContext().shutdown()
            """)
