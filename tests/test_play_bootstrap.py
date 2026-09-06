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
import ast
import importlib.machinery
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]


class PlayBootstrapTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="nouraajd-launcher-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.addCleanup(os.chdir, Path.cwd())
        self.enterContext(patch.object(sys, "path", list(sys.path)))
        self.enterContext(patch.dict(os.environ, {"GAME_BUILD_DIR": "", "GAME_BUILD_CONFIG": ""}))

    def bootstrap(self, script_root):
        module = ast.parse((REPO_ROOT / "play.py").read_text(encoding="utf-8"))
        isolated_module = ast.Module(
            body=[node for node in module.body if isinstance(node, ast.FunctionDef)],
            type_ignores=[],
        )
        namespace = {"os": os, "Path": Path, "sys": sys, "__file__": str(script_root / "play.py")}
        exec(compile(isolated_module, str(REPO_ROOT / "play.py"), "exec"), namespace)
        namespace["_bootstrap"]()

    def writeExtension(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        module_path = directory / "_game.py"
        module_path.write_text("", encoding="utf-8")
        return module_path

    def assertExtensionSelected(self, expected):
        spec = importlib.machinery.PathFinder.find_spec("_game", sys.path)
        self.assertIsNotNone(spec)
        self.assertEqual(expected.resolve(), Path(spec.origin).resolve())

    def testDefaultConfigurationPrefersRelease(self):
        build_root = self.root / "cmake-build-release"
        for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"):
            self.writeExtension(build_root / config)

        self.bootstrap(self.root)

        self.assertExtensionSelected(build_root / "Release" / "_game.py")

    def testExplicitConfigurationSelectsDebug(self):
        build_root = self.root / "cmake-build-release"
        self.writeExtension(build_root / "Release")
        expected = self.writeExtension(build_root / "Debug")
        os.environ["GAME_BUILD_CONFIG"] = "Debug"

        self.bootstrap(self.root)

        self.assertExtensionSelected(expected)

    def testRelativeBuildOverrideResolvesFromScriptRoot(self):
        self.writeExtension(self.root / "cmake-build-release")
        expected = self.writeExtension(self.root / "custom-build")
        os.environ["GAME_BUILD_DIR"] = "custom-build"
        unrelated_cwd = self.root / "unrelated"
        unrelated_cwd.mkdir()
        os.chdir(unrelated_cwd)

        self.bootstrap(self.root)

        self.assertEqual(expected.parent.resolve(), Path.cwd().resolve())
        self.assertExtensionSelected(expected)

    def testAbsoluteBuildOverrideResolvesOutsideScriptRoot(self):
        script_root = self.root / "source"
        self.writeExtension(script_root / "cmake-build-release")
        expected = self.writeExtension(self.root / "custom-build")
        os.environ["GAME_BUILD_DIR"] = str(expected.parent)

        self.bootstrap(script_root)

        self.assertEqual(expected.parent.resolve(), Path.cwd().resolve())
        self.assertExtensionSelected(expected)

    def testCopiedLauncherFindsConfiguredExtension(self):
        for resource in ("config", "maps", "plugins"):
            (self.root / resource).mkdir()
        expected = self.writeExtension(self.root / "Release")
        os.environ["GAME_BUILD_CONFIG"] = "Release"

        self.bootstrap(self.root)

        self.assertEqual(self.root.resolve(), Path.cwd().resolve())
        self.assertExtensionSelected(expected)

    def testPackagedLauncherFindsRootExtension(self):
        for resource in ("config", "maps", "plugins"):
            (self.root / resource).mkdir()
        expected = self.writeExtension(self.root)

        self.bootstrap(self.root)

        self.assertExtensionSelected(expected)


if __name__ == "__main__":
    unittest.main()
