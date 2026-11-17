# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Focused checks for the compile-only historical workbench."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import history_workbench as workbench
from tests.test_history_smoke import pngBytes


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

    def testBuildRunsTheSharedSourcePreparationBeforeQmake(self):
        (self.source / "game.pro").write_text("LIBS += -lpython2.7\n")
        (self.source / "preprocessor.py").write_text("# original property generator\n")
        result = subprocess.CompletedProcess([], 0, "rc=0", "")
        with mock.patch.object(workbench, "docker", return_value=result) as run:
            self.assertTrue(workbench.build(self.commit))
        command = run.call_args.args[0]
        self.assertLess(command.index("history_source_prep.py"), command.index("QMAKE_CXX=test-compiler"))
        self.assertIn("--source-root " + str(self.source), command)
        self.assertIn("--recipe test-python27", command)

    def testExportRetainsOriginalGeneratorPreparationProof(self):
        fingerprint = "b" * 64
        evidence = self.root / "verify/evidence" / fingerprint
        evidence.mkdir(parents=True)
        report = {
            "status": "success",
            "sourceCommit": self.commit,
            "restoration": {"restoredFilesFingerprint": fingerprint},
        }
        (evidence / "verification.json").write_text(json.dumps(report))
        (evidence / "build.log").write_bytes(b"real build log\n")
        files = {
            "source-preparation.json": b'{"status":"success"}\n',
            "source-preparation.log": b"generator log\n",
            "legacy_tiles.json": b'{"GrassTile":{"path":"images/tiles/grass","canStep":true}}\n',
        }
        for name, data in files.items():
            (evidence / name).write_bytes(data)
        repository = self.root / "repository"
        with (
            mock.patch.object(workbench, "REPO", repository),
            mock.patch.object(workbench, "workbenchOverrides", return_value=self.root / "overrides.json"),
            mock.patch.object(workbench.rh, "loadOverrides", return_value={}),
            mock.patch.object(workbench.rh, "GitObjects"),
            mock.patch.object(workbench.rh, "prepareSnapshot", return_value=({}, report["restoration"])),
        ):
            workbench.export()
        for name, data in files.items():
            self.assertEqual(data, (repository / "recovery/evidence" / self.commit / name).read_bytes())

    def testProgressSeparatesEditorAndGameEvidenceAndRejectsMissingPlayer(self):
        repository = self.root / "repository"
        image = "sha256:" + "d" * 64
        fingerprint = "f" * 64
        commits = [character * 40 for character in "abc"]
        trees = {commit: {"tree": character * 40} for commit, character in zip(commits, "def")}
        for commit, mode in zip(commits, ("game", "editor", "game")):
            evidence = repository / "recovery/evidence" / commit
            evidence.mkdir(parents=True)
            checks = workbench.vh.EDITOR_CHECKS if mode == "editor" else workbench.vh.REQUIRED_CHECKS
            startup = {
                "schemaVersion": 1,
                "status": "ready",
                "mode": mode,
                "checks": {name: True for name in checks},
                "frame": {
                    "path": "startup.png",
                    "width": 2,
                    "height": 1,
                    "sha256": hashlib.sha256(pngBytes()).hexdigest(),
                },
            }
            if commit == commits[-1]:
                startup["checks"].pop("player")
            report = {
                "status": "success",
                "sourceCommit": commit,
                "sourceTree": trees[commit]["tree"],
                "toolchainImage": image,
                "startupMode": mode,
                "smoke": {"startup": startup},
                "restoration": {"restoredFilesFingerprint": fingerprint},
            }
            if mode == "editor":
                report["startupSelection"] = {
                    "mode": mode,
                    "originalInputs": [
                        {"path": name, "blob": "e" * 40, "sha256": "f" * 64}
                        for name in ("main.cpp", "config/init.json")
                    ],
                }
            (evidence / "verification.json").write_text(json.dumps(report))
            (evidence / "startup.json").write_text(json.dumps(startup))
            (evidence / "startup.png").write_bytes(pngBytes())
        with (
            mock.patch.object(workbench, "REPO", repository),
            mock.patch.object(workbench, "ROOTFS", None),
            mock.patch.object(workbench, "TREE_OF", trees),
            mock.patch.object(workbench, "ORDER", commits),
            mock.patch.object(workbench, "CATALOG", {"trees": list(trees.values())}),
            mock.patch.dict(workbench.os.environ, {"HISTORY_TOOLCHAIN_IMAGE_ID": image}),
            mock.patch.object(workbench.rh, "loadOverrides", return_value={}),
            mock.patch.object(workbench.rh, "GitObjects"),
            mock.patch.object(
                workbench.rh, "prepareSnapshot", return_value=(None, {"restoredFilesFingerprint": fingerprint})
            ),
        ):
            workbench.progress()
        result = json.loads((repository / "recovery/progress.json").read_text())
        self.assertEqual(2, result["validatedCommitCount"])
        self.assertEqual(1, result["validatedGameCommitCount"])
        self.assertEqual(1, result["validatedGameTreeCount"])
        self.assertEqual(1, result["validatedEditorCommitCount"])
        self.assertEqual(1, result["validatedEditorTreeCount"])
        self.assertEqual("build-and-editor-startup-passed", result["snapshots"][1]["validation"])



class DonorSourcesTest(unittest.TestCase):
    """Project inference used when a tree has lost its .pro and no object_script listing."""

    TEMPLATE = (
        "QT += core gui\n"
        "TARGET = Game\n"
        "SOURCES += main.cpp \\\n"
        "    Map\\Map.cpp \\\n"
        "    ./view/gameview.cpp \\\n"
        "    $$PWD/gone/removed.cpp\n"
        "SOURCES += zlib/inflate.c\n"
        "HEADERS += map/map.h\n"
    )

    def test_keeps_surviving_donor_units_case_insensitively_and_adds_same_directory_files(self):
        files = [
            "main.cpp",
            "map/map.cpp",
            "map/tile.cpp",
            "map/map.h",
            "view/gameview.cpp",
            "view/moc_gameview.cpp",
            "zlib/inflate.c",
            "tools/editor.cpp",
            "tmp/generated.cpp",
        ]
        self.assertEqual(
            ["main.cpp", "map/map.cpp", "view/gameview.cpp", "zlib/inflate.c", "map/tile.cpp"],
            workbench.donorSources(self.TEMPLATE, files),
        )

    def test_include_closure_adds_new_vendored_directories_without_entry_points(self):
        contents = {
            "main.cpp": '#include "view/gameview.h"\n',
            "view/gameview.cpp": "#include <TMX\\Tmx.h>\n",
            "tmx/Tmx.h": '#include "TmxMap.h"\n',
            "tmx/TmxMap.h": "#include <tinyxml/tinyxml.h>\n",
            "tmx/TmxMap.cpp": '#include "TmxMap.h"\n#include "../zlib/zlib.h"\n',
            "tinyxml/tinyxml.h": "",
            "tinyxml/tinyxml.cpp": "",
            "tinyxml/tinyxmlparser.cpp": "",
            "tinyxml/xmltest.cpp": "int main(int argc, char** argv) {}\n",
            "zlib/zlib.h": "",
            "zlib/deflate.c": "",
            "zlib/inflate.c": "/* Example:\n    int main(void)\n */\nint inflate(void) { return 0; }\n",
            "base64/base64.cpp": "",
            "base64/base64.h": "",
        }
        template = "SOURCES += main.cpp view/gameview.cpp\n"
        self.assertEqual(
            [
                "main.cpp",
                "view/gameview.cpp",
                "tmx/TmxMap.cpp",
                "zlib/deflate.c",
                "zlib/inflate.c",
                "tinyxml/tinyxml.cpp",
                "tinyxml/tinyxmlparser.cpp",
            ],
            workbench.donorSources(template, list(contents), contents.get),
        )

    def test_returns_nothing_when_no_donor_unit_survives(self):
        self.assertEqual([], workbench.donorSources(self.TEMPLATE, ["other/new.cpp"]))

if __name__ == "__main__":
    unittest.main()
