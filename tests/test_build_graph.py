# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_CONFIG_KEYS = {
    "CMAKE_C_COMPILER",
    "CMAKE_CXX_COMPILER",
    "CMAKE_TOOLCHAIN_FILE",
    "VCPKG_INSTALLED_DIR",
    "VCPKG_TARGET_TRIPLET",
    "VCPKG_HOST_TRIPLET",
    "VCPKG_OVERLAY_TRIPLETS",
    "VCPKG_CHAINLOAD_TOOLCHAIN_FILE",
    "Python3_EXECUTABLE",
    "Python3_INCLUDE_DIR",
    "Python3_LIBRARY",
    "_Python3_INCLUDE_DIR",
    "_Python3_LIBRARY_RELEASE",
    "_Python3_LIBRARY_DEBUG",
    "pybind11_DIR",
    "SDL2_DIR",
    "SDL2_image_DIR",
    "SDL2_ttf_DIR",
}


def productionConfiguration(root=ROOT, environment=None, windows=None):
    environment = os.environ if environment is None else environment
    windows = os.name == "nt" if windows is None else windows
    default = "cmake-build-clangcl20-release" if windows else "cmake-build-gcc15-release"
    directory = Path(environment.get("GAME_BUILD_DIR") or default)
    cache = (directory if directory.is_absolute() else root / directory) / "CMakeCache.txt"
    values = {}
    if cache.is_file():
        for line in cache.read_text(encoding="utf-8").splitlines():
            match = re.match(r"([^:#]+):[^=]*=(.*)", line)
            if match and match[1] in PRODUCTION_CONFIG_KEYS and not match[2].endswith("-NOTFOUND"):
                values[match[1]] = match[2]
    values.setdefault("Python3_EXECUTABLE", sys.executable)
    if windows or any(key.startswith("VCPKG_") for key in values):
        values["VCPKG_MANIFEST_MODE"] = "OFF"
    return values


class ProductionGraphConfigurationTest(unittest.TestCase):
    def testWindowsCachePathsAndPythonSdkAreForwardedWithoutPrivateOrInstallSettings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / "cmake-build-clangcl20-release"
            build.mkdir()
            settings = {
                "CMAKE_TOOLCHAIN_FILE": r"C:\Program Files\vcpkg\scripts\buildsystems\vcpkg.cmake",
                "VCPKG_INSTALLED_DIR": r"D:\game\vcpkg_installed\fast",
                "VCPKG_TARGET_TRIPLET": "x64-windows-release",
                "VCPKG_OVERLAY_TRIPLETS": r"D:\game\cmake\triplets",
                "Python3_EXECUTABLE": r"C:\Python312\python.exe",
                "Python3_INCLUDE_DIR": r"C:\Python312\include",
                "_Python3_LIBRARY_RELEASE": r"C:\Python312\libs\python312.lib",
                "pybind11_DIR": r"D:\game\vcpkg_installed\fast\x64-windows-release\share\pybind11",
                "VCPKG_MANIFEST_MODE": "ON",
                "SERVICE_TOKEN": "private-value",
                "SDL2_ttf_DIR": "SDL2_ttf_DIR-NOTFOUND",
            }
            cache = build / "CMakeCache.txt"
            cache.write_text("".join(f"{key}:STRING={value}\n" for key, value in settings.items()), encoding="utf-8")
            original = cache.read_bytes()
            values = productionConfiguration(root, {}, windows=True)
            for key in PRODUCTION_CONFIG_KEYS.intersection(settings) - {"SDL2_ttf_DIR"}:
                self.assertEqual(settings[key], values[key])
            self.assertEqual("OFF", values["VCPKG_MANIFEST_MODE"])
            self.assertNotIn("SERVICE_TOKEN", values)
            self.assertNotIn("SDL2_ttf_DIR", values)
            self.assertEqual(original, cache.read_bytes())

    def testExplicitBuildDirectoryAndCurrentPythonFallbackDoNotCreateArtifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / "selected"
            values = productionConfiguration(root, {"GAME_BUILD_DIR": str(selected)}, windows=False)
            self.assertEqual({"Python3_EXECUTABLE": sys.executable}, values)
            self.assertFalse(selected.exists())
            selected.mkdir()
            (selected / "CMakeCache.txt").write_text("CMAKE_CXX_COMPILER:FILEPATH=/tools/g++-15\n", encoding="utf-8")
            self.assertEqual(
                "/tools/g++-15", productionConfiguration(root, {"GAME_BUILD_DIR": "selected"})["CMAKE_CXX_COMPILER"]
            )


def runConfigure(source_dir, build_dir, *arguments):
    return subprocess.run(
        ["cmake", "-S", str(source_dir), "-B", str(build_dir), "-G", "Ninja", *arguments],
        capture_output=True,
        text=True,
        timeout=60,
    )


@unittest.skipUnless(shutil.which("cmake") and shutil.which("ninja"), "CMake and Ninja are required")
class HeaderBuildPolicyTest(unittest.TestCase):
    def testHeaderSourcesKeepUnityAndNeverRequestModuleScanning(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-header-graph-") as directory:
            root = Path(directory)
            for name in ("first", "second"):
                (root / f"{name}.cpp").write_text(f"int {name}() {{ return 1; }}\n", encoding="utf-8")
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.28)\n"
                "project(header_graph LANGUAGES CXX)\n"
                "set(CMAKE_CXX_STANDARD 20)\n"
                "set(CMAKE_CXX_STANDARD_REQUIRED ON)\n"
                "set(CMAKE_CXX_EXTENSIONS OFF)\n"
                f'include("{(ROOT / "cmake/ConfigureBuildPolicy.cmake").as_posix()}")\n'
                "add_library(probe OBJECT first.cpp second.cpp)\n"
                "set_target_properties(probe PROPERTIES UNITY_BUILD ON UNITY_BUILD_BATCH_SIZE 2)\n",
                encoding="utf-8",
            )
            build = root / "build"
            result = runConfigure(root, build, "-DCMAKE_CXX_SCAN_FOR_MODULES=ON", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            commands = json.loads((build / "compile_commands.json").read_text(encoding="utf-8"))
            self.assertEqual(1, len(commands), "Both header-based sources must compile in one unity object")
            unity = Path(commands[0]["file"])
            self.assertIn("Unity", unity.parts)
            self.assertIn("first.cpp", unity.read_text(encoding="utf-8"))
            self.assertIn("second.cpp", unity.read_text(encoding="utf-8"))
            graph = (build / "build.ninja").read_text(encoding="utf-8")
            self.assertNotIn(": CXX_SCAN__", graph)
            self.assertNotIn(": CXX_DYNDEP__", graph)
            for option in ("-fmodules-ts", "-fmodule-mapper", "/scanDependencies"):
                self.assertNotIn(option, commands[0]["command"])


@unittest.skipUnless(shutil.which("cmake") and shutil.which("ninja"), "CMake and Ninja are required")
class TestPchCohortTest(unittest.TestCase):
    def testOnlyIdenticalCompileEnvironmentsReuseTheSharedPch(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-pch-cohort-") as directory:
            root = Path(directory)
            (root / "empty.cpp").write_text("int probe;\n", encoding="utf-8")
            (root / "pch.h").write_text("#include <vector>\n", encoding="utf-8")
            (root / "extra").mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(pch_cohort LANGUAGES CXX)\n"
                "set(CMAKE_CXX_STANDARD 20)\n"
                "set(CMAKE_CXX_SCAN_FOR_MODULES OFF)\n"
                f'include("{(ROOT / "cmake/ConfigureTestPch.cmake").as_posix()}")\n'
                "add_library(extra INTERFACE)\n"
                "foreach(target IN ITEMS seed identical options definitions includes links pic visibility standard)\n"
                "  add_library(${target} OBJECT empty.cpp)\n"
                "  target_compile_definitions(${target} PRIVATE SHARED_DEFINITION=1)\n"
                "endforeach()\n"
                "target_precompile_headers(seed PRIVATE pch.h)\n"
                "target_compile_options(options PRIVATE -DEXTRA_OPTION=1)\n"
                "target_compile_definitions(definitions PRIVATE DIFFERENT_RESOURCE_ROOT=1)\n"
                "target_include_directories(includes PRIVATE extra)\n"
                "target_link_libraries(links PRIVATE extra)\n"
                "set_target_properties(pic PROPERTIES POSITION_INDEPENDENT_CODE ON)\n"
                "set_target_properties(visibility PROPERTIES CXX_VISIBILITY_PRESET hidden)\n"
                "set_target_properties(standard PROPERTIES CXX_STANDARD 17)\n"
                "foreach(target IN ITEMS identical options definitions includes links pic visibility standard)\n"
                "  configure_test_pch(${target} seed)\n"
                "  get_target_property(reuse ${target} PRECOMPILE_HEADERS_REUSE_FROM)\n"
                '  file(APPEND "${CMAKE_BINARY_DIR}/reuse.txt" "${target}=${reuse}\\n")\n'
                "endforeach()\n",
                encoding="utf-8",
            )
            build = root / "build"
            result = runConfigure(root, build, "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            values = dict(line.split("=", 1) for line in (build / "reuse.txt").read_text().splitlines())
            self.assertEqual("seed", values.pop("identical"))
            for target, reuse in values.items():
                with self.subTest(target=target):
                    self.assertEqual("reuse-NOTFOUND", reuse)
            commands = json.loads((build / "compile_commands.json").read_text(encoding="utf-8"))
            for entry in commands:
                command = entry["command"]
                if "identical.dir" in command:
                    self.assertIn("seed.dir", command)
                    self.assertIn("cmake_pch", command)
                elif any(f"{target}.dir" in command for target in values):
                    self.assertNotIn("cmake_pch", command)


@unittest.skipUnless(shutil.which("cmake") and shutil.which("ninja"), "CMake and Ninja are required")
class SharedCompilationGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cmake_version = subprocess.check_output(["cmake", "--version"], text=True, timeout=10)
        if tuple(map(int, re.search(r"(\d+)\.(\d+)\.(\d+)", cmake_version).groups())) < (4, 0, 2):
            raise unittest.SkipTest("Project graph requires CMake 4.0.2 or newer")
        configuration = productionConfiguration()
        cls.compiler = (
            configuration.get("CMAKE_CXX_COMPILER")
            or os.environ.get("CMAKE_CXX_COMPILER")
            or os.environ.get("CXX")
            or shutil.which("g++-15")
            or shutil.which("clang-cl" if os.name == "nt" else "c++")
        )
        if not cls.compiler:
            raise unittest.SkipTest("No C++ compiler is available")
        try:
            version = subprocess.check_output([cls.compiler, "--version"], text=True, timeout=10)
        except (OSError, subprocess.CalledProcessError) as error:
            raise unittest.SkipTest(f"Selected C++ compiler is unavailable: {error}") from error
        minimum = 20 if "clang" in version.lower() else 15
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
        if not match or int(match.group(1)) < minimum:
            raise unittest.SkipTest("Project graph requires GCC 15 or LLVM 20.1.8 or newer")
        cls.temporary = tempfile.TemporaryDirectory(prefix="nouraajd-shared-graph-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.source = Path(cls.temporary.name)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        before_resources, resources_and_tests = cmake.split("configure_file(res/config/adventure.json", 1)
        _resources, tests = resources_and_tests.split("enable_testing()", 1)
        # Use the production target definitions without staging any runtime assets.
        projected = before_resources + "enable_testing()" + tests
        projected = projected.replace("${CMAKE_SOURCE_DIR}", "${GAME_GRAPH_SOURCE_ROOT}")
        projected = projected.replace("${CMAKE_CURRENT_SOURCE_DIR}", "${GAME_GRAPH_SOURCE_ROOT}")
        projected = re.sub(
            r"include\((cmake/[^)]+)\)", lambda match: f'include("{ROOT.as_posix()}/{match[1]}")', projected
        )
        projected = re.sub(
            r"(?<![\w/])((?:src|tests|native_plugins)/[\w./-]+\.(?:cpp|h))",
            lambda match: "${GAME_GRAPH_SOURCE_ROOT}/" + match[1],
            projected,
        )
        projected = f'set(GAME_GRAPH_SOURCE_ROOT "{ROOT.as_posix()}")\n' + projected
        (cls.source / "CMakeLists.txt").write_text(projected, encoding="utf-8")
        cls.build = cls.source / "build"
        result = runConfigure(
            cls.source,
            cls.build,
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_CXX_COMPILER={cls.compiler}",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            "-DGAME_ENABLE_PCH=OFF",
            "-DGAME_ENABLE_UNITY_BUILD=ON",
            *(f"-D{key}={value}" for key, value in configuration.items()),
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.commands = json.loads((cls.build / "compile_commands.json").read_text(encoding="utf-8"))

    def commandsFor(self, relative):
        source = (ROOT / relative).resolve()
        return [entry for entry in self.commands if Path(entry["file"]).resolve() == source]

    def testBindingObjectsCompileOnceForModuleAndEmbeddedInterpreter(self):
        sources = ["src/core/CModule.cpp"]
        sources.extend(path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "src/core/bindings").glob("*.cpp")))
        self.assertGreater(len(sources), 1, "Binding registration must remain split across translation units")
        for source in sources:
            with self.subTest(source=source):
                commands = self.commandsFor(source)
                self.assertEqual(1, len(commands), f"Compile {source} once for both binding consumers")
                self.assertIn("game_binding_objects.dir", commands[0]["command"])
        ninja = (self.build / "build.ninja").read_text(encoding="utf-8")
        targets = (
            ("game_core", "monster_balance_unit_tests") if os.name == "nt" else ("_game", "monster_balance_unit_tests")
        )
        for target in targets:
            self.assertRegex(ninja, rf"build {target}[^\n]*: [^\n]*game_binding_objects\.dir")

    def testRuntimeAdaptersCompileInEachConsumerWithItsOwnVisibility(self):
        commands = self.commandsFor("src/core/CModuleRuntime.cpp")
        self.assertEqual(2, len(commands), "Module and embedded interpreter need separate runtime adapters")
        owners = (
            ("game_core", "monster_balance_unit_tests") if os.name == "nt" else ("_game", "monster_balance_unit_tests")
        )
        for owner in owners:
            with self.subTest(owner=owner):
                owned = [
                    entry for entry in commands if f"CMakeFiles/{owner}.dir/" in entry["command"].replace("\\", "/")
                ]
                self.assertEqual(1, len(owned), f"Compile the runtime adapter once inside {owner}")
                command = owned[0]["command"]
                self.assertNotIn("game_binding_objects.dir", command)
                self.assertNotIn("game_core_objects.dir", command)
                if os.name == "nt":
                    self.assertIn("GAME_CORE_BUILD", command)
                elif owner == "_game":
                    self.assertIn("-fvisibility=hidden", command)
                    self.assertIn("-fvisibility-inlines-hidden", command)
                else:
                    self.assertNotIn("-fvisibility=hidden", command)
                    self.assertNotIn("-fvisibility-inlines-hidden", command)
        unity_sources = {Path(entry["file"]) for entry in self.commands if "Unity" in Path(entry["file"]).parts}
        self.assertTrue(unity_sources)
        for unity in unity_sources:
            self.assertNotIn("CModuleRuntime.cpp", unity.read_text(encoding="utf-8"))

    def testSharedRandomMapBodiesCompileOnceForBothTestExecutables(self):
        for name in ("test_random_map_optimizations.cpp", "test_tile_recipes.cpp", "test_generated_names.cpp"):
            with self.subTest(source=name):
                commands = self.commandsFor(f"tests/unit/{name}")
                self.assertEqual(1, len(commands), f"Compile {name} once for both test executables")
                self.assertIn("random_map_test_objects.dir", commands[0]["command"])
                self.assertNotIn("GAME_RANDOM_MAP_OPTIMIZATION_MAIN", commands[0]["command"])
        driver = self.commandsFor("tests/unit/random_map_optimization_main.cpp")
        self.assertEqual(1, len(driver))
        ninja = (self.build / "build.ninja").read_text(encoding="utf-8")
        for target in ("performance_guard_tests", "random_map_optimization_tests"):
            self.assertRegex(ninja, rf"build {target}[^\n]*: [^\n]*random_map_test_objects\.dir")

    def testGeneratedCommandsPreserveOptimizationAndAvoidModuleFlags(self):
        self.assertFalse((self.build / "images").exists(), "Graph probes must not copy runtime assets")
        counts = Counter(Path(entry["file"]).name for entry in self.commands)
        self.assertGreater(sum(count for name, count in counts.items() if name.startswith("unity_")), 1)
        for entry in self.commands:
            if "game_binding_objects.dir" not in entry["command"]:
                continue
            command = entry["command"]
            self.assertRegex(command, r"(?:-O3|/O2)(?:\s|$)")
            self.assertRegex(command, r"(?:-std=c\+\+26|[-/]std:c\+\+latest)(?:\s|$)")
            self.assertNotIn("-fmodules-ts", command)
            self.assertNotIn("-fmodule-mapper", command)

    def testSharedTestPchIsUsedOnlyByCompatibleProductionTargets(self):
        result = runConfigure(self.source, self.build, "-DGAME_ENABLE_PCH=ON")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        cache = (self.build / "CMakeCache.txt").read_text(encoding="utf-8")
        if "GAME_ENABLE_PCH:BOOL=OFF" in cache:
            self.skipTest("The selected compiler is covered by the Clang 20 PCH compatibility policy")
        commands = json.loads((self.build / "compile_commands.json").read_text(encoding="utf-8"))
        by_source = {Path(entry["file"]).name: entry["command"] for entry in commands}
        for source in ("test_core.cpp", "test_performance.cpp", "test_random_map_optimizations.cpp"):
            with self.subTest(source=source):
                self.assertIn("game_test_pch.dir", by_source[source])
                self.assertIn("cmake_pch", by_source[source])
        for source in ("test_monster_balance.cpp", "test_handler.cpp", "test_map.cpp"):
            if source in by_source:
                with self.subTest(source=source):
                    self.assertNotIn("cmake_pch", by_source[source])
        pch_commands = [
            entry for entry in commands if "game_test_pch.dir" in entry["command"] and "cmake_pch" in entry["file"]
        ]
        self.assertEqual(1, len(pch_commands), "The compatible test cohort must create one PCH")


class CompilerCommandGraphTest(unittest.TestCase):
    def testProductionGraphAcceptsClangClLatestSpellingAndRejectsAnOlderStandard(self):
        with tempfile.TemporaryDirectory() as directory:
            graph = SharedCompilationGraphTest("testGeneratedCommandsPreserveOptimizationAndAvoidModuleFlags")
            graph.build = Path(directory)
            graph.commands = [
                {"file": f"Unity/unity_{index}_cxx.cxx", "command": "clang-cl.exe /O2"} for index in range(2)
            ]
            # CMake's clang-cl command observed in the Windows build graph.
            binding = {
                "file": "src/core/CModule.cpp",
                "command": "clang-cl.exe /O2 /DNDEBUG -std:c++latest -MD "
                "/FoCMakeFiles/game_binding_objects.dir/src/core/CModule.cpp.obj -c src/core/CModule.cpp",
            }
            graph.commands.append(binding)
            graph.testGeneratedCommandsPreserveOptimizationAndAvoidModuleFlags()
            binding["command"] = binding["command"].replace("-std:c++latest", "/std:c++latest")
            graph.testGeneratedCommandsPreserveOptimizationAndAvoidModuleFlags()
            binding["command"] = binding["command"].replace("/std:c++latest", "/std:c++20")
            with self.assertRaises(AssertionError):
                graph.testGeneratedCommandsPreserveOptimizationAndAvoidModuleFlags()


if __name__ == "__main__":
    unittest.main()
