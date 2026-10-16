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


class DesktopReleaseToolchainTest(unittest.TestCase):
    def desktopJob(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        return workflow.split("\n  android:", 1)[0]

    def testTaggedDesktopReleaseProvisionsTheMandatoryPinnedToolchain(self):
        desktop = self.desktopJob()
        for setting in (
            "runs-on: ubuntu-26.04",
            "CC: gcc-15",
            "CXX: g++-15",
            "GAME_CONFIGURE_BUILD_PREFIX: cmake-build-gcc15",
            "GAME_BUILD_DIR: cmake-build-gcc15-release",
            "GAME_BUILD_CONFIG: Release",
            "python3 -m pip install --upgrade cmake==4.3.1",
            "sudo apt-get install -y build-essential gcc-15 g++-15 ninja-build",
        ):
            with self.subTest(setting=setting):
                self.assertTrue(setting in desktop, "Missing desktop release setting: " + setting)
        self.assertTrue("cmake==4.3.1" in desktop, "Desktop release must provision the pinned CMake before configure")
        self.assertLess(
            desktop.index("cmake==4.3.1"), desktop.index("GAME_CONFIGURE_BUILD_TYPES=Release ./configure.sh")
        )
        self.assertNotIn("build-essential cmake ", desktop)
        self.assertNotIn("CMAKE_CXX_STANDARD=23", desktop)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("set(CMAKE_CXX_STANDARD 26)", cmake)
        self.assertIn("set(CMAKE_CXX_STANDARD_REQUIRED ON)", cmake)
        self.assertIn("set(CMAKE_CXX_EXTENSIONS OFF)", cmake)

    def testTaggedDesktopReleaseBuildsValidatesAndPackagesTheConfiguredTree(self):
        desktop = self.desktopJob()
        for command in (
            'cmake --build cmake-build-gcc15-release --target _game for_unit_tests performance_guard_tests -j"$(nproc)"',
            "ctest --test-dir cmake-build-gcc15-release --output-on-failure -R for_unit_tests",
            "ctest --test-dir cmake-build-gcc15-release --output-on-failure --verbose -L performance",
            'python3 test.py --suite full --jobs "$(nproc)"',
            'cmake --build cmake-build-gcc15-release --target package -j"$(nproc)"',
            "files: cmake-build-gcc15-release/fall-of-nouraajd-*.tar.gz",
        ):
            with self.subTest(command=command):
                self.assertTrue(command in desktop, "Missing desktop release command: " + command)
        self.assertNotIn("cmake-build-release", desktop)

    def testReleaseCacheMetadataUsesTheSelectedCompilerWithoutBroadFallback(self):
        desktop = self.desktopJob()
        self.assertIn('compiler_id="$("${CXX}" -dumpmachine)-$("${CXX}" -dumpfullversion -dumpversion)"', desktop)
        self.assertIn("-ccache-cxx26-release-package-${compiler_id}-", desktop)
        restore = desktop.split("      - name: Restore ccache", 1)[1].split("      - name:", 1)[0]
        keys = restore.split("restore-keys:", 1)[1].strip().splitlines()
        self.assertEqual(["${{ steps.ccache.outputs.prefix }}"], [line.strip() for line in keys if line.strip() != "|"])


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


@unittest.skipUnless(shutil.which("cmake") and shutil.which("ninja"), "CMake and Ninja are required")
class ProfileCompilePoolPolicyTest(unittest.TestCase):
    def runProbe(
        self,
        *,
        generator="Ninja",
        build_type="RelWithDebInfo",
        system="Linux",
        global_pools=None,
        fallback_pools="",
        inherited_pool=None,
        explicit_pool=None,
    ):
        with tempfile.TemporaryDirectory(prefix="nouraajd-profile-pool-") as directory:
            root = Path(directory)
            (root / "dummy.h").write_text(
                "// Header-only configure fixture; no compiler is enabled.\n", encoding="utf-8"
            )
            settings = [
                "cmake_minimum_required(VERSION 3.20)",
                "project(profile_pool_policy LANGUAGES NONE)",
                f'set(CMAKE_BUILD_TYPE "{build_type}")',
                f'set(CMAKE_SYSTEM_NAME "{system}")',
                f"set(WIN32 {'TRUE' if system == 'Windows' else 'FALSE'})",
                f'set(CMAKE_JOB_POOLS "{fallback_pools}")',
            ]
            if global_pools is not None:
                settings.append(f'set_property(GLOBAL PROPERTY JOB_POOLS "{global_pools}")')
            if inherited_pool is not None:
                settings.append(f'set(CMAKE_JOB_POOL_COMPILE "{inherited_pool}")')
            settings.extend(
                [
                    f'include("{(ROOT / "cmake/ConfigureCompilePool.cmake").as_posix()}")',
                    "foreach(target IN ITEMS first second vendor)",
                    "  add_library(${target} OBJECT dummy.h)",
                    "  set_target_properties(${target} PROPERTIES LINKER_LANGUAGE CXX CXX_STANDARD 26",
                    '    CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF COMPILE_OPTIONS "-O2;-g")',
                    "endforeach()",
                ]
            )
            if explicit_pool is not None:
                settings.append(f'set_property(TARGET first PROPERTY JOB_POOL_COMPILE "{explicit_pool}")')
            settings.extend(
                [
                    "configure_profile_compile_pool(first)",
                    "configure_profile_compile_pool(second)",
                    "configure_profile_compile_pool(first)",
                    "get_property(pools GLOBAL PROPERTY JOB_POOLS)",
                    'file(WRITE "${CMAKE_BINARY_DIR}/policy.txt" "pools=${pools}\\n")',
                    "foreach(target IN ITEMS first second vendor)",
                    "  foreach(property IN ITEMS JOB_POOL_COMPILE COMPILE_OPTIONS CXX_STANDARD",
                    "      CXX_STANDARD_REQUIRED CXX_EXTENSIONS)",
                    "    get_property(value TARGET ${target} PROPERTY ${property})",
                    '    file(APPEND "${CMAKE_BINARY_DIR}/policy.txt" "${target}.${property}=${value}\\n")',
                    "  endforeach()",
                    "endforeach()",
                ]
            )
            (root / "CMakeLists.txt").write_text("\n".join(settings) + "\n", encoding="utf-8")
            result = subprocess.run(
                ["cmake", "-S", str(root), "-B", str(root / "build"), "-G", generator],
                capture_output=True,
                text=True,
                timeout=15,
            )
            report = root / "build/policy.txt"
            values = dict(line.split("=", 1) for line in report.read_text().splitlines()) if report.is_file() else {}
            rules = root / "build/CMakeFiles/rules.ninja"
            ninja = rules.read_text() if rules.is_file() else ""
            if result.returncode == 0:
                for target in ("first", "second", "vendor"):
                    self.assertEqual("-O2;-g", values[f"{target}.COMPILE_OPTIONS"])
                    self.assertEqual("26", values[f"{target}.CXX_STANDARD"])
                    self.assertEqual("ON", values[f"{target}.CXX_STANDARD_REQUIRED"])
                    self.assertEqual("OFF", values[f"{target}.CXX_EXTENSIONS"])
                self.assertNotIn("CXX compiler identification", result.stdout)
                self.assertFalse(list((root / "build").rglob("*.obj")))
                self.assertFalse(list((root / "build").rglob("*.o")))
            return result, values, ninja

    def successfulProbe(self, **arguments):
        result, values, ninja = self.runProbe(**arguments)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return values, ninja

    def testDesktopProfileUsesOneSharedDepthTwoPoolWithoutChangingFlagsOrVendors(self):
        for system in ("Linux", "Windows"):
            with self.subTest(system=system):
                values, ninja = self.successfulProbe(system=system)
                self.assertEqual("nouraajd_profile_compile=2", values["pools"])
                self.assertEqual("nouraajd_profile_compile", values["first.JOB_POOL_COMPILE"])
                self.assertEqual("nouraajd_profile_compile", values["second.JOB_POOL_COMPILE"])
                self.assertEqual("", values["vendor.JOB_POOL_COMPILE"])
                self.assertEqual(1, ninja.count("pool nouraajd_profile_compile\n"))
                self.assertIn("pool nouraajd_profile_compile\n  depth = 2", ninja)

    def testOtherConfigurationsPlatformsAndMultiConfigStayUnchanged(self):
        cases = (
            {"build_type": "Debug"},
            {"build_type": "Release"},
            {"system": "Android"},
            {"system": "Darwin"},
            {"generator": "Ninja Multi-Config"},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                values, ninja = self.successfulProbe(**arguments)
                self.assertEqual("", values["pools"])
                self.assertEqual("", values["first.JOB_POOL_COMPILE"])
                self.assertEqual("", values["second.JOB_POOL_COMPILE"])
                self.assertNotIn("pool nouraajd_profile_compile", ninja)

    def testVariableFallbackAndGlobalPoolsRetainTheirPrecedence(self):
        values, ninja = self.successfulProbe(fallback_pools="custom_compile=3;custom_link=1")
        self.assertEqual("custom_compile=3;custom_link=1;nouraajd_profile_compile=2", values["pools"])
        self.assertIn("pool custom_compile\n  depth = 3", ninja)
        self.assertIn("pool custom_link\n  depth = 1", ninja)
        values, ninja = self.successfulProbe(global_pools="custom=4", fallback_pools="ignored=9")
        self.assertEqual("custom=4;nouraajd_profile_compile=2", values["pools"])
        self.assertNotIn("pool ignored", ninja)
        values, _ninja = self.successfulProbe(global_pools="", fallback_pools="ignored=9")
        self.assertEqual("nouraajd_profile_compile=2", values["pools"])

    def testExplicitAndInheritedTargetAssignmentsArePreserved(self):
        for assigned in ("custom", ""):
            with self.subTest(assigned=assigned):
                values, _ninja = self.successfulProbe(global_pools="custom=1", explicit_pool=assigned)
                self.assertEqual(assigned, values["first.JOB_POOL_COMPILE"])
                self.assertEqual("nouraajd_profile_compile", values["second.JOB_POOL_COMPILE"])
        values, ninja = self.successfulProbe(global_pools="custom=1", inherited_pool="custom")
        self.assertEqual("custom=1", values["pools"])
        for target in ("first", "second", "vendor"):
            self.assertEqual("custom", values[f"{target}.JOB_POOL_COMPILE"])
        self.assertNotIn("pool nouraajd_profile_compile", ninja)

    def testConflictingReservedPoolFailsAtConfigureWithoutReplacingIt(self):
        result, _values, _ninja = self.runProbe(global_pools="custom=1;nouraajd_profile_compile=4")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("nouraajd_profile_compile pool is reserved with depth 2", result.stderr)

    def testPolicyIsAppliedOnlyThroughTheOwnedTargetHelper(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("include(cmake/ConfigureCompilePool.cmake)", cmake)
        helper = cmake.split("function(configure_cpp_target target_name)", 1)[1].split("endfunction()", 1)[0]
        self.assertIn("configure_profile_compile_pool(${target_name})", helper)
        self.assertNotIn("CMAKE_JOB_POOL_COMPILE", cmake)


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
