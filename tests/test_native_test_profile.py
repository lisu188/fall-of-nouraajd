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
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
# Ordered native cases on main e3d3c90, before adding diagnostic wrappers.
BASELINE_CASES = {
    "handler": (36, "133d76b3db645f21a09e2b55fc738f481318a97c42532b80bb67edba5354a89d"),
    "map": (49, "17f592c7f09a057f9c3249babde697470899143ffda78688662f61ab5cfbdf9e"),
}


class NativeTestProfileSourceTest(unittest.TestCase):
    def testConfiguredFixtureIsRequiredByNativeAndGameplayValidation(self):
        import test as runner

        names = runner.discover_unittest_test_names(["test.py", "NativeTestProfileRuntimeTest"])
        self.assertEqual(5, len(names))
        self.assertEqual([], runner.filter_test_names_by_suite(names, "fast"))
        for suite in ("gameplay", "coverage-safe", "full"):
            self.assertEqual(names, runner.filter_test_names_by_suite(names, suite))
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("add_executable(native_test_profile_fixture tests/unit/native_test_profile_fixture.cpp)", cmake)
        self.assertIn("configure_cpp_target(native_test_profile_fixture)", cmake)
        self.assertIn("list(APPEND GAME_UNIT_TEST_TARGETS native_test_profile_fixture)", cmake)
        self.assertIn('add_test(NAME "for_unit_tests.native_test_profile_contracts"', cmake)
        self.assertIn("NativeTestProfileRuntimeTest -v", cmake)
        self.assertIn(
            'ENVIRONMENT "GAME_NATIVE_TEST_PROFILE_FIXTURE=$<TARGET_FILE:native_test_profile_fixture>"', cmake
        )
        self.assertRegex(cmake, r'LABELS "for_unit_tests;unit;native_test_profile_contracts"\s+TIMEOUT 60')
        fixture = (ROOT / "tests/unit/native_test_profile_fixture.cpp").read_text(encoding="utf-8")
        self.assertIn("for (int attempt = 0; attempt < 256; ++attempt)", fixture)
        self.assertIn("return samples == 768 ? 0 : 5", fixture)

    def testExplicitMissingCompiledFixtureCannotSkipMandatoryContracts(self):
        class MissingFixture(NativeTestProfileRuntimeTest):
            pass

        with tempfile.TemporaryDirectory(prefix="nouraajd-profile-preflight-") as directory:
            missing = Path(directory) / "missing-fixture"
            with mock.patch.dict(os.environ, {"GAME_NATIVE_TEST_PROFILE_FIXTURE": str(missing)}):
                with self.assertRaisesRegex(AssertionError, "Configured native profiling fixture is unavailable"):
                    MissingFixture.setUpClass()

    def testEveryExistingCaseKeepsItsOrderAndMetadataComesFirst(self):
        for suite, (count, digest) in BASELINE_CASES.items():
            source = (ROOT / f"tests/unit/test_{suite}.cpp").read_text(encoding="utf-8")
            main = source[source.rindex("int main() {") :]
            calls = re.findall(
                r'nativeTestProfile\(\)\.run\("(test\w+)",\s*'
                r'(?:(test\w+)\);|\[&\] \{\s*runTimedGuiCancellationTest\("(test\w+)",\s*(test\w+)\);\s*\}\);)',
                main,
            )
            self.assertEqual(count, len(calls), suite)
            self.assertTrue(
                all(
                    name == callback if callback else name == timed_name == timed_callback
                    for name, callback, timed_name, timed_callback in calls
                ),
                suite,
            )
            names = [name for name, *_callbacks in calls]
            self.assertEqual(digest, hashlib.sha256("\n".join(names).encode()).hexdigest(), suite)
            self.assertFalse(re.search(r"^\s+(test\w+)\(\);", main, re.MULTILINE), suite)
            self.assertIn("return finish_tests();", main)
            if suite == "handler":
                self.assertEqual("testGameplayMetadataIsAvailableBeforePluginLoading", names[0])
                self.assertEqual(3, sum(bool(timed_name) for _name, _callback, timed_name, _timed_callback in calls))

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
        explicit_fixture = os.environ.get("GAME_NATIVE_TEST_PROFILE_FIXTURE")
        if explicit_fixture:
            binary = Path(explicit_fixture)
            if not binary.is_file():
                raise AssertionError("Configured native profiling fixture is unavailable: " + str(binary))
        else:
            build_root = Path(os.environ.get("GAME_BUILD_DIR", ROOT / "cmake-build-release"))
            if not build_root.is_absolute():
                build_root = ROOT / build_root
            executable_name = "native_test_profile_fixture.exe" if os.name == "nt" else "native_test_profile_fixture"
            build_config = os.environ.get("GAME_BUILD_CONFIG")
            candidates = [build_root / build_config / executable_name] if build_config else []
            if os.name == "nt" and not build_config:
                candidates.append(build_root / "Release" / executable_name)
            candidates.append(build_root / executable_name)
            binary = next((path for path in candidates if path.is_file()), None)
            if binary is None:
                raise unittest.SkipTest("Build native_test_profile_fixture through the for_unit_tests target")
        scratch_root = ROOT / "build"
        scratch_root.mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="native-profile-check-", dir=scratch_root)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.scratch = Path(cls.temporary.name)
        cls.output = cls.scratch / "source coverage" / "profiles"
        cls.binary = binary.resolve()

    def runFixture(self, mode):
        return subprocess.run([str(self.binary), mode, str(self.output)], capture_output=True, text=True, timeout=5)

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


if __name__ == "__main__":
    unittest.main()
