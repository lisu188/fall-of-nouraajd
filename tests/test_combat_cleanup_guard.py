# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable source contracts and an opt-in extracted C++ cleanup guard probe."""

from pathlib import Path
import ast
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def fightCleanupGuardProbeSource(source=None):
    if source is None:
        source = (ROOT / "src/handler/CFightHandler.cpp").read_text(encoding="utf-8")
    start = source.index("class FightControllerEndGuard {")
    guard = source[start : source.index("\n};", start) + len("\n};")]
    return (
        r"""
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <memory>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>
static bool failNextAllocation = false;
void *operator new(std::size_t size) {
    if (failNextAllocation) {
        failNextAllocation = false;
        throw std::bad_alloc();
    }
    if (auto allocation = std::malloc(size ? size : 1))
        return allocation;
    throw std::bad_alloc();
}
void operator delete(void *allocation) noexcept { std::free(allocation); }
void operator delete(void *allocation, std::size_t) noexcept { std::free(allocation); }
class CCreature {};
class CFightController {
  public:
    virtual ~CFightController() = default;
    virtual void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) {}
    virtual void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) {}
};
"""
        + guard
        + r"""
class CleanupProbe : public CFightController {
  public:
    const char *failure = nullptr;
    const char *startFailure = nullptr;
    bool resourceAcquired = false;
    std::shared_ptr<CCreature> expectedOpponent;
    int starts = 0;
    int ends = 0;
    void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        ++starts;
        resourceAcquired = true;
        if (startFailure)
            throw std::runtime_error(startFailure);
    }
    void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature> opponent) override {
        ++ends;
        resourceAcquired = false;
        if (opponent != expectedOpponent)
            throw std::logic_error("wrong cleanup opponent");
        if (failure)
            throw std::runtime_error(failure);
    }
};
class PrimaryCancellation {};
int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    const std::string mode = argv[1];
    auto actor = std::make_shared<CCreature>();
    auto originalOpponent = std::make_shared<CCreature>();
    auto currentOpponent = originalOpponent;
    auto first = std::make_shared<CleanupProbe>();
    auto second = std::make_shared<CleanupProbe>();
    auto third = std::make_shared<CleanupProbe>();
    first->failure = "first cleanup failure";
    second->failure = "second cleanup failure";
    first->expectedOpponent = originalOpponent;
    second->expectedOpponent = third->expectedOpponent = originalOpponent;
    if (mode == "allocate-pointer" || mode == "allocate-value") {
        bool allocationFailed = false;
        {
            FightControllerEndGuard guard;
            failNextAllocation = true;
            try {
                if (mode == "allocate-pointer")
                    guard.start(first, actor, &currentOpponent);
                else
                    guard.start(first, actor, originalOpponent);
            } catch (const std::bad_alloc &) {
                allocationFailed = true;
            }
            failNextAllocation = false;
        }
        return allocationFailed && first->starts == 0 && first->ends == 0 && !first->resourceAcquired ? 0 : 4;
    }
    if (mode == "start-pointer" || mode == "start-value") {
        const bool firstFails = mode == "start-pointer";
        (firstFails ? first : second)->startFailure = "primary start failure";
        bool originalStartPreserved = false;
        try {
            FightControllerEndGuard guard;
            guard.start(first, actor, &currentOpponent);
            guard.start(second, actor, originalOpponent);
            guard.start(third, actor, originalOpponent);
        } catch (const std::runtime_error &failure) {
            originalStartPreserved = std::string(failure.what()) == "primary start failure";
        }
        return originalStartPreserved && first->starts == 1 && first->ends == 1 &&
                       second->starts == (firstFails ? 0 : 1) && second->ends == (firstFails ? 0 : 1) &&
                       third->starts == 0 && third->ends == 0 && !first->resourceAcquired && !second->resourceAcquired
                   ? 0
                   : 5;
    }
    auto start = [&](FightControllerEndGuard &guard) {
        guard.start(first, actor, &currentOpponent);
        guard.start(second, actor, originalOpponent);
        guard.start(third, actor, originalOpponent);
        guard.start(nullptr, actor, originalOpponent);
        currentOpponent = std::make_shared<CCreature>();
        first->expectedOpponent = currentOpponent;
    };
    bool originalPreserved = false;
    if (mode == "finish") {
        FightControllerEndGuard guard;
        start(guard);
        try {
            guard.endAll();
        } catch (const std::runtime_error &failure) {
            originalPreserved = std::string(failure.what()) == "first cleanup failure";
        }
        guard.endAll();
    } else {
        try {
            FightControllerEndGuard guard;
            start(guard);
            if (mode == "cancel")
                throw PrimaryCancellation{};
            throw std::runtime_error("primary combat failure");
        } catch (const PrimaryCancellation &) {
            originalPreserved = mode == "cancel";
        } catch (const std::runtime_error &failure) {
            originalPreserved = mode == "combat" && std::string(failure.what()) == "primary combat failure";
        }
    }
    if (!originalPreserved || first->starts != 1 || second->starts != 1 || third->starts != 1 ||
        first->ends != 1 || second->ends != 1 || third->ends != 1)
        return 3;
    return 0;
}
"""
    )


class CombatCleanupGuardSourceTest(unittest.TestCase):
    def guardSource(self):
        source = (ROOT / "src/handler/CFightHandler.cpp").read_text(encoding="utf-8")
        start = source.index("class FightControllerEndGuard {")
        return source[start : source.index("\n};", start)]

    def testDestructorContainsCleanupErrorsDuringPrimaryUnwind(self):
        guard = self.guardSource()
        destructor = guard.split("~FightControllerEndGuard()", 1)[1].split("\n    void start(", 1)[0]
        self.assertTrue(destructor.lstrip().startswith("noexcept"))
        self.assertRegex(destructor, r"try\s*\{\s*endAll\(\);\s*\}\s*catch\s*\(\.\.\.\)")

    def testBothStartOverloadsOwnCleanupBeforeCallingUserCode(self):
        starts = re.findall(r"void start\([^{}]*\) \{(.*?)\n    \}", self.guardSource(), re.DOTALL)
        self.assertEqual(2, len(starts))
        for start in starts:
            self.assertLess(start.index("startedControllers.push_back("), start.index("controller->start("))

    def testNativeLifecycleRegressionsAreRegisteredUsingOrdinaryCombat(self):
        source = (ROOT / "tests/unit/test_allied_combat.cpp").read_text(encoding="utf-8")
        names = (
            "testCombatCleanupExceptionsEndEveryControllerOnce",
            "testCombatCleanupPreservesPrimaryFailureAndCancellation",
            "testCombatOwnsPartialControllerStartsAndPreservesTheirFailure",
            "testRejectedCombatAdmissionDoesNotStartOrEndControllers",
        )
        for name in names:
            self.assertIn("void " + name + "()", source)
            self.assertIn("    " + name + "();", source)
        cleanup_tests = source[source.index("void " + names[0]) : source.index("} // namespace")]
        self.assertIn("CFightHandler::fightManyWithAlliesResultAsync(", cleanup_tests)
        self.assertNotIn("fightOneRound", cleanup_tests)
        self.assertNotIn("fightManyProtecting", cleanup_tests)

    def testOnlyPortableSourceChecksAreRegisteredInFast(self):
        source = (ROOT / "test.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        prefixes = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "FAST_TEST_PREFIXES" for target in node.targets)
        )
        self.assertIn("CombatCleanupGuardSourceTest.", prefixes)
        self.assertNotIn("CombatCleanupGuardNativeProbeTest.", prefixes)
        for name in ("CombatCleanupGuardSourceTest", "CombatCleanupGuardNativeProbeTest"):
            self.assertIn("class " + name + "(_" + name + "):", source)
            self.assertIn(name + " as _" + name, source)


@unittest.skipUnless(os.environ.get("GAME_RUN_FIGHT_CLEANUP_GUARD_PROBE") == "1", "Tiny cleanup guard probe is opt-in")
class CombatCleanupGuardNativeProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "posix":
            raise unittest.SkipTest("The isolated cleanup guard probe requires a POSIX compiler")
        compiler = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            raise unittest.SkipTest("No C++ compiler is available for the isolated cleanup guard probe")
        cls.temporary = tempfile.TemporaryDirectory(prefix="nouraajd-cleanup-guard-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.executable = Path(cls.temporary.name) / "cleanup-guard"
        result = subprocess.run(
            [compiler, "-std=c++23", "-x", "c++", "-", "-o", str(cls.executable)],
            input=fightCleanupGuardProbeSource(),
            text=True,
            capture_output=True,
            timeout=30,
        )
        if result.returncode:
            raise AssertionError("Actual cleanup guard failed to compile:\n" + result.stderr[-700:])
        if cls.executable.stat().st_size >= 1024 * 1024:
            raise AssertionError("The isolated cleanup guard executable exceeded its one-MiB artifact budget")

    def runProbe(self, mode):
        import resource

        result = subprocess.run(
            [str(self.executable), mode],
            text=True,
            capture_output=True,
            timeout=5,
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)),
        )
        self.assertEqual(0, result.returncode, result.stderr[-600:])
        self.assertEqual("", result.stdout)
        self.assertEqual("", result.stderr)

    def testExplicitFinishReportsFirstCleanupErrorAfterEveryEndAndRemainsIdempotent(self):
        self.runProbe("finish")

    def testDestructorPreservesPrimaryCombatAndCancellationFailures(self):
        for mode in ("combat", "cancel"):
            with self.subTest(mode=mode):
                self.runProbe(mode)

    def testPartialStartsAreOwnedAndPreserveTheirFailureDespiteThrowingCleanup(self):
        for mode in ("start-pointer", "start-value"):
            with self.subTest(mode=mode):
                self.runProbe(mode)

    def testEntryAllocationFailureInvokesNeitherStartNorEnd(self):
        for mode in ("allocate-pointer", "allocate-value"):
            with self.subTest(mode=mode):
                self.runProbe(mode)
