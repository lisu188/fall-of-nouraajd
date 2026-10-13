# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.check_build_directory import validateBuildDirectory

ROOT = Path(__file__).resolve().parents[1]


class BuildDirectoryTest(unittest.TestCase):
    def testFreshDirectoryDoesNotCreateArtifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            build_dir = Path(directory) / "build"
            validateBuildDirectory(build_dir, "Ninja", "g++-15")
            self.assertFalse(build_dir.exists())

    def testDifferentGeneratorOrCompilerPreservesCacheAndSaves(self):
        with tempfile.TemporaryDirectory() as directory:
            build_dir = Path(directory)
            compiler = build_dir / "compiler"
            cache = build_dir / "CMakeCache.txt"
            cache.write_text(
                f"CMAKE_GENERATOR:INTERNAL=Ninja\nCMAKE_CXX_COMPILER:FILEPATH={compiler}\n", encoding="utf-8"
            )
            saved_game = build_dir / "save" / "hero.json"
            saved_game.parent.mkdir()
            saved_game.write_text("unique save", encoding="utf-8")
            original_cache = cache.read_bytes()
            validateBuildDirectory(build_dir, "Ninja", str(compiler))
            for generator, selected in (("Visual Studio 17 2022", compiler), ("Ninja", build_dir / "new-compiler")):
                with self.subTest(generator=generator, compiler=selected):
                    with self.assertRaisesRegex(ValueError, "Preserving existing build directory"):
                        validateBuildDirectory(build_dir, generator, str(selected))
                    self.assertEqual(original_cache, cache.read_bytes())
                    self.assertEqual("unique save", saved_game.read_text(encoding="utf-8"))

    def testCompilerCommandResolvesBeforeComparingCachedPath(self):
        with tempfile.TemporaryDirectory() as directory:
            build_dir = Path(directory)
            compiler = build_dir / "compiler"
            (build_dir / "CMakeCache.txt").write_text(
                f"CMAKE_GENERATOR:INTERNAL=Ninja\nCMAKE_CXX_COMPILER:FILEPATH={compiler}\n", encoding="utf-8"
            )
            with mock.patch("scripts.check_build_directory.shutil.which", return_value=str(compiler)):
                validateBuildDirectory(build_dir, "Ninja", "g++-15")


class DefaultBuildConsumerTest(unittest.TestCase):
    def testRunnerDiscoversCompilerSpecificRelease(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = "cmake-build-clangcl20-release" if os.name == "nt" else "cmake-build-gcc15-release"
            (root / name).mkdir()
            (root / "cmake-build-release").mkdir()
            tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
            body = []
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == "resolveBuildDirectory":
                    body.append(node)
                elif isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id in {"build_dir", "build_dir_override"}
                    for target in node.targets
                ):
                    body.append(node)
                elif (
                    isinstance(node, ast.If)
                    and isinstance(node.test, ast.Name)
                    and node.test.id == "build_dir_override"
                ):
                    body.append(node)
            namespace = {"REPO_ROOT": root, "Path": Path, "os": os}
            with mock.patch.dict(os.environ, {"GAME_BUILD_DIR": ""}):
                exec(compile(ast.Module(body=body, type_ignores=[]), "test.py", "exec"), namespace)
            self.assertEqual(root / name, namespace["build_dir"])

    def testVideoBootstrapDiscoversCompilerSpecificRelease(self):
        from scripts import generate_walkthrough_video
        import sys

        previous_cwd = Path.cwd()
        self.addCleanup(os.chdir, previous_cwd)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = "cmake-build-clangcl20-release" if os.name == "nt" else "cmake-build-gcc15-release"
            (root / name).mkdir()
            (root / "cmake-build-release").mkdir()
            with (
                mock.patch.object(generate_walkthrough_video, "REPO_ROOT", root),
                mock.patch.object(sys, "path", sys.path.copy()),
                mock.patch.dict(os.environ, {"GAME_BUILD_DIR": "", "GAME_BUILD_CONFIG": ""}),
            ):
                try:
                    generate_walkthrough_video._bootstrap_paths()
                    self.assertEqual(root / name, Path.cwd())
                finally:
                    os.chdir(previous_cwd)


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Shell probes require POSIX Bash")
class ConfigureShellTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nouraajd-toolchain-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        (self.root / "scripts").mkdir()
        for name in ("check_build_directory.py", "run_coverage.sh"):
            shutil.copyfile(ROOT / "scripts" / name, self.root / "scripts" / name)
        shutil.copyfile(ROOT / "configure.sh", self.root / "configure.sh")
        self.makeTool("gcc-15", "exit 0\n")
        self.makeTool("g++-15", "echo 15.2.0\n")
        self.makeTool("dpkg-query", f"echo '{self.root}/pybind11Config.cmake'\n")
        self.makeTool("cmake", 'printf "%s\\n" "$@" > "$GAME_ARGUMENT_CAPTURE"\n')
        self.environment = dict(os.environ)
        for key in ("CC", "CXX", "GAME_CONFIGURE_BUILD_PREFIX", "BUILD_DIR", "GCOV_EXECUTABLE"):
            self.environment.pop(key, None)
        self.environment.update(
            PATH=str(self.bin_dir) + os.pathsep + os.environ["PATH"],
            GAME_CONFIGURE_SKIP_APT="1",
            GAME_CONFIGURE_SKIP_SUBMODULES="1",
            GAME_CONFIGURE_BUILD_TYPES="Release",
            GAME_ARGUMENT_CAPTURE=str(self.root / "arguments"),
        )

    def makeTool(self, name, body):
        path = self.bin_dir / name
        path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def testConfigureSelectsGcc15AndASeparateBuildDirectory(self):
        result = subprocess.run(
            ["bash", "configure.sh"], cwd=self.root, env=self.environment, capture_output=True, text=True, timeout=15
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        arguments = (self.root / "arguments").read_text().splitlines()
        self.assertIn("./cmake-build-gcc15-release", arguments)
        self.assertIn("-DCMAKE_C_COMPILER=gcc-15", arguments)
        self.assertIn("-DCMAKE_CXX_COMPILER=g++-15", arguments)
        self.assertFalse((self.root / "cmake-build-release").exists())

    def testCoverageRejectsGcovMismatchBeforeConfiguration(self):
        self.makeTool("gcov-15", "echo 'gcov (GCC) 14.3.0'\n")
        result = subprocess.run(
            ["bash", "scripts/run_coverage.sh"],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("matching compiler/gcov versions", result.stderr)
        self.assertFalse((self.root / "arguments").exists())
        self.assertFalse((self.root / "cmake-build-gcc15-coverage").exists())


@unittest.skipUnless(shutil.which("cmake"), "CMake is unavailable")
class PchCompilerPolicyTest(unittest.TestCase):
    def runProbe(self, *, compiler="Clang", version="20.1.8", frontend="MSVC", requested="ON", expected="OFF"):
        with tempfile.TemporaryDirectory(prefix="nouraajd-pch-policy-") as directory:
            script = Path(directory) / "probe.cmake"
            script.write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "if(POLICY CMP0126)\n"
                "  cmake_policy(SET CMP0126 NEW)\n"
                "endif()\n"
                f'set(CMAKE_CXX_COMPILER_ID "{compiler}")\n'
                f'set(CMAKE_CXX_COMPILER_VERSION "{version}")\n'
                f'set(CMAKE_CXX_COMPILER_FRONTEND_VARIANT "{frontend}")\n'
                f'set(GAME_ENABLE_PCH "{requested}" CACHE BOOL "Requested PCH" FORCE)\n'
                f'set(GAME_ENABLE_PCH "{requested}")\n'
                "set(GAME_ENABLE_UNITY_BUILD ON)\n"
                "set(CMAKE_CXX_STANDARD 26)\n"
                "set(CMAKE_CXX_STANDARD_REQUIRED ON)\n"
                "set(CMAKE_CXX_EXTENSIONS OFF)\n"
                f'include("{(ROOT / "cmake/ConfigurePch.cmake").as_posix()}")\n'
                f'if(NOT GAME_ENABLE_PCH STREQUAL "{expected}")\n'
                '  message(FATAL_ERROR "Effective PCH policy differs: ${GAME_ENABLE_PCH}")\n'
                "endif()\n"
                "get_property(cached CACHE GAME_ENABLE_PCH PROPERTY VALUE)\n"
                f'if(NOT cached STREQUAL "{expected}")\n'
                '  message(FATAL_ERROR "Cached PCH policy differs: ${cached}")\n'
                "endif()\n"
                'if(NOT GAME_ENABLE_UNITY_BUILD OR NOT CMAKE_CXX_STANDARD STREQUAL "26"\n'
                "    OR NOT CMAKE_CXX_STANDARD_REQUIRED OR CMAKE_CXX_EXTENSIONS)\n"
                '  message(FATAL_ERROR "PCH policy changed Unity or the required C++26 mode")\n'
                "endif()\n",
                encoding="utf-8",
            )
            return subprocess.run(["cmake", "-P", str(script)], capture_output=True, text=True, timeout=15)

    def testClang20DisablesRequestedPchForBothFrontends(self):
        for frontend in ("MSVC", "GNU"):
            for version in ("20.0.0", "20.1.8", "20.9.0"):
                with self.subTest(frontend=frontend, version=version):
                    result = self.runProbe(frontend=frontend, version=version)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertIn("Disabling GAME_ENABLE_PCH", result.stdout)
                    self.assertIn("LLVM #172464 and #205965", result.stdout)

    def testGcc15PreservesRequestedPch(self):
        result = self.runProbe(compiler="GNU", version="15.2.0", frontend="GNU", expected="ON")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("Disabling GAME_ENABLE_PCH", result.stdout)

    def testExplicitOffRemainsOff(self):
        result = self.runProbe(requested="OFF")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("Disabling GAME_ENABLE_PCH", result.stdout)

    def testOtherClangVersionsAreOutsideThisPolicy(self):
        for version in ("19.1.7", "21.1.0"):
            with self.subTest(version=version):
                result = self.runProbe(version=version, expected="ON")
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def testPolicyRunsAfterTheRootOptionAndWindowsFastBuildKeepsUnity(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        policy = "include(cmake/ConfigurePch.cmake)"
        self.assertGreater(cmake.index(policy), cmake.index("option(GAME_ENABLE_PCH "))
        self.assertLess(cmake.index(policy), cmake.index("if (GAME_ENABLE_PCH)"))
        configure = (ROOT / "configure.bat").read_text(encoding="utf-8")
        self.assertIn("-DGAME_ENABLE_UNITY_BUILD=ON -DGAME_ENABLE_PCH=ON -DGAME_UNITY_BATCH_SIZE=16", configure)


@unittest.skipUnless(shutil.which("cmake"), "CMake is unavailable")
class Cxx26ConfigureRejectionTest(unittest.TestCase):
    def runProbe(
        self, *, windows=False, compiler="GNU", version="15.2.0", frontend="GNU", features="cxx_std_26", missing=""
    ):
        with tempfile.TemporaryDirectory(prefix="nouraajd-cxx26-") as directory:
            root = Path(directory)
            # Isolate configure policy tests from compiler and third-party dependency installation.
            (root / "CheckCXXSourceCompiles.cmake").write_text(
                "macro(check_cxx_source_compiles source variable)\n"
                '  if("${variable}" STREQUAL "GAME_HAS_${missing}")\n'
                "    set(${variable} FALSE)\n"
                "  else()\n"
                "    set(${variable} TRUE)\n"
                "  endif()\n"
                "endmacro()\n",
                encoding="utf-8",
            )
            script = root / "probe.cmake"
            script.write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                f'set(CMAKE_MODULE_PATH "{root.as_posix()}")\n'
                f"set(WIN32 {'TRUE' if windows else 'FALSE'})\n"
                f'set(CMAKE_CXX_COMPILER_ID "{compiler}")\n'
                f'set(CMAKE_CXX_COMPILER_VERSION "{version}")\n'
                f'set(CMAKE_CXX_COMPILER_FRONTEND_VARIANT "{frontend}")\n'
                f'set(CMAKE_CXX_COMPILE_FEATURES "{features}")\n'
                f'set(missing "{missing}")\n'
                f'include("{(ROOT / "cmake/RequireCxx26.cmake").as_posix()}")\n',
                encoding="utf-8",
            )
            return subprocess.run(["cmake", "-P", str(script)], capture_output=True, text=True, timeout=15)

    def testRejectsMissingCxx26WithoutFallback(self):
        result = self.runProbe(features="cxx_std_23")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("C++26 is required without fallback", result.stderr)

    def testRejectsOlderGccAndNonClangWindowsToolchains(self):
        cases = (
            ({"version": "14.3.0"}, "GCC 15 or newer"),
            ({"windows": True, "compiler": "MSVC", "version": "19.44", "frontend": "MSVC"}, "clang-cl"),
            ({"windows": True, "compiler": "Clang", "version": "19.1.7", "frontend": "MSVC"}, "clang-cl"),
            ({"windows": True, "compiler": "Clang", "version": "20.1.8", "frontend": "GNU"}, "clang-cl"),
        )
        for arguments, diagnostic in cases:
            with self.subTest(arguments=arguments):
                result = self.runProbe(**arguments)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(diagnostic, result.stderr)

    def testMissingSyntaxOrLibraryFeatureFailsConfiguration(self):
        for missing in ("PACK_INDEXING", "DELETED_FUNCTION_REASON", "COROUTINES", "EXPECTED", "MOVE_ONLY_FUNCTION"):
            with self.subTest(missing=missing):
                result = self.runProbe(missing=missing)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(missing, result.stderr)

    def testSelectedDesktopToolchainsPassPolicy(self):
        for arguments in ({}, {"windows": True, "compiler": "Clang", "version": "20.1.8", "frontend": "MSVC"}):
            with self.subTest(arguments=arguments):
                result = self.runProbe(**arguments)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
