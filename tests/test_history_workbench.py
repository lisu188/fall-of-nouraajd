# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Focused checks for the compile-only historical workbench."""

import contextlib
import io
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import history_workbench as workbench


class HistoricalWorkbenchBuildTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="history-workbench-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.commit = "a" * 40
        self.source = self.root / "src" / self.commit[:8]
        self.source.mkdir(parents=True)
        self.recipe = {
            "id": "test-python27",
            "pythonAbi": "2.7",
            "qmakeCommand": "/bin/true",
            "makeCommand": "/bin/true",
            "qmakeArguments": ["QMAKE_CXX=test-compiler"],
            "environment": {"PYTHONHOME": "/test/python27"},
        }
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(workbench, "WORK", self.root))
        stack.enter_context(mock.patch.object(workbench, "resolve", return_value=self.commit))
        stack.enter_context(mock.patch.object(workbench.vh, "loadRecipes", return_value=[self.recipe]))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def testBuildUsesExplicitReconstructedApplicationAndMatchingRecipe(self):
        (self.source / "Game.pro").write_text("SOURCES += old.cpp\n")
        (self.source / "game.pro").write_text("GAME_RECOVERY_APPLICATION = true\nLIBS += -lpython2.7\n")
        result = subprocess.CompletedProcess([], 0, "rc=0", "")
        with mock.patch.object(workbench, "docker", return_value=result) as run:
            self.assertTrue(workbench.build(self.commit))
        command = run.call_args.args[0]
        self.assertIn(str(self.source / "game.pro"), command)
        self.assertNotIn(str(self.source / "Game.pro"), command)
        self.assertIn("PYTHONHOME=/test/python27", command)
        self.assertIn("QMAKE_CXX=test-compiler", command)

    def testBuildUsesDeclaredDependencyOrderAndSeparateDirectories(self):
        for name in ("game", "python"):
            (self.source / name).mkdir()
        (self.source / "game.pro").write_text("TEMPLATE = subdirs\nSUBDIRS = game python\ngame.depends = python\n")
        (self.source / "game/game.pro").write_text("TEMPLATE = app\nLIBS += -lpython2.7\n")
        (self.source / "python/python.pro").write_text("TEMPLATE = lib\n")
        result = subprocess.CompletedProcess([], 0, "rc=0", "")
        with mock.patch.object(workbench, "docker", return_value=result) as run:
            self.assertTrue(workbench.build(self.commit))
        command = run.call_args.args[0]
        self.assertLess(
            command.index(str(self.source / "python/python.pro")), command.index(str(self.source / "game/game.pro"))
        )
        for name in ("python", "game"):
            self.assertIn("cd " + shlex.quote(str(self.root / "build" / self.commit[:8] / name)), command)

    def testBuildReportsMakeFailureEvenWhenOutputContainsAnOldSuccessMarker(self):
        (self.source / "game.pro").write_text("LIBS += -lpython2.7\n")
        make = self.root / "failing make"
        make.write_text("#!/bin/sh\necho 'previous rc=0'\nexit 9\n")
        make.chmod(0o700)
        self.recipe["makeCommand"] = str(make)

        def run(command, directory):
            return subprocess.run(["bash", "-c", command], cwd=directory, capture_output=True, text=True)

        with mock.patch.object(workbench, "docker", side_effect=run):
            self.assertFalse(workbench.build(self.commit))


if __name__ == "__main__":
    unittest.main()
