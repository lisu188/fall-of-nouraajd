# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fast source contracts; the corresponding native wait and save cases run in CI."""

import ast
from pathlib import Path
import re
import unittest

from tests.cpp_bindings import CPP_TOKENS

ROOT = Path(__file__).resolve().parents[1]
WAIT_CASES = (
    "testWaitStateSnapshotsPreserveRemainingDurationWithoutRebasingLiveTime",
    "testWaitStateRejectsInvalidDurationsMutationsAndDuplicateLeases",
    "testScriptWaitFlowCompletesAndRejectsInvalidObjectArguments",
    "testScriptWaitSurvivesFailedSaveResourceBindingWithoutDispatchingMapChanges",
    "testScriptWaitCancellationAndMapBindingLossFreezeRemainingTime",
    "testSyncScriptWaitReleasesTheFinalGameOwner",
)


def functionBody(source, anchor):
    opening = source.index("{", source.index(anchor))
    depth = 1
    for token in CPP_TOKENS.finditer(source, opening + 1):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : token.start()]
    raise AssertionError(anchor)


class SavedWaitSourceTest(unittest.TestCase):
    def read(self, path):
        source = ROOT / path
        self.assertTrue(source.is_file(), f"Missing saved-wait source: {path}")
        return source.read_text(encoding="utf-8")

    def testSnapshotsReflectOnlyRemainingDurationAndUseMonotonicCeiling(self):
        header = self.read("src/object/CWaitState.h")
        metadata = header.split("V_META(", 1)[1].split("public:", 1)[0]
        self.assertEqual(["remainingMilliseconds"], re.findall(r"V_PROPERTY\(\w+,\s*\w+,\s*(\w+)", metadata))
        self.assertIn("using Clock = std::chrono::steady_clock;", header)
        source = self.read("src/object/CWaitState.cpp")
        remaining = functionBody(source, "int CWaitState::remainingLocked()")
        self.assertIn("if (!running)", remaining)
        self.assertIn("std::chrono::ceil<std::chrono::milliseconds>(deadline - timeSource())", remaining)
        self.assertNotIn("deadline =", remaining)
        self.assertNotIn("running =", remaining)
        getter = functionBody(source, "int CWaitState::getRemainingMilliseconds()")
        self.assertIn("std::lock_guard lock(waitMutex);", getter)
        self.assertIn("return remainingLocked();", getter)

    def testWaitLeaseRejectsMutationAndInvalidationRetainsOwnershipUntilUnwind(self):
        source = self.read("src/object/CWaitState.cpp")
        setter = functionBody(source, "void CWaitState::setRemainingMilliseconds(")
        self.assertIn("if (activeLease)", setter)
        self.assertLess(setter.index("if (activeLease)"), setter.index("remainingMilliseconds = value;"))
        start = functionBody(source, "std::optional<CWaitState::Lease> CWaitState::tryStart()")
        self.assertIn("if (activeLease)", start)
        self.assertIn("return std::nullopt;", start)
        invalidation = functionBody(source, "void CWaitState::invalidateForMapBindingChange()")
        self.assertIn("remainingMilliseconds = remainingLocked();", invalidation)
        self.assertIn("running = false;", invalidation)
        self.assertIn("invalidated = true;", invalidation)
        self.assertNotIn("activeLease.reset()", invalidation)
        pause = functionBody(source, "void CWaitState::pause(")
        self.assertIn("if (activeLease != lease)", pause)
        self.assertIn("activeLease.reset();", pause)
        complete = functionBody(source, "bool CWaitState::complete(")
        self.assertIn("activeLease != lease || invalidated || !running || remainingLocked() != 0", complete)

    def testStrictSetterChecksExactPythonIntegerBeforeConversionAndNativeMutation(self):
        source = self.read("src/core/bindings/CModuleGameplay.cpp")
        self.assertIn('py::class_<CWaitState, CGameObject, std::shared_ptr<CWaitState>>(m, "CWaitState"', source)
        setter = functionBody(source, '.def("setRemainingMilliseconds",')
        for expression in (
            "!PyLong_CheckExact(value.ptr())",
            "value.cast<long long>()",
            "milliseconds < 0 || milliseconds > CWaitState::MAX_MILLISECONDS",
            "state.setRemainingMilliseconds(static_cast<int>(milliseconds));",
        ):
            self.assertIn(expression, setter)
        self.assertLess(setter.index("!PyLong_CheckExact"), setter.index("value.cast<long long>()"))
        self.assertLess(setter.index("milliseconds < 0"), setter.index("state.setRemainingMilliseconds"))
        runtime = self.read("tests/test_wait_state.py")
        self.assertIn("(True, False, 1.5, '4', None, -1, 60001, 10 ** 100)", runtime)

    def testDispatcherRequiresExactlyOneNativeStateToken(self):
        source = self.read("src/handler/CGuiHandler.cpp")
        self.assertIn('operation == "waitMilliseconds"', source)
        branch = functionBody(source, 'else if (operation == "waitMilliseconds")')
        for expression in (
            "!arguments.is_array()",
            "arguments.size() != 1",
            "!arguments.at(0).is_object()",
            "arguments.at(0).size() != 1",
            '!arguments.at(0).contains("__nativeObject")',
            '!arguments.at(0).at("__nativeObject").is_string()',
            "co_await self->waitMillisecondsAsync(flowObjectArgument<CWaitState>(*flow, arguments, 0))",
        ):
            self.assertIn(expression, branch)
        self.assertNotIn("get<int>", branch)
        world = self.read("src/core/bindings/CModuleWorld.cpp")
        self.assertIn('.def("waitMilliseconds", &CGuiHandler::waitMilliseconds, py::arg("state")', world)

    def testAwaitDropsGameOwnerAndChecksCapturedBindingBeforeCompletion(self):
        source = self.read("src/handler/CGuiHandler.cpp")
        self.assertIn("vstd::task<bool> CGuiHandler::waitMillisecondsAsync(", source)
        body = functionBody(source, "vstd::task<bool> CGuiHandler::waitMillisecondsAsync(")
        for expression in (
            "state->getGame() != game",
            "const auto context = game->getContext();",
            "const auto map = game->getMap();",
            "context->captureTransitionGeneration()",
            "ScriptWaitOwner owner{game, state, *lease};",
            'game->connect("mapBindingChanged", state, "invalidateForMapBindingChange");',
            "!context->isTransitionGenerationCurrent(generation)",
            "game->getMap() != map",
            "state->isInvalidated(*lease)",
            "!state->complete(*lease)",
        ):
            self.assertIn(expression, body)
        delay = body.index("co_await vstd::sleepFor(")
        self.assertLess(body.index("game.reset();"), delay)
        self.assertLess(body.index("state->isInvalidated(*lease)"), body.index("!state->complete(*lease)"))
        owner = functionBody(source, "struct ScriptWaitOwner")
        self.assertIn("std::weak_ptr<CGame> game;", owner)
        for declaration in (
            "ScriptWaitOwner(const ScriptWaitOwner &) = delete;",
            "ScriptWaitOwner &operator=(const ScriptWaitOwner &) = delete;",
            "ScriptWaitOwner(ScriptWaitOwner &&) = delete;",
            "ScriptWaitOwner &operator=(ScriptWaitOwner &&) = delete;",
        ):
            self.assertIn(declaration, owner)
        self.assertIn('owner->disconnect("mapBindingChanged", state, "invalidateForMapBindingChange");', owner)
        self.assertIn("state->pause(lease);", owner)

    def testActualMapBindingSignalIsSynchronousAndTemporaryResourceBindingsAreSilent(self):
        source = self.read("src/core/CGame.cpp")
        installed = functionBody(source, "void CGame::setMap(")
        self.assertIn("bindingChanged = this->map != map;", installed)
        self.assertIn("if (bindingChanged)", installed)
        self.assertIn('signal<true>("mapBindingChanged");', installed)
        self.assertLess(installed.index("this->map = map;"), installed.index('signal<true>("mapBindingChanged");'))
        temporary = functionBody(source, "void CGame::setMapForResourceLoad(")
        self.assertNotIn("signal", temporary)
        self.assertNotIn("advanceTransitionGeneration", temporary)
        reserved = self.read("src/object/CGameObject.cpp")
        self.assertIn('"mapBindingChanged"', reserved)
        self.assertIn("FN_TYPE(CWaitState, CGameObject)", self.read("src/core/CGameplayTypeTable.h"))

    def testSixNativeCasesAreRegisteredOnceAndSnapshotUsesTypedJson(self):
        source = self.read("tests/unit/test_handler.cpp")
        profile = self.read("tests/test_native_test_profile.py")
        self.assertTrue(all("void " + name + "()" in source for name in WAIT_CASES), "Missing native wait cases")
        for name in WAIT_CASES:
            with self.subTest(case=name):
                self.assertEqual(1, source.count("void " + name + "()"))
                self.assertEqual(1, source.count('nativeTestProfile().run("' + name + '"'))
                self.assertEqual(1, profile.count('"' + name + '"'))
        snapshot = functionBody(source, "void " + WAIT_CASES[0] + "()")
        self.assertIn('properties.at("remainingMilliseconds").is_number_integer()', snapshot)
        self.assertIn('properties.at("remainingMilliseconds").get<int>() == 2500', snapshot)
        self.assertNotIn('properties.at("remainingMilliseconds") ==', snapshot)
        self.assertIn("CSerialization::serializeExpected(coordinator)", snapshot)
        self.assertIn("CSerialization::deserializeExpected<std::shared_ptr<CGameObject>>", snapshot)
        self.assertIn("std::chrono::hours(48)", snapshot)
        cancellation = functionBody(source, "void " + WAIT_CASES[4] + "()")
        self.assertIn("variant < 4", cancellation)
        self.assertIn("variant == 3", cancellation)
        self.assertIn("game->setMap(original);", cancellation)
        self.assertIn("state->getRemainingMilliseconds() == 58766", cancellation)

    def testSerializationPerformanceGuardHasFiniteActualCodecAndClockBudgets(self):
        source = self.read("tests/unit/test_serialization_performance.cpp")
        name = "testSavedWaitSnapshotsHaveBoundedClockWorkAndOneAliasDefinition"
        self.assertIn("void " + name + "()", source)
        body = functionBody(source, "void " + name + "()")
        for expression in (
            "constexpr std::size_t snapshotCount = 64;",
            "index < snapshotCount",
            "CSerialization::serializeExpected(owner)",
            "count == 1 && countSerializedCreatures(*snapshot) == 1 && clockReads == before + 1",
            "definitions == snapshotCount && clockReads == initialClockReads + snapshotCount",
            "EffectSerializationProbe::serializationVisits == snapshotCount",
            "bytes == firstBytes",
            'coordinator->setObjectProperty("pendingWait", state);',
            'owner->setObjectProperty("pendingWaitOwner", coordinator);',
            'owner->setObjectProperty("waitOwnerAlias", coordinator);',
            "restoredOwner == ownerAlias && loaded && loaded != state",
            "clockReads == beforeRestore",
            "std::chrono::hours(48)",
            "std::chrono::hours(24)",
            "loaded->getRemainingMilliseconds() == 1",
        ):
            self.assertIn(expression, body)
        self.assertNotIn("sleep", body)
        self.assertEqual(1, body.count('setObjectProperty("pendingWait", state)'))
        entry = functionBody(source, "void run_serialization_performance_tests()")
        self.assertEqual(1, entry.count(name + "();"))
        cmake = self.read("CMakeLists.txt")
        self.assertIn("tests/unit/test_serialization_performance.cpp", cmake)

    def testSnapshotFixtureInstallsInjectedClockBeforeDefaultBuilders(self):
        fixture = functionBody(
            self.read("tests/unit/test_serialization_performance.cpp"),
            "void testSavedWaitSnapshotsHaveBoundedClockWorkAndOneAliasDefinition()",
        )
        registration = functionBody(
            self.read("src/handler/CObjectHandler.cpp"), "void CObjectHandler::registerType("
        ).split("// Persistent registration path:", 1)[1]
        self.assertIn("constructors.insert(", registration)
        self.assertNotIn("insert_or_assign", registration)
        injected = fixture.index('registerType("CWaitState"')
        bulk = fixture.index("for (const auto &[name, builder] : *CTypes::builders())")
        self.assertLess(injected, bulk, "First-registration-wins must retain the injected native clock.")
        self.assertLess(bulk, fixture.index('createObject<CWaitState>("CWaitState")'))
        self.assertEqual(1, fixture.count('registerType("CWaitState"'))
        self.assertIn("std::make_shared<CWaitState>(timeSource)", fixture)
        self.assertIn("clockReads == 1", fixture)
        self.assertLess(fixture.index("state->tryStart()"), fixture.index("clockReads == 1"))
        self.assertLess(fixture.index("clockReads == 1"), fixture.index("const auto initialClockReads"))

    def testRunnerRegistersSourceAndRuntimeExactlyOnceWithSeparateSuites(self):
        runner = ast.parse(self.read("test.py"))
        classes = [node for node in ast.walk(runner) if isinstance(node, ast.ClassDef)]
        imports = [node for node in ast.walk(runner) if isinstance(node, ast.ImportFrom)]
        assignments = {
            node.targets[0].id: node.value
            for node in runner.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        }
        fast = ast.literal_eval(assignments["FAST_TEST_PREFIXES"])
        gameplay = tuple(
            item.value for item in assignments["GAMEPLAY_TEST_PREFIXES"].elts if isinstance(item, ast.Constant)
        )
        for name, module in (
            ("SavedWaitSourceTest", "tests.test_saved_wait_source"),
            ("WaitStateRuntimeTest", "tests.test_wait_state"),
        ):
            self.assertEqual(1, sum(node.name == name for node in classes))
            selected = [item for node in imports if node.module == module for item in node.names if item.name == name]
            self.assertEqual(["_" + name], [item.asname for item in selected])
            deleted = [
                node
                for node in ast.walk(runner)
                if isinstance(node, ast.Delete)
                for target in node.targets
                if isinstance(target, ast.Name) and target.id == "_" + name
            ]
            self.assertEqual(1, len(deleted))
        self.assertEqual(1, fast.count("SavedWaitSourceTest."))
        self.assertNotIn("WaitStateRuntimeTest.", fast)
        self.assertEqual(1, gameplay.count("WaitStateRuntimeTest."))


if __name__ == "__main__":
    unittest.main()
