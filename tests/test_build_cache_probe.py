# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import probe_build_cache as probe

OBJECTS = (
    "CMakeFiles/game_binding_objects.dir/src/core/bindings/CModuleWorld.cpp.o",
    "CMakeFiles/game_core_objects.dir/Unity/unity_0_cxx.cxx.o",
    "CMakeFiles/random_map_test_objects.dir/tests/unit/test_tile_recipes.cpp.o",
)


class CacheProbeSelectionTest(unittest.TestCase):
    def testCountersUseTheScopedCacheAndRetainOnlyRequiredNumbers(self):
        configuration = {"GAME_CCACHE_DIR": "/project/.cache/ccache"}
        counters = {"direct_cache_hit": 3, "preprocessed_cache_hit": 2, "cache_miss": 1}
        with mock.patch.object(
            probe, "cacheStatistics", return_value={"counters": {**counters, "unrelated": 42}}
        ) as stats:
            self.assertEqual(counters, probe.cacheCounters(configuration))
        stats.assert_called_once_with("ccache", configuration)

    def testLongestCompletedObjectInEachRoleUsesItsLatestRecord(self):
        lines = [f"0\t100000\t1\t{path}\thash{index}" for index, path in enumerate(OBJECTS)]
        lines += [
            f"0\t10\t2\t{OBJECTS[0]}\tnew-command",
            "0\t80\t1\tCMakeFiles/game_binding_objects.dir/src/core/CModule.cpp.o\talternative",
            "0\t900000\t1\tCMakeFiles/game_binding_objects.dir/cmake_pch.hxx.gch\tpch",
            "0\t900000\t1\tlibgame_core.so\tlink",
            "bad entry",
        ]
        selected = probe.selectObjects("# ninja log v7\n" + "\n".join(lines))
        self.assertEqual(["binding", "unity", "test"], [sample["role"] for sample in selected])
        self.assertTrue(selected[0]["object"].endswith("CModule.cpp.o"))
        self.assertEqual(0.08, selected[0]["prior_edge_seconds"])
        self.assertEqual(OBJECTS[1:], tuple(sample["object"] for sample in selected[1:]))

    def testMissingRoleFailsBeforeAnyCompile(self):
        with self.assertRaisesRegex(ValueError, "No completed binding"):
            probe.selectObjects("# ninja log v7\n")

    def testCoverageWithoutUnityUsesAnOrdinaryCoreObjectAndLabelsIt(self):
        core = "CMakeFiles/game_core_objects.dir/src/core/CMap.cpp.o"
        paths = (OBJECTS[0], core, OBJECTS[2])
        selected = probe.selectObjects(
            "\n".join(f"0\t10000\t1\t{path}\thash{index}" for index, path in enumerate(paths))
        )
        self.assertEqual(["binding", "core", "test"], [sample["role"] for sample in selected])
        self.assertFalse(selected[1]["unity"])
        self.assertEqual(core, selected[1]["object"])

    def testUnityIsPreferredEvenWhenAnOrdinaryCoreObjectWasSlower(self):
        lines = [f"0\t1000\t1\t{path}\thash{index}" for index, path in enumerate(OBJECTS)]
        lines.append("0\t100000\t1\tCMakeFiles/game_core_objects.dir/src/handler/CLuaHandler.cpp.o\tseparate")
        selected = probe.selectObjects("\n".join(lines))
        self.assertEqual("unity", selected[1]["role"])
        self.assertTrue(selected[1]["unity"])
        self.assertEqual(OBJECTS[1], selected[1]["object"])

    def testCommandMustBeOneExplicitCompileOfTheSelectedOutput(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory).resolve()
            selected = build / "selected.o"
            good = f'"/tools/compiler path/c++" -DNAME="two words" -c source.cpp -o "{selected}"'
            self.assertEqual("/tools/compiler path/c++", probe.compileArguments(good, build, selected)[0])
            for command in (
                good + " && rm source.cpp",
                good + ";touch source.cpp",
                good + "\nrm source.cpp",
                good + " $(touch source.cpp)",
                good.replace(" -c ", " "),
                good.replace(str(selected), str(build / "different.o")),
            ):
                with self.subTest(command=command), self.assertRaises(ValueError):
                    probe.compileArguments(command, build, selected)


@unittest.skipUnless(sys.platform == "linux", "Object replay is limited to Linux")
class CacheProbeReplayTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="nouraajd-cache-probe-test-")
        self.addCleanup(temporary.cleanup)
        self.build = Path(temporary.name).resolve()
        self.arguments = argparse.Namespace(
            build_dir=str(self.build), output=str(self.build / "report.json"), replay_objects=True, timeout=60
        )
        for name in OBJECTS:
            path = self.build / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"reproducible object")
        (self.build / ".ninja_log").write_text(
            "# ninja log v7\n" + "".join(f"0\t100000\t1\t{path}\thash{index}\n" for index, path in enumerate(OBJECTS)),
            encoding="utf-8",
        )
        self.counters = {"direct_cache_hit": 0, "preprocessed_cache_hit": 0, "cache_miss": 0}

    def runProbe(self, replay=None, clock=None):
        def hit(arguments, build, timeout):
            self.counters["direct_cache_hit"] += 1
            return 0

        with (
            mock.patch.object(probe, "readConfiguration", return_value={}),
            mock.patch.object(probe, "cacheCounters", side_effect=lambda configuration: dict(self.counters)),
            mock.patch.object(
                probe.subprocess,
                "check_output",
                side_effect=lambda arguments, **kwargs: f'c++ -c source.cpp -o "{arguments[-1]}"',
            ),
            mock.patch.object(probe, "runCommand", side_effect=replay or hit) as compiler,
            mock.patch.object(probe.time, "monotonic", side_effect=clock or list(range(12))),
            mock.patch("builtins.print"),
        ):
            result = probe.runProbe(self.arguments)
        return result, json.loads(Path(self.arguments.output).read_text()), compiler.call_count

    def testThreeRealObjectPathsRequireHitsAndByteIdentity(self):
        result, report, calls = self.runProbe()
        self.assertEqual(0, result)
        self.assertEqual(6, calls)
        self.assertEqual("passed", report["status"])
        self.assertEqual(0.01, report["aggregate_observed_ratio"])
        self.assertTrue(report["observed_80_percent_reduction"])
        self.assertIn("whole-build speedup is unproven", report["timing_note"])
        self.assertEqual(3, report["priming_seconds"])
        for sample in report["samples"]:
            self.assertEqual(sample["sha256_before"], sample["sha256_after"])
            self.assertEqual(1, sample["counter_delta"]["direct_cache_hit"])
            self.assertEqual(0, sample["counter_delta"]["cache_miss"])
            self.assertEqual(sample["priming"]["sha256_before"], sample["priming"]["sha256_after"])

    def testTimingIsSupplementalAndNeverWeakensTheCacheHitGate(self):
        result, report, calls = self.runProbe(clock=[0, 1, 2, 92, 100, 101, 102, 192, 200, 201, 202, 292])
        self.assertEqual(0, result)
        self.assertEqual(6, calls)
        self.assertFalse(report["observed_80_percent_reduction"])
        self.assertEqual(0.9, report["aggregate_observed_ratio"])

    def testColdPrimeIsSeparateFromTheVerifiedWarmHit(self):
        def prime_then_hit(arguments, build, timeout):
            calls = sum(self.counters.values())
            self.counters["cache_miss" if calls % 2 == 0 else "direct_cache_hit"] += 1
            return 0

        result, report, calls = self.runProbe(replay=prime_then_hit)
        self.assertEqual(0, result)
        self.assertEqual(6, calls)
        for sample in report["samples"]:
            self.assertEqual(1, sample["priming"]["counter_delta"]["cache_miss"])
            self.assertEqual(1, sample["counter_delta"]["direct_cache_hit"])
            self.assertEqual(0, sample["counter_delta"]["cache_miss"])

    def testMissAfterPrimingStopsRemainingCompilesAndPreservesDiagnostics(self):
        def miss(arguments, build, timeout):
            self.counters["cache_miss"] += 1
            return 0

        result, report, calls = self.runProbe(replay=miss)
        self.assertEqual(1, result)
        self.assertEqual(2, calls)
        self.assertEqual("failed", report["status"])
        self.assertIn("not exactly one cache hit", report["error"])
        self.assertIsNone(report["observed_80_percent_reduction"])

    def testChangedBytesFailEvenWhenTheCacheReportsAHit(self):
        def changed(arguments, build, timeout):
            self.counters["direct_cache_hit"] += 1
            (build / arguments[-1]).write_bytes(b"changed object")
            return 0

        result, report, calls = self.runProbe(replay=changed)
        self.assertEqual(1, result)
        self.assertEqual(1, calls)
        self.assertIn("object bytes changed", report["error"])

    def testExplicitOptInIsRequiredBeforeCommandsAreRead(self):
        self.arguments.replay_objects = False
        result, report, calls = self.runProbe()
        self.assertEqual(1, result)
        self.assertEqual(0, calls)
        self.assertIn("explicit --replay-objects", report["error"])

    def testTimeoutKeepsSampleHashesAndCacheCounters(self):
        result, report, calls = self.runProbe(replay=subprocess.TimeoutExpired("compile", 60))
        self.assertEqual(1, result)
        self.assertEqual(1, calls)
        self.assertEqual(1, len(report["samples"]))
        self.assertIn("60-second timeout", report["error"])
        self.assertIn("sha256_after", report["samples"][0]["priming"])
        self.assertIn("counter_delta", report["samples"][0]["priming"])

    def testSymbolicLinksCannotEscapeTheBuild(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "protected.o"
            outside.write_bytes(b"protected")
            link = self.build / "escape.o"
            link.symlink_to(outside)
            with self.assertRaises(ValueError):
                probe.objectPath(self.build, "escape.o")
            self.assertEqual(b"protected", outside.read_bytes())

    def testHardLinkedObjectsAreNotReplayed(self):
        selected = self.build / OBJECTS[0]
        (self.build / "another.o").hardlink_to(selected)
        with self.assertRaisesRegex(ValueError, "shared hard links"):
            probe.objectPath(self.build, OBJECTS[0])

    def testTimeoutTerminatesTheWholeCompilerProcessGroup(self):
        process = mock.Mock(pid=12345)
        process.wait.side_effect = [subprocess.TimeoutExpired("compile", 60), 0]
        with (
            mock.patch.object(probe.subprocess, "Popen", return_value=process) as launch,
            mock.patch.object(probe.os, "killpg") as kill,
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                probe.runCommand(["c++", "-c", "source.cpp"], self.build, 60)
            launch.assert_called_once_with(["c++", "-c", "source.cpp"], cwd=self.build, start_new_session=True)
            kill.assert_called_once_with(12345, signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
