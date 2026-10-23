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


class GameMapBindingEpochRuntimeTest(unittest.TestCase):
    def testNativePythonGetterReturnsStableIntegerWithoutAdvancingSceneGeneration(self):
        import game

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
