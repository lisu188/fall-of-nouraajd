# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import build_metrics

ROOT = Path(__file__).resolve().parents[1]


class BuildMetricsTest(unittest.TestCase):
    def testEffectiveBuildPolicyOverridesShadowedCacheWithoutExposingUnrelatedValues(self):
        with tempfile.TemporaryDirectory() as directory:
            build_dir = Path(directory)
            (build_dir / "CMakeCache.txt").write_text("CMAKE_CXX_SCAN_FOR_MODULES:BOOL=ON\n", encoding="utf-8")
            (build_dir / "game-build-policy.json").write_text(
                json.dumps({"CMAKE_CXX_SCAN_FOR_MODULES": "OFF", "SERVICE_TOKEN": "private-value"}), encoding="utf-8"
            )
            self.assertEqual({"CMAKE_CXX_SCAN_FOR_MODULES": "OFF"}, build_metrics.readConfiguration(build_dir))

    def testNinjaRecordsOnlyNewEdgesAndCountsMultipleOutputsOnce(self):
        previous = b"# ninja log v5\n0\t90\t1\told.o\told\n"
        current = previous + b"0\t25\t2\tnew.o\ta\n25\t30\t2\tgame.dll\tb\n25\t30\t2\tgame.lib\tb\n"
        report = build_metrics.summarizeNinjaLog(previous, current)
        self.assertEqual(2, report["edge_count"])
        self.assertEqual(30, report["summed_edge_milliseconds"])
        self.assertEqual("new.o", report["longest_edges"][0]["output"])
        self.assertFalse(report["log_rewritten"])
        self.assertTrue(build_metrics.summarizeNinjaLog(previous, current[-24:])["log_rewritten"])

    def testToolchainIdentityChangesWhenWrappedFrontendChanges(self):
        with tempfile.TemporaryDirectory() as directory:
            compiler = Path(directory) / "compiler"
            frontend = Path(directory) / "cc1plus"
            compiler.write_bytes(b"unchanged wrapper")
            frontend.write_bytes(b"first compiler")
            with (
                mock.patch.dict(os.environ, {"GAME_REAL_CXX_COMPILER": ""}),
                mock.patch.object(build_metrics.subprocess, "run", return_value=SimpleNamespace(stdout=str(frontend))),
                mock.patch.object(build_metrics.subprocess, "check_output", side_effect=["linux", "15.2"] * 2),
            ):
                first = build_metrics.compilerIdentity(str(compiler))
                frontend.write_bytes(b"different compiler, same version")
                second = build_metrics.compilerIdentity(str(compiler))
            self.assertNotEqual(first, second)

    def testReportPreservesFailedBuildAndOmitsUnrelatedCacheValues(self):
        with tempfile.TemporaryDirectory() as directory:
            build_dir = Path(directory)
            (build_dir / "CMakeCache.txt").write_text(
                "CMAKE_BUILD_TYPE:STRING=Release\nSERVICE_TOKEN:STRING=private-value\n", encoding="utf-8"
            )
            output = build_dir / "report.json"
            arguments = argparse.Namespace(
                build_dir=directory, phase="compile", cache_tool="ccache", command=["compile"], output=str(output)
            )

            def failingBuild(command):
                (build_dir / ".ninja_log").write_text("# ninja log v5\n0\t42\t1\tnew.o\tab\n", encoding="utf-8")
                return 7

            with (
                mock.patch.object(build_metrics.subprocess, "call", side_effect=failingBuild),
                mock.patch.object(build_metrics.time, "monotonic", side_effect=[10.0, 11.5]),
                mock.patch.object(
                    build_metrics,
                    "cacheStatistics",
                    side_effect=[{"counters": {"cache_miss": 3}}, {"counters": {"cache_miss": 5}}],
                ),
            ):
                self.assertEqual(7, build_metrics.runBuild(arguments))
            report = json.loads(output.read_text())
            self.assertEqual(7, report["exit_code"])
            self.assertEqual(1.5, report["wall_seconds"])
            self.assertEqual(1, report["ninja"]["edge_count"])
            self.assertEqual(2, report["cache"]["counter_delta"]["cache_miss"])
            self.assertNotIn("private-value", output.read_text())

    def testUnavailableStatisticsCannotPreventTheBuild(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments = argparse.Namespace(
                build_dir=directory,
                phase="compile",
                cache_tool="ccache",
                command=["compile"],
                output=str(Path(directory) / "report.json"),
            )
            with (
                mock.patch.object(build_metrics.subprocess, "call", return_value=0) as build,
                mock.patch.object(build_metrics, "cacheStatistics", side_effect=OSError("missing cache tool")),
            ):
                self.assertEqual(0, build_metrics.runBuild(arguments))
                build.assert_called_once_with(["compile"])
            self.assertIn("diagnostic_error", json.loads(Path(arguments.output).read_text())["cache"])

    def testCliReturnsChildFailureAndWritesItsReport(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_metrics.py"),
                    "run",
                    "--build-dir",
                    directory,
                    "--output",
                    str(output),
                    "--",
                    sys.executable,
                    "-c",
                    "raise SystemExit(3)",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(3, result.returncode, result.stdout + result.stderr)
            self.assertEqual(3, json.loads(output.read_text())["exit_code"])


@unittest.skipUnless(shutil.which("cmake") and os.name == "posix", "CMake and POSIX compiler paths required")
class CompilerCachePolicyTest(unittest.TestCase):
    def launcher(self, directory, custom=None):
        root = Path(directory)
        frontend = root / "cc1plus"
        frontend.write_text("compiler backend", encoding="utf-8")
        compiler = root / "compiler"
        compiler.write_text(f"#!/bin/sh\nprintf '%s\\n' '{frontend}'\n", encoding="utf-8")
        compiler.chmod(0o755)
        output = root / "launcher.txt"
        custom_setting = "" if custom is None else f'set(CMAKE_CXX_COMPILER_LAUNCHER "{custom}")\n'
        script = root / "probe.cmake"
        script.write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            f'set(CMAKE_SOURCE_DIR "{root}")\n'
            'set(CMAKE_CXX_COMPILER_ID "GNU")\n'
            f'set(CMAKE_C_COMPILER "{compiler}")\n'
            f'set(CMAKE_CXX_COMPILER "{compiler}")\n'
            f'set(GAME_CCACHE_EXECUTABLE "{root}/ccache")\n'
            + custom_setting
            + f'include("{ROOT}/cmake/ConfigureCompilerCache.cmake")\n'
            + f'file(WRITE "{output}" "${{CMAKE_CXX_COMPILER_LAUNCHER}}")\n',
            encoding="utf-8",
        )
        result = subprocess.run(["cmake", "-P", str(script)], capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return output.read_text().split(";")

    def testCacheIsBoundedProjectScopedAndKeepsHeaderTimestampSafeguards(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = self.launcher(directory)
            self.assertIn(f"CCACHE_DIR={directory}/.cache/ccache", launcher)
            self.assertIn("CCACHE_MAXSIZE=1G", launcher)
            self.assertIn("CCACHE_COMPILERCHECK=content", launcher)
            self.assertIn("CCACHE_SLOPPINESS=pch_defines,time_macros", launcher)
            self.assertIn(f"CCACHE_EXTRAFILES={directory}/cc1plus", launcher)
            self.assertNotIn("include_file_mtime", " ".join(launcher))
            self.assertNotIn("include_file_ctime", " ".join(launcher))
            self.assertFalse((Path(directory) / ".cache").exists())

    def testExplicitDisabledOrCustomLauncherIsPreserved(self):
        for custom in ("", "custom-cache"):
            with self.subTest(custom=custom), tempfile.TemporaryDirectory() as directory:
                self.assertEqual([custom], self.launcher(directory, custom))


@unittest.skipUnless(
    os.name == "posix" and all(shutil.which(tool) for tool in ("cmake", "ninja", "ccache")),
    "Native cache probes require POSIX, CMake, Ninja, and ccache",
)
class NativeCompilerCacheTest(unittest.TestCase):
    def runProbe(self, coverage=False):
        compiler = next(
            (
                selected
                for candidate in (os.environ.get("CXX", ""), "g++-15", "g++")
                if candidate and (selected := shutil.which(candidate))
            ),
            None,
        )
        if not compiler:
            self.skipTest("A GNU C++ compiler is unavailable")
        macros = subprocess.run(
            [compiler, "-dM", "-E", "-x", "c++", "-"],
            input="",
            capture_output=True,
            text=True,
            timeout=15,
        )
        if macros.returncode or "__GNUC__" not in macros.stdout or "__clang__" in macros.stdout:
            self.skipTest("The selected C++ compiler is not GNU")
        with tempfile.TemporaryDirectory(prefix="nouraajd-native-cache-") as directory:
            root = Path(directory)
            build_dir = root / "build"
            cache_dir = root / "cache"
            environment = {key: value for key, value in os.environ.items() if not key.startswith("CCACHE_")}
            environment["CCACHE_DIR"] = str(cache_dir)
            environment["CCACHE_CONFIGPATH"] = str(root / "ccache.conf")
            environment["GAME_REAL_CXX_COMPILER"] = ""
            (root / "ccache.conf").write_text("", encoding="utf-8")
            header = root / "pch.h"
            source = root / "main.cpp"
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(cache_probe LANGUAGES CXX)\n"
                f'include("{ROOT}/cmake/ConfigureBuildPolicy.cmake")\n'
                f'include("{ROOT}/cmake/ConfigureCompilerCache.cmake")\n'
                "set(CMAKE_CXX_STANDARD 17)\n"
                'set(PROBE_COMMAND_VALUE "1" CACHE STRING "Probe definition")\n'
                "add_executable(cache_probe main.cpp)\n"
                "target_precompile_headers(cache_probe PRIVATE pch.h)\n"
                "target_compile_options(cache_probe PRIVATE -O0 -g0)\n"
                "target_compile_definitions(cache_probe PRIVATE COMMAND_VALUE=${PROBE_COMMAND_VALUE})\n"
                + (
                    "target_compile_options(cache_probe PRIVATE --coverage)\n"
                    "target_link_options(cache_probe PRIVATE --coverage)\n"
                    if coverage
                    else ""
                ),
                encoding="utf-8",
            )
            peak_bytes = 0

            def measureSize():
                nonlocal peak_bytes
                peak_bytes = max(peak_bytes, sum(path.stat().st_size for path in root.rglob("*") if path.is_file()))

            def run(*command):
                result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=45)
                measureSize()
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                return result.stdout

            def writeInput(path, contents):
                path.write_text(contents, encoding="utf-8")

            def writeSource(value):
                writeInput(
                    source,
                    '#include "pch.h"\n'
                    'extern "C" int printf(const char*, ...);\n'
                    f'int main() {{ return printf("%d\\n", HEADER_VALUE + COMMAND_VALUE + {value}) < 0; }}\n',
                )

            def counters():
                return {
                    fields[0]: int(fields[1])
                    for line in run("ccache", "--print-stats").splitlines()
                    if len(fields := line.split()) == 2 and fields[1].isdigit()
                }

            def hitCount(values):
                return values.get("direct_cache_hit", 0) + values.get("preprocessed_cache_hit", 0)

            def build():
                run("cmake", "--build", str(build_dir), "--target", "cache_probe", "--parallel", "2")

            def agePch():
                run("cmake", "--build", str(build_dir), "--target", "CMakeFiles/cache_probe.dir/cmake_pch.hxx.gch")
                time.sleep(1.05)

            def output():
                return run(str(build_dir / "cache_probe")).strip()

            writeInput(header, "#pragma once\n#define HEADER_VALUE 2\n")
            writeSource(1)
            configure = [
                "cmake",
                "-S",
                str(root),
                "-B",
                str(build_dir),
                "-G",
                "Ninja",
                f"-DCMAKE_CXX_COMPILER={compiler}",
                f"-DGAME_CCACHE_DIR={cache_dir}",
            ]
            run(*configure)
            build()
            self.assertEqual("4", output())
            agePch()
            run("ccache", "--clear")
            object_file = build_dir / "CMakeFiles/cache_probe.dir/main.cpp.o"
            object_file.unlink()
            before = counters()
            build()
            populated = counters()
            self.assertGreater(populated.get("cache_miss", 0), before.get("cache_miss", 0))
            object_file.unlink()
            build()
            warm = counters()
            self.assertGreater(hitCount(warm), hitCount(populated))
            self.assertEqual("4", output())

            writeSource(2)
            time.sleep(1.05)
            build()
            changed_source = counters()
            self.assertGreater(changed_source.get("cache_miss", 0), warm.get("cache_miss", 0))
            self.assertEqual("5", output())

            writeInput(header, "#pragma once\n#define HEADER_VALUE 3\n")
            agePch()
            build()
            changed_header = counters()
            self.assertGreater(changed_header.get("cache_miss", 0), changed_source.get("cache_miss", 0))
            self.assertEqual("6", output())

            run(*configure, "-DPROBE_COMMAND_VALUE=2")
            agePch()
            build()
            changed_command = counters()
            self.assertGreater(changed_command.get("cache_miss", 0), changed_header.get("cache_miss", 0))
            self.assertEqual("7", output())
            print(
                f"Native ccache PCH probe coverage={coverage}: identical rebuild hit; source/header/definition misses; "
                f"outputs 4,5,6,7; peak reproducible fixture {peak_bytes} bytes (removed)",
                flush=True,
            )

    def testPchCacheHitsAndInvalidatesForSourceHeaderAndCommand(self):
        self.runProbe()

    def testInstrumentedPchCacheHitsAndInvalidatesForSourceHeaderAndCommand(self):
        self.runProbe(coverage=True)


if __name__ == "__main__":
    unittest.main()
