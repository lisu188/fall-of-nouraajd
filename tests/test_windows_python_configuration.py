#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import windows_python_artifacts

REPO_ROOT = Path(__file__).resolve().parents[1]


class WindowsPythonConfigurationTest(unittest.TestCase):
    def makeSdk(self, root, *, vcpkg=False, minor=12):
        include_dir = root / "include" / "python3.12" if vcpkg else root / "Include"
        library_path = root / ("lib" if vcpkg else "libs") / "python312.lib"
        include_dir.mkdir(parents=True)
        library_path.parent.mkdir(parents=True)
        (include_dir / "Python.h").write_text("", encoding="utf-8")
        (include_dir / "patchlevel.h").write_text(
            f"#define PY_MAJOR_VERSION 3\n#define PY_MINOR_VERSION {minor}\n", encoding="utf-8"
        )
        library_path.write_bytes(b"fixture")
        return include_dir, library_path

    def testStandardAndVcpkgSdkLayoutsUseTheActiveMinorVersion(self):
        with tempfile.TemporaryDirectory(prefix="game-python-sdk-") as directory:
            for vcpkg, has_debug in ((False, False), (False, True), (True, False), (True, True)):
                with self.subTest(vcpkg=vcpkg, has_debug=has_debug):
                    root = Path(directory) / f"{vcpkg}-{has_debug}"
                    include_dir, library_path = self.makeSdk(root, vcpkg=vcpkg)
                    debug_library = (
                        root / "debug" / "lib" / "python312_d.lib" if vcpkg else root / "libs" / "python312_d.lib"
                    )
                    if has_debug:
                        debug_library.parent.mkdir(parents=True, exist_ok=True)
                        debug_library.write_bytes(b"fixture")
                    base_prefix = root / "tools" / "python3" if vcpkg else root
                    with (
                        patch.object(windows_python_artifacts.sys, "version_info", (3, 12, 10)),
                        patch.object(windows_python_artifacts.sys, "base_prefix", str(base_prefix)),
                        patch.object(windows_python_artifacts.sysconfig, "get_path", return_value=str(include_dir)),
                    ):
                        self.assertEqual(
                            (
                                include_dir.resolve(),
                                library_path.resolve(),
                                debug_library.resolve() if has_debug else None,
                            ),
                            windows_python_artifacts.resolvePythonArtifacts(),
                        )

    def testMismatchedHeadersAndMissingLibraryFailBeforeConfiguration(self):
        with tempfile.TemporaryDirectory(prefix="game-python-sdk-") as directory:
            root = Path(directory)
            include_dir, library_path = self.makeSdk(root, minor=14)
            with (
                patch.object(windows_python_artifacts.sys, "version_info", (3, 12, 10)),
                patch.object(windows_python_artifacts.sys, "base_prefix", str(root)),
                patch.object(windows_python_artifacts.sysconfig, "get_path", return_value=str(include_dir)),
            ):
                with self.assertRaisesRegex(ValueError, "do not match Python 3.12"):
                    windows_python_artifacts.resolvePythonArtifacts()
                (include_dir / "patchlevel.h").write_text(
                    "#define PY_MAJOR_VERSION 3\n#define PY_MINOR_VERSION 12\n", encoding="utf-8"
                )
                library_path.unlink()
                with self.assertRaisesRegex(ValueError, "python312.lib is missing"):
                    windows_python_artifacts.resolvePythonArtifacts()

    @unittest.skipUnless(sys.version_info[:2] == (3, 12), "The SDK CLI requires Python 3.12")
    def testArtifactCliRejectsAnInvalidSdk(self):
        with tempfile.TemporaryDirectory(prefix="game-python-sdk-") as directory:
            include_dir, _ = self.makeSdk(Path(directory), minor=14)
            driver = (
                "import runpy, sysconfig; "
                f"sysconfig.get_path = lambda name: {str(include_dir)!r}; "
                f"runpy.run_path({str(REPO_ROOT / 'scripts' / 'windows_python_artifacts.py')!r}, run_name='__main__')"
            )
            result = subprocess.run([sys.executable, "-B", "-c", driver], capture_output=True, text=True, timeout=10)
            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stdout)
            self.assertIn("do not match Python 3.12", result.stderr)

    @unittest.skipUnless(os.name == "nt", "configure.bat requires Windows")
    def testConfigureOverridesConflictingVcpkgArtifactsWithTheActiveSdk(self):
        if sys.version_info[:2] != (3, 12):
            self.skipTest("The Windows configuration probe requires Python 3.12")
        cmake_executable = shutil.which("cmake")
        if not cmake_executable:
            self.skipTest("CMake is unavailable")
        include_dir, library_path, debug_library = windows_python_artifacts.resolvePythonArtifacts()
        with tempfile.TemporaryDirectory(prefix="game-python-cmake-") as directory:
            root = Path(directory)
            tools_dir = root / "tools"
            tools_dir.mkdir()
            capture_path = root / "cmake-arguments.txt"
            (tools_dir / "cmake.cmd").write_text(
                '@echo off\n> "%GAME_CMAKE_CAPTURE%" echo %*\nexit /b 0\n', encoding="utf-8"
            )
            vcpkg_root = root / "vcpkg"
            toolchain = vcpkg_root / "scripts" / "buildsystems" / "vcpkg.cmake"
            toolchain.parent.mkdir(parents=True)
            toolchain.write_text("", encoding="utf-8")
            (vcpkg_root / "vcpkg.exe").write_bytes(b"")
            configure_script = (REPO_ROOT / "configure.bat").read_text()
            # A batch capture shim needs CALL; the production command launches cmake.exe directly.
            configure_script = configure_script.replace("\ncmake -B", "\ncall cmake -B")
            (root / "configure.bat").write_text(configure_script, encoding="utf-8")
            (root / "scripts").mkdir()
            shutil.copyfile(
                REPO_ROOT / "scripts" / "windows_python_artifacts.py", root / "scripts" / "windows_python_artifacts.py"
            )
            env = dict(os.environ)
            env.update(
                PATH=os.pathsep.join((str(tools_dir), str(Path(sys.executable).parent), env.get("PATH", ""))),
                GAME_CMAKE_CAPTURE=str(capture_path),
                GAME_WINDOWS_FAST_BUILD="0",
                GAME_WINDOWS_INSTALL_FAST_TOOLS="0",
                CMAKE_GENERATOR="Visual Studio 17 2022",
                CMAKE_GENERATOR_PLATFORM="x64",
                CONFIGURE_BUILD_DIRS="probe-build",
                VCPKG_ROOT=str(vcpkg_root),
                VCPKG_INSTALLATION_ROOT=str(vcpkg_root),
                VCPKG_INSTALLED_DIR=str(root / "installed"),
                VCPKG_TARGET_TRIPLET="x64-windows",
                VCPKG_MANIFEST_MODE="OFF",
            )
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "configure.bat"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            artifacts = dict(
                re.findall(r'-D(_?Python3_\w+)(?::\w+)?="([^"]*)"', capture_path.read_text(encoding="utf-8"))
            )

            conflict_dir = root / "conflicting-python314"
            conflict_dir.mkdir()
            shutil.copyfile(include_dir / "Python.h", conflict_dir / "Python.h")
            shutil.copyfile(include_dir / "pyconfig.h", conflict_dir / "pyconfig.h")
            (conflict_dir / "patchlevel.h").write_text(
                "#define PY_MAJOR_VERSION 3\n#define PY_MINOR_VERSION 14\n"
                '#define PY_MICRO_VERSION 7\n#define PY_VERSION "3.14.7"\n',
                encoding="utf-8",
            )
            (conflict_dir / "python314.lib").write_bytes(b"")
            (conflict_dir / "python314_d.lib").write_bytes(b"")
            project_dir = root / "project"
            project_dir.mkdir()
            (project_dir / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(PythonArtifacts LANGUAGES NONE)\n"
                'find_path(_Python3_INCLUDE_DIR NAMES Python.h PATHS "${CONFLICT_DIR}" NO_DEFAULT_PATH)\n'
                'find_library(_Python3_LIBRARY_RELEASE NAMES python314 PATHS "${CONFLICT_DIR}" NO_DEFAULT_PATH)\n'
                'find_library(_Python3_LIBRARY_DEBUG NAMES python314_d PATHS "${CONFLICT_DIR}" NO_DEFAULT_PATH)\n'
                'set(_Python3_INCLUDE_DIR "${_Python3_INCLUDE_DIR}")\n'
                'set(_Python3_LIBRARY_RELEASE "${_Python3_LIBRARY_RELEASE}")\n'
                'set(_Python3_LIBRARY_DEBUG "${_Python3_LIBRARY_DEBUG}")\n'
                "find_package(Python3 COMPONENTS Interpreter Development REQUIRED)\n"
                'if(NOT Python3_VERSION MATCHES "^3\\.12\\.")\n'
                '  message(FATAL_ERROR "Unexpected Python version: ${Python3_VERSION}")\n'
                "endif()\n"
                "foreach(target Python3::Python Python3::Module)\n"
                "  get_target_property(library ${target} IMPORTED_IMPLIB_RELEASE)\n"
                "  if(NOT library)\n"
                "    get_target_property(library ${target} IMPORTED_IMPLIB)\n"
                "  endif()\n"
                '  file(TO_CMAKE_PATH "${library}" library)\n'
                "  if(NOT library STREQUAL EXPECTED_LIBRARY)\n"
                '    message(FATAL_ERROR "Wrong release import library for ${target}: ${library}")\n'
                "  endif()\n"
                "  get_target_property(debug_library ${target} IMPORTED_IMPLIB_DEBUG)\n"
                "  if(EXPECTED_DEBUG_LIBRARY AND NOT debug_library)\n"
                '    message(FATAL_ERROR "Missing matching debug import library for ${target}")\n'
                "  endif()\n"
                "  if(debug_library)\n"
                '    file(TO_CMAKE_PATH "${debug_library}" debug_library)\n'
                "    if(NOT debug_library STREQUAL EXPECTED_DEBUG_LIBRARY)\n"
                '      message(FATAL_ERROR "Conflicting debug import library: ${debug_library}")\n'
                "    endif()\n"
                "  endif()\n"
                "endforeach()\n"
                "if(NOT Python3_Development.Module_FOUND OR NOT Python3_Development.Embed_FOUND)\n"
                '  message(FATAL_ERROR "Missing Python development components")\n'
                "endif()\n",
                encoding="utf-8",
            )
            command = [
                cmake_executable,
                "-S",
                str(project_dir),
                "-B",
                str(root / "cmake-probe"),
                "-G",
                "Visual Studio 17 2022",
                "-A",
                "x64",
                f"-DCONFLICT_DIR={conflict_dir.as_posix()}",
                f"-DEXPECTED_LIBRARY={library_path.as_posix()}",
                f"-DEXPECTED_DEBUG_LIBRARY={debug_library.as_posix() if debug_library else ''}",
            ]
            command.extend(f"-D{key}={value}" for key, value in artifacts.items())
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(str(include_dir), artifacts.get("Python3_INCLUDE_DIR"))
            self.assertEqual(str(library_path), artifacts.get("Python3_LIBRARY"))
            self.assertEqual(str(debug_library) if debug_library else "", artifacts.get("_Python3_LIBRARY_DEBUG"))
            self.assertEqual(Path(sys.executable).resolve(), Path(artifacts.get("Python3_EXECUTABLE", "")).resolve())

            helper_path = root / "scripts" / "windows_python_artifacts.py"
            helper_text = helper_path.read_text(encoding="utf-8").replace(
                "import sysconfig\n", f"import sysconfig\nsysconfig.get_path = lambda name: {str(conflict_dir)!r}\n"
            )
            helper_path.write_text(helper_text, encoding="utf-8")
            env["GAME_CMAKE_CAPTURE"] = str(root / "rejected-cmake-arguments.txt")
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "configure.bat"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("do not match Python 3.12", result.stderr)
            self.assertFalse(Path(env["GAME_CMAKE_CAPTURE"]).exists())


if __name__ == "__main__":
    unittest.main()
