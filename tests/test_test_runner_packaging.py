# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestRunnerPackagingTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="nouraajd-test-runner-")
        self.addCleanup(temporary.cleanup)
        self.package = Path(temporary.name)
        for name in ("test.py", "game_simulation.py", "mcp.py", "play.py", "game_diagnostics.py", "quest_state.py"):
            shutil.copy2(ROOT / name, self.package / name)

    def runPackaged(self, *arguments, build_dir=None):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.update(
            GAME_BUILD_DIR=str(build_dir or self.package / "no-native-build"),
            GAME_TEST_JOBS="1",
            GAME_TEST_OUTPUT_DIR=str(self.package / "test-output"),
            SDL_VIDEODRIVER="dummy",
            SDL_AUDIODRIVER="dummy",
            SDL_RENDER_DRIVER="software",
        )
        return subprocess.run(
            [sys.executable, *arguments],
            cwd=self.package,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def testInstalledRunnerHelpAndImportWorkWithoutSourceTests(self):
        for arguments, expected in (
            (("test.py", "--help"), "usage:"),
            (("-c", "import test; print(test.SOURCE_UI_TESTS_AVAILABLE)"), "False"),
        ):
            with self.subTest(arguments=arguments):
                result = self.runPackaged(*arguments)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)

    def testAvailableSourcePackageDoesNotHideImportFailures(self):
        source_tests = self.package / "tests"
        source_tests.mkdir()
        (source_tests / "__init__.py").write_text("", encoding="utf-8")
        runner_path = self.package / "test.py"
        runner_source = runner_path.read_text(encoding="utf-8")
        for new_registration in (False, True):
            with self.subTest(new_registration=new_registration):
                lines = runner_source.splitlines(keepends=True)
                guard = next(
                    node
                    for node in ast.parse(runner_source).body
                    if isinstance(node, ast.If)
                    and isinstance(node.test, ast.Name)
                    and node.test.id == "SOURCE_UI_TESTS_AVAILABLE"
                )
                if new_registration:
                    lines.insert(
                        guard.lineno,
                        "    from tests.test_future_source_registration import FutureSourceTest\n",
                    )
                source = "".join(lines)
                runner_path.write_text(source, encoding="utf-8")
                guard = next(
                    node
                    for node in ast.parse(source).body
                    if isinstance(node, ast.If)
                    and isinstance(node.test, ast.Name)
                    and node.test.id == "SOURCE_UI_TESTS_AVAILABLE"
                )
                first_module = next(
                    node.module
                    for node in guard.body
                    if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tests.")
                )
                module_path = self.package.joinpath(*first_module.split(".")).with_suffix(".py")
                module_path.parent.mkdir(parents=True, exist_ok=True)
                module_path.write_text('raise ImportError("deliberate source-test import failure")\n', encoding="utf-8")
                result = self.runPackaged("test.py", "--help")
                self.assertNotEqual(0, result.returncode)
                self.assertIn("deliberate source-test import failure", result.stderr)

    def testInstalledLaunchersHelpWorksWithoutNativeBuild(self):
        for launcher in ("play.py", "mcp.py"):
            with self.subTest(launcher=launcher):
                result = self.runPackaged(launcher, "--help")
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("usage:", result.stdout)
                self.assertIn("--debug", result.stdout)

    def testCliHarnessImportKeepsTheSourceRunnerWhenBuildHasACopy(self):
        build_dir = self.package / "build"
        build_dir.mkdir()
        shutil.copy2(ROOT / "test.py", build_dir / "test.py")
        result = self.runPackaged(
            "test.py", "TestRunnerSuiteTest.testImportedHarnessUsesExecutingModule", build_dir="build"
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Ran 1 test", result.stdout + result.stderr)
        self.assertNotIn("skipped", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
