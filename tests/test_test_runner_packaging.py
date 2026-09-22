# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

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
        for name in ("test.py", "game_simulation.py", "mcp.py", "quest_state.py"):
            shutil.copy2(ROOT / name, self.package / name)

    def runPackaged(self, *arguments):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.update(
            GAME_BUILD_DIR=str(self.package / "no-native-build"),
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
        (source_tests / "test_ui_mcp_dialogue.py").write_text(
            'raise ImportError("deliberate source-test import failure")\n', encoding="utf-8"
        )
        result = self.runPackaged("test.py", "--help")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("deliberate source-test import failure", result.stderr)


if __name__ == "__main__":
    unittest.main()
