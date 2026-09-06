import os
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


class AndroidPortScaffoldTest(unittest.TestCase):
    def test_android_native_host_embeds_existing_game_module(self):
        source = (ROOT / "src/platform/android/CAndroidMain.cpp").read_text(encoding="utf-8")
        self.assertIn('PyImport_AppendInittab("_game", &PyInit__game)', source)
        self.assertIn('CResourcesProvider::configurePlatformRoots(runtimeRoot.string(), writableRoot.string())', source)
        self.assertIn('std::getenv("TMPDIR")', source)
        self.assertIn('::setenv("TMPDIR", tempRoot.string().c_str(), 0)', source)
        self.assertIn('PyConfig_SetBytesString(&config, &config.home, pythonRoot.string().c_str())', source)
        self.assertIn('PyList_Insert(sysPath, 0, runtimePath)', source)
        self.assertIn('PyImport_ImportModule("game")', source)
        self.assertIn('PyObject_CallMethod(gameModule, "new", nullptr)', source)
        self.assertIn('filesRoot / "runtime"', source)
        self.assertIn('filesRoot / "user"', source)
        self.assertIn('filesRoot / "python"', source)
        self.assertNotIn("module_search_paths_set", source)

    def test_android_cmake_builds_monolithic_sdl_main_without_duplicate_module_entry(self):
        cmake = (ROOT / "android/CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('add_library(main SHARED ${GAME_ANDROID_SRC})', cmake)
        self.assertIn('src/core/CModuleEntry\\\\.cpp$', cmake)
        self.assertIn('game_android_python', cmake)
        self.assertIn('pybind11::headers', cmake)
        self.assertIn('${SDL2_ANDROID_LIBS}', cmake)
        self.assertIn('${SDL2_ANDROID_MAIN_LIBS}', cmake)
        self.assertIn('SDL2::SDL2main', cmake)
        self.assertIn('${SDL2_IMAGE_ANDROID_LIBS}', cmake)
        self.assertIn('${SDL2_TTF_ANDROID_LIBS}', cmake)

    def testAndroidCmakeFindsTargetPackagesOutsideTheSysroot(self):
        cmake = shutil.which("cmake")
        if cmake is None:
            self.skipTest("CMake is required for Android package-discovery regression")
        source = (ROOT / "android/CMakeLists.txt").read_text(encoding="utf-8")
        discovery = source[source.index("get_filename_component(") : source.index("add_library(game_android_python")]
        with tempfile.TemporaryDirectory(prefix="nouraajd-android-packages-") as temporary:
            project = Path(temporary)
            prefix = project / "target dependencies"
            sysroot = project / "sysroot"
            host_prefix = project / "host"
            sysroot.mkdir()
            python_include = prefix / "include/python3.14"
            python_include.mkdir(parents=True)
            python_library = prefix / "lib/libpython3.14.so"
            python_library.parent.mkdir()
            python_library.touch()
            packages = {
                "pybind11": ("pybind11::headers",),
                "SDL2": ("SDL2::SDL2", "SDL2::SDL2main"),
                "SDL2_image": ("SDL2_image::SDL2_image",),
                "SDL2_ttf": ("SDL2_ttf::SDL2_ttf",),
            }
            for package, targets in packages.items():
                package_dir = prefix / "share" / package
                package_dir.mkdir(parents=True)
                (package_dir / f"{package}Config.cmake").write_text(
                    "".join(f"add_library({target} INTERFACE IMPORTED)\n" for target in targets), encoding="utf-8"
                )
            host_package = host_prefix / "share/HostOnly"
            host_package.mkdir(parents=True)
            (host_package / "HostOnlyConfig.cmake").write_text("set(HostOnly_FOUND TRUE)\n", encoding="utf-8")
            (project / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(android_package_lookup LANGUAGES NONE)\n"
                f'set(CMAKE_FIND_ROOT_PATH "{sysroot.as_posix()}")\n'
                f'set(CMAKE_PREFIX_PATH "{prefix.as_posix()}")\n'
                f'set(CMAKE_SYSTEM_PREFIX_PATH "{host_prefix.as_posix()}")\n'
                "set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)\n"
                "set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)\n"
                "set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)\n"
                "set(CMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH FALSE)\n"
                "set(CMAKE_FIND_USE_PACKAGE_REGISTRY FALSE)\n"
                "set(CMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY FALSE)\n"
                f'set(GAME_ANDROID_DEPENDENCY_PREFIX "{prefix.as_posix()}" CACHE PATH "Fixture prefix")\n'
                f'set(GAME_ANDROID_PYTHON_INCLUDE_DIR "{python_include.as_posix()}" CACHE PATH "Fixture headers")\n'
                f'set(GAME_ANDROID_PYTHON_LIBRARY "{python_library.as_posix()}" CACHE FILEPATH "Fixture library")\n'
                + discovery
                + "\n"
                + "".join(
                    f'if (NOT TARGET {target})\nmessage(FATAL_ERROR "Missing target package: {target}")\nendif ()\n'
                    for targets in packages.values()
                    for target in targets
                )
                + f'if (NOT "{sysroot.as_posix()}" IN_LIST CMAKE_FIND_ROOT_PATH)\n'
                'message(FATAL_ERROR "Original sysroot was discarded")\nendif ()\n'
                "foreach (kind PACKAGE LIBRARY INCLUDE)\n"
                'if (NOT CMAKE_FIND_ROOT_PATH_MODE_${kind} STREQUAL "ONLY")\n'
                'message(FATAL_ERROR "Host lookup was enabled for ${kind}")\nendif ()\nendforeach ()\n'
                "find_package(HostOnly CONFIG QUIET)\n"
                'if (HostOnly_FOUND)\nmessage(FATAL_ERROR "Host-only package escaped target isolation")\nendif ()\n'
                'message(STATUS "Android target packages resolved without host fallback")\n',
                encoding="utf-8",
            )
            completed = subprocess.run(
                [cmake, "-S", str(project), "-B", str(project / "build")],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("Android target packages resolved without host fallback", completed.stdout)

    def test_gradle_stages_game_and_cpython_payloads(self):
        gradle = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('File(repositoryRoot, "res")', gradle)
        self.assertIn('File(repositoryRoot, "quest_state.py")', gradle)
        self.assertIn('into("python/lib/${pythonStdlibDir.name}")', gradle)
        self.assertIn('include("libpython*.*.so")', gradle)
        self.assertIn('include("lib*_python.so")', gradle)
        self.assertIn('from(File(dependencyPrefix, "lib"))', gradle)
        self.assertIn('include("*.so")', gradle)
        self.assertIn('ignoreAssetsPattern = "fall-of-nouraajd-dont-ignore-anything"', gradle)
        self.assertIn('File(repositoryRoot, "android/CMakeLists.txt")', gradle)
        self.assertIn('abiFilters += "arm64-v8a"', gradle)
        self.assertIn('minSdk = 28', gradle)
        self.assertIn('"-DGAME_ANDROID_DEPENDENCY_PREFIX=${dependencyPrefix.absolutePath}"', gradle)

    def testGradleSelectsTheLibraryMatchingPythonHeaders(self):
        gradle = shutil.which("gradle")
        if gradle is None and os.environ.get("GRADLE_HOME"):
            executable = "gradle.bat" if os.name == "nt" else "gradle"
            candidate = Path(os.environ["GRADLE_HOME"]) / "bin" / executable
            if candidate.is_file():
                gradle = str(candidate)
        if gradle is None:
            self.skipTest("Gradle is required to execute the Android Kotlin selector regression")

        source = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
        start = source.index("val pythonIncludeDir =")
        end = source.index("val generatedAssetsDir =", start)
        selector = source[start:end]
        staging_start = source.index("val prepareRuntimeAssets by", end)
        android_start = source.index("\nandroid {", staging_start)
        generated_directories = source[end:staging_start]
        staging_tasks = source[staging_start:android_start]
        source_arguments = dict(re.findall(r"^\s*(assets|jniLibs)\.srcDir\((.+)\)\s*$", source, re.MULTILINE))
        self.assertEqual({"assets", "jniLibs"}, set(source_arguments))
        staging_dependencies = source[source.index('tasks.named("preBuild")') :]
        with tempfile.TemporaryDirectory(prefix="nouraajd-python-selector-") as temporary:
            project = Path(temporary)
            for name, version in (
                ("official", "3.14"),
                ("alternate", "3.15"),
                ("missing", "3.14"),
                ("directory", "3.14"),
            ):
                prefix = project / name
                (prefix / "include" / f"python{version}").mkdir(parents=True)
                (prefix / "lib" / f"python{version}").mkdir(parents=True)
                (prefix / "lib" / "libpython3.so").touch()
                (prefix / "lib" / "libpython3.13.so").touch()
                if name in ("official", "alternate"):
                    (prefix / "lib" / f"libpython{version}.so").touch()
                elif name == "directory":
                    (prefix / "lib" / f"libpython{version}.so").mkdir()
            (project / "settings.gradle.kts").write_text(
                'rootProject.name = "python-library-selector-regression"\n', encoding="utf-8"
            )
            (project / "build.gradle.kts").write_text(
                "import java.io.File\n"
                "import org.gradle.api.GradleException\n"
                "import org.gradle.api.tasks.Sync\n"
                "fun selectPythonLibrary(pythonPrefix: File): File {\n"
                + selector
                + "return pythonLibrary\n}\n"
                + generated_directories
                + 'val repositoryRoot = file("repository")\n'
                'val pythonPrefix = file("official")\n'
                'val dependencyPrefix = file("dependencies")\n'
                'val pythonStdlibDir = file("official/lib/python3.14")\n'
                + staging_tasks
                + 'tasks.register("preBuild")\n'
                + staging_dependencies
                + "\n"
                'tasks.register("verifyPythonLibrarySelection") {\n'
                "    doLast {\n"
                '        check(selectPythonLibrary(file("official")) == file("official/lib/libpython3.14.so"))\n'
                '        check(selectPythonLibrary(file("alternate")) == file("alternate/lib/libpython3.15.so"))\n'
                '        for (name in listOf("missing", "directory")) {\n'
                "            val error = runCatching { selectPythonLibrary(file(name)) }.exceptionOrNull()\n"
                '            check(error is GradleException) { "Expected a missing-library error for $name" }\n'
                "        }\n"
                + f'        val assetsSource: Any = {source_arguments["assets"]}\n'
                + f'        val nativeSource: Any = {source_arguments["jniLibs"]}\n'
                + '        check(assetsSource is File) { "assets.srcDir requires a concrete File" }\n'
                '        check(nativeSource is File) { "jniLibs.srcDir requires a concrete File" }\n'
                "        check(assetsSource == generatedAssetsDir.get().asFile)\n"
                "        check(nativeSource == generatedJniLibsDir.get().asFile)\n"
                '        val preBuild = tasks.getByName("preBuild")\n'
                "        val dependencies = preBuild.taskDependencies.getDependencies(preBuild)\n"
                "        check(dependencies.contains(prepareRuntimeAssets.get()))\n"
                "        check(dependencies.contains(prepareNativeLibraries.get()))\n"
                "        check(prepareRuntimeAssets.get().destinationDir == assetsSource)\n"
                '        check(prepareNativeLibraries.get().destinationDir == File(nativeSource, "arm64-v8a"))\n'
                '        println("Python library selection regression passed")\n'
                "    }\n}\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [gradle, "--offline", "--no-daemon", "--console=plain", "verifyPythonLibrarySelection"],
                cwd=project,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("Python library selection regression passed", completed.stdout)

    def testAndroidNdkPinsMatchAcrossBuildEntrypoints(self):
        bootstrap = (ROOT / "android/bootstrap-deps.sh").read_text(encoding="utf-8")
        required = re.search(r'^ANDROID_NDK_VERSION="([0-9.]+)"$', bootstrap, re.MULTILINE)
        self.assertIsNotNone(required, "Bootstrap must declare its required Android NDK revision")
        version = required.group(1)
        gradle = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn(f'ndkVersion = "{version}"', gradle)
        for workflow in ("android.yml", "release.yml"):
            with self.subTest(workflow=workflow):
                source = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
                selected_versions = re.findall(r"ANDROID_HOME\}/ndk/([0-9.]+)", source)
                self.assertTrue(selected_versions, "Workflow must select the bootstrap NDK")
                self.assertEqual({version}, set(selected_versions))

    def testAndroidBootstrapChecksNdkBeforeDownloadsOrDependencyBuilds(self):
        if os.name != "posix":
            self.skipTest("Android bootstrap guard uses POSIX shell tooling")
        for command in ("bash", "awk", "find", "sed", "sha256sum", "tar"):
            if shutil.which(command) is None:
                self.skipTest(f"Android bootstrap guard requires {command}")
        gradle = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
        version = re.search(r'ndkVersion\s*=\s*"([0-9.]+)"', gradle).group(1)
        bootstrap = (ROOT / "android/bootstrap-deps.sh").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="nouraajd-ndk-guard-") as temporary:
            project = Path(temporary)
            script = project / "android/bootstrap-deps.sh"
            script.parent.mkdir()
            script.write_text(bootstrap, encoding="utf-8")
            fake_bin = project / "bin"
            fake_bin.mkdir()
            for command in ("curl", "git"):
                executable = fake_bin / command
                executable.write_text(
                    '#!/bin/sh\nprintf "%s\\n" "$0" >> "$GAME_TEST_DOWNLOAD_LOG"\nexit 97\n', encoding="utf-8"
                )
                executable.chmod(0o755)
            for case, revision in (("old", "28.2.13676358"), ("missing", None), ("matching", version)):
                with self.subTest(case=case):
                    ndk = project / case
                    ndk.mkdir()
                    if revision is not None:
                        (ndk / "source.properties").write_text(f"Pkg.Revision = {revision}\n", encoding="utf-8")
                    dependencies = project / f"dependencies-{case}"
                    download_log = project / f"downloads-{case}.log"
                    environment = os.environ | {
                        "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
                        "ANDROID_NDK_HOME": str(ndk),
                        "GAME_ANDROID_DEPS_DIR": str(dependencies),
                        "GAME_TEST_DOWNLOAD_LOG": str(download_log),
                    }
                    completed = subprocess.run(
                        [shutil.which("bash"), str(script)],
                        cwd=project,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if case == "matching":
                        self.assertEqual(97, completed.returncode, completed.stdout + completed.stderr)
                        self.assertTrue(dependencies.is_dir())
                        self.assertIn("curl", download_log.read_text(encoding="utf-8"))
                    else:
                        self.assertEqual(3, completed.returncode, completed.stdout + completed.stderr)
                        self.assertIn("Android NDK", completed.stderr)
                        self.assertFalse(dependencies.exists(), "Reject incompatible NDK before dependency setup")
                        self.assertFalse(download_log.exists(), "Reject incompatible NDK before network access")

    def test_dependency_bootstrap_pins_python_and_dynamic_sdl(self):
        bootstrap = (ROOT / "android/bootstrap-deps.sh").read_text(encoding="utf-8")
        triplet = (ROOT / "android/triplets/arm64-android-dynamic.cmake").read_text(encoding="utf-8")
        self.assertIn('PYTHON_VERSION="${GAME_ANDROID_PYTHON_VERSION:-3.14.7}"', bootstrap)
        self.assertIn('6d50cc3aa66e414a439594089bcdfb5f1264358155c70c1f00471c24cfb477fb', bootstrap)
        self.assertIn('VCPKG_REF="${GAME_ANDROID_VCPKG_REF:-2026.05.25}"', bootstrap)
        self.assertIn('VCPKG_TRIPLET="arm64-android-dynamic"', bootstrap)
        self.assertIn('--overlay-triplets="${SCRIPT_DIR}/triplets"', bootstrap)
        self.assertIn('--x-manifest-root="${REPO_ROOT}"', bootstrap)
        self.assertNotIn('"pybind11:${VCPKG_TRIPLET}"', bootstrap)
        for dependency in (
            "boost-algorithm",
            "boost-filesystem",
            "boost-pool",
            "pybind11",
            "sdl2",
            "sdl2-image",
            "sdl2-ttf",
        ):
            self.assertIn(dependency, bootstrap)
        self.assertIn('lib/libSDL2.so', bootstrap)
        self.assertIn('set(VCPKG_LIBRARY_LINKAGE dynamic)', triplet)
        self.assertIn('set(VCPKG_CMAKE_SYSTEM_NAME Android)', triplet)
        self.assertIn('set(VCPKG_CMAKE_SYSTEM_VERSION 28)', triplet)
        self.assertIn('set(VCPKG_CMAKE_CONFIGURE_OPTIONS -DANDROID_ABI=arm64-v8a)', triplet)

    def test_manifest_launches_sdl_activity_in_landscape(self):
        root = ET.parse(ROOT / "android/app/src/main/AndroidManifest.xml").getroot()
        application = root.find("application")
        self.assertIsNotNone(application)
        activities = application.findall("activity")
        self.assertEqual(1, len(activities))
        activity = activities[0]
        self.assertEqual(".FallOfNouraajdActivity", activity.attrib[ANDROID_NS + "name"])
        self.assertEqual("landscape", activity.attrib[ANDROID_NS + "screenOrientation"])
        self.assertEqual("true", activity.attrib[ANDROID_NS + "exported"])

    def test_android_native_plugins_keep_manifest_ids(self):
        manifest = (ROOT / "res/plugins/manifest.json").read_text(encoding="utf-8")
        runtime = (ROOT / "src/plugin/CNativePluginRuntime.cpp").read_text(encoding="utf-8")
        self.assertIn('"library": "plugins/native/native_marker_plugin"', manifest)
        self.assertIn('"library": "plugins/native/native_gameplay"', manifest)
        self.assertIn('library == "plugins/native/native_marker_plugin"', runtime)
        self.assertIn('library == "plugins/native/native_gameplay"', runtime)
        self.assertIn("native_plugin::register_dynamic_marker", runtime)
        self.assertIn("native_plugin::register_gameplay_types", runtime)

    def test_platform_resource_roots_are_explicit_and_reversible(self):
        header = (ROOT / "src/core/CProvider.h").read_text(encoding="utf-8")
        source = (ROOT / "src/core/CPlatformResources.cpp").read_text(encoding="utf-8")
        self.assertIn("configurePlatformRoots", header)
        self.assertIn("clearPlatformRoots", header)
        self.assertIn("searchPath.push_front(*packaged)", source)
        self.assertIn("searchPath.push_front(*writable)", source)
        self.assertLess(source.index("searchPath.push_front(*packaged)"), source.index("searchPath.push_front(*writable)"))


if __name__ == "__main__":
    unittest.main()
