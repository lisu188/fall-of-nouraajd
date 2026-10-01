# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import csv
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Ordered native cases on main f80edd27, before adding diagnostic wrappers.
BASELINE_CASES = {
    "handler": (30, "b52fed9d5b269e53ba035c51fa6085bd85ee02527c0bb457a7a58e37054ca525"),
    "map": (49, "17f592c7f09a057f9c3249babde697470899143ffda78688662f61ab5cfbdf9e"),
}

FIXTURE = r"""
#include "native_test_profile.h"
#include <cstdlib>
#include <stdexcept>

int main(int argc, char **argv) {
    const std::string mode = argc > 1 ? argv[1] : "success";
    CNativeTestProfile profile("fixture");
    if (mode == "interrupt") {
        profile.run("interrupted", [] { std::_Exit(23); });
    }
    if (mode == "return-code") {
        return profile.run("return-code", [] { return 17; });
    }
    if (mode == "sampling-batches") {
        int samples = 0;
        profile.run("unchanged-sampling", [&] {
            for (const char *batch : {"full-budget", "tight-budget", "player-exclusion"}) {
                profile.run(batch, [&] {
                    for (int attempt = 0; attempt < 256; ++attempt) {
                        ++samples;
                    }
                });
            }
        });
        return samples == 768 ? 0 : 5;
    }
    int calls = 0;
    const int result = profile.run("outer", [&] {
        return profile.run("setup", [&] { ++calls; return 42; });
    });
    if (result != 42 || calls != 1) {
        return 1;
    }
    int value = 4;
    int &reference = profile.run("reference", [&]() -> int & { return value; });
    reference += 2;
    if (value != 6) {
        return 2;
    }
    try {
        profile.run("throws", [] { throw std::runtime_error("original exception"); });
        return 3;
    } catch (const std::runtime_error &error) {
        if (std::string(error.what()) != "original exception") {
            return 4;
        }
    }
    if (mode == "success") {
        profile.run("flush", [&] {
            std::ifstream input(std::filesystem::path(GAME_NATIVE_TEST_PROFILE_DIR) / "fixture.tsv");
            std::string line;
            std::string last;
            while (std::getline(input, line)) {
                last = line;
            }
            if (last.find("\tSTART\tflush\t") == std::string::npos) {
                throw std::runtime_error("START was not flushed before its action");
            }
        });
    }
    return 0;
}
"""


class NativeTestProfileSourceTest(unittest.TestCase):
    def testEveryExistingCaseKeepsItsOrderAndMetadataComesFirst(self):
        for suite, (count, digest) in BASELINE_CASES.items():
            source = (ROOT / f"tests/unit/test_{suite}.cpp").read_text(encoding="utf-8")
            main = source[source.rindex("int main() {") :]
            calls = re.findall(r'nativeTestProfile\(\)\.run\("(test\w+)",\s*(test\w+)\);', main)
            self.assertEqual(count, len(calls), suite)
            self.assertTrue(all(name == callback for name, callback in calls), suite)
            names = [name for name, _callback in calls]
            self.assertEqual(digest, hashlib.sha256("\n".join(names).encode()).hexdigest(), suite)
            self.assertFalse(re.search(r"^\s+(test\w+)\(\);", main, re.MULTILINE), suite)
            self.assertIn("return finish_tests();", main)
            if suite == "handler":
                self.assertEqual("testGameplayMetadataIsAvailableBeforePluginLoading", names[0])

    def testProfilesGoIntoTheUploadedSourceCoverageDirectoryWithoutChangingLimits(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        for suite in BASELINE_CASES:
            self.assertRegex(
                cmake,
                rf"target_compile_definitions\({suite}_unit_tests PRIVATE\s+"
                r'GAME_NATIVE_TEST_PROFILE_DIR="\$\{CMAKE_CURRENT_SOURCE_DIR\}/coverage/native-test-profiles"\)',
            )
        self.assertRegex(cmake, r'LABELS "for_unit_tests;unit;\$\{target_name\}"\s+TIMEOUT 60')
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn("coverage/", workflow)

    def testMeasuredHotCasesKeepTheirSamplingCountsAndExposeNestedPhases(self):
        handler = (ROOT / "tests/unit/test_handler.cpp").read_text(encoding="utf-8")
        self.assertTrue('nativeTestProfile().run("primeEncounterFixtureLevels",' in handler)
        for test_name, phases, loops in (
            (
                "test_rng_handler_encounter_candidates_stay_in_stable_power_buckets",
                ("CRngHandler::CRngHandler", "encounter samples(full-budget)", "encounter samples(tight-budget)"),
                2,
            ),
            (
                "test_rng_handler_excludes_player_templates_from_encounters",
                ("CRngHandler::CRngHandler", "encounter samples(player-exclusion)"),
                1,
            ),
        ):
            body = handler.split(f"void {test_name}() {{", 1)[1].split("\n}\n", 1)[0]
            self.assertEqual(loops, body.count("for (int attempt = 0; attempt < 256; attempt++)"))
            for phase in phases:
                self.assertTrue(f'nativeTestProfile().run("{phase}",' in body)
        map_source = (ROOT / "tests/unit/test_map.cpp").read_text(encoding="utf-8")
        race_case = map_source.split("void test_loader_race_overloads_preserve_default_and_attach_race() {", 1)[1]
        race_case = race_case.split("\n}\n", 1)[0]
        self.assertEqual(3, race_case.count('nativeTestProfile().run("CGameLoader::startGameWithPlayer",'))
        self.assertTrue('nativeTestProfile().run("CGameLoader::startRandomGameWithPlayer",' in race_case)
        self.assertEqual(1, race_case.count("CGameLoader::startRandomGameWithPlayer(random_game"))


class NativeTestProfileRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            raise unittest.SkipTest("A standalone existing C++ compiler is unavailable")
        scratch_root = ROOT / "build"
        scratch_root.mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="native-profile-check-", dir=scratch_root)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.scratch = Path(cls.temporary.name)
        cls.output = cls.scratch / "source coverage" / "profiles"
        source = cls.scratch / "fixture.cpp"
        source.write_text(FIXTURE, encoding="utf-8")
        cls.binary = cls.scratch / "fixture"
        definition = f'-DGAME_NATIVE_TEST_PROFILE_DIR="{cls.output.as_posix()}"'
        result = subprocess.run(
            [
                compiler,
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Werror",
                definition,
                "-I",
                str(ROOT / "tests/unit"),
                str(source),
                "-o",
                str(cls.binary),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode:
            (scratch_root / "native-profile-compile-failure.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            raise AssertionError(result.stdout + result.stderr)

    def runFixture(self, mode):
        return subprocess.run([str(self.binary), mode], capture_output=True, text=True, timeout=5)

    def records(self):
        with (self.output / "fixture.tsv").open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream, delimiter="\t"))

    def testReturnsReferencesNestedCallsAndOriginalExceptionsArePreserved(self):
        result = self.runFixture("success")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        records = self.records()
        self.assertEqual(
            [
                ("START", "outer"),
                ("START", "setup"),
                ("DONE", "setup"),
                ("DONE", "outer"),
                ("START", "reference"),
                ("DONE", "reference"),
                ("START", "throws"),
                ("EXCEPTION", "throws"),
                ("START", "flush"),
                ("DONE", "flush"),
            ],
            [(record["event"], record["name"]) for record in records],
        )
        for record in records:
            self.assertEqual("fixture", record["suite"])
            self.assertGreaterEqual(float(record["wallMs"]), 0)
            if os.name == "nt" and record["event"] != "START":
                self.assertEqual(-1, float(record["cpuMs"]))
            else:
                self.assertGreaterEqual(float(record["cpuMs"]), 0)

    def testInterruptedActionsRetainTheirFlushedStart(self):
        result = self.runFixture("interrupt")
        self.assertEqual(23, result.returncode, result.stdout + result.stderr)
        self.assertEqual([("START", "interrupted")], [(row["event"], row["name"]) for row in self.records()])

    def testReturnCodeIsUnchanged(self):
        result = self.runFixture("return-code")
        self.assertEqual(17, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["START", "DONE"], [row["event"] for row in self.records()])

    def testNestedSamplingBatchesRunEveryIterationOnce(self):
        result = self.runFixture("sampling-batches")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            [
                ("START", "unchanged-sampling"),
                ("START", "full-budget"),
                ("DONE", "full-budget"),
                ("START", "tight-budget"),
                ("DONE", "tight-budget"),
                ("START", "player-exclusion"),
                ("DONE", "player-exclusion"),
                ("DONE", "unchanged-sampling"),
            ],
            [(record["event"], record["name"]) for record in self.records()],
        )

    def testUnavailableDiagnosticOutputDoesNotChangeTheAction(self):
        if self.output.exists():
            shutil.rmtree(self.output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text("a file blocks the directory", encoding="utf-8")
        try:
            result = self.runFixture("unavailable")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("profiling file is unavailable", result.stderr)
        finally:
            self.output.unlink()
