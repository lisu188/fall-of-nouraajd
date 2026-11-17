# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unfinished original refactor lines are completed only in the isolated build copy, with the developer's lines."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_prepare_refactor_lines as replay
from scripts import history_source_prep as preparation
from scripts import verify_history as verify

STATE = "1" * 40
NEXT = "2" * 40


class HistoricalRefactorPreparationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        (self.source / "src").mkdir(parents=True)
        self.originals = {
            "src/monster.cpp": b"void f() {\n  GameScene::getPlayer()->hit();\n}\n",
            "src/tile.cpp": b"void RoadTile() { GameScene::getPlayer()->heal(1); }\n",
        }
        for name, data in self.originals.items():
            (self.source / name).write_bytes(data)
        states = {
            STATE: {
                "src/monster.cpp": {
                    "sha256": hashlib.sha256(self.originals["src/monster.cpp"]).hexdigest(),
                    "lines": [("  GameScene::getPlayer()->hit();", "  map->getScene()->getPlayer()->hit();", NEXT)],
                },
                "src/tile.cpp": {
                    "sha256": hashlib.sha256(self.originals["src/tile.cpp"]).hexdigest(),
                    "lines": [("void RoadTile() { GameScene::getPlayer()->heal(1); }", replay.ROAD_TILE, NEXT)],
                },
            }
        }
        self.header = b"class GameScene { Player *getPlayer() const; };\n"
        (self.source / "src/gamescene.h").write_bytes(self.header)
        for mock in (
            patch.object(replay, "STATES", states),
            patch.object(replay, "CONTEXT", {STATE: {"src/gamescene.h": hashlib.sha256(self.header).hexdigest()}}),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def runCommand(self, *args):
        self.fail("Refactor completion cannot execute historical programs")

    def prepare(self):
        return preparation.prepareSources(self.source, self.root / "proof", {}, {}, self.runCommand)

    def testOnlyTheExactOriginalStateGetsTheDevelopersFollowingLines(self):
        recipe = {"id": "fixture", "pythonAbi": "none", "qmakeArguments": []}
        self.assertEqual([], verify.selectRecipe([recipe], self.source, "fixture")["qmakeArguments"])
        result = self.prepare()
        self.assertEqual("success", result["status"])
        self.assertEqual(["refactorCompletion"], [step["name"] for step in result["steps"]])
        self.assertEqual(sorted(self.originals), [entry["path"] for entry in result["outputs"]])
        for entry in result["outputs"]:
            self.assertEqual(hashlib.sha256(self.originals[entry["path"]]).hexdigest(), entry["before"]["sha256"])
            self.assertEqual(
                "unfinished-refactor lines completed with the developer's own following lines", entry["purpose"]
            )
        self.assertEqual(
            b"void f() {\n  map->getScene()->getPlayer()->hit();\n}\n", (self.source / "src/monster.cpp").read_bytes()
        )
        self.assertEqual((replay.ROAD_TILE + "\n").encode(), (self.source / "src/tile.cpp").read_bytes())
        identity = result["identity"]["refactorCompletion"]
        self.assertEqual(STATE, identity["state"])
        self.assertEqual(replay.BOUNDARY, identity["validationBoundary"])
        expected = [list(replay.STATES[STATE]["src/tile.cpp"]["lines"][0])]
        self.assertEqual(expected, identity["files"]["src/tile.cpp"]["lines"])

    def testUnchangedFilesBeforeTheHeaderChangeAreLeftAlone(self):
        (self.source / "src/gamescene.h").write_bytes(b"class GameScene { static Player *getPlayer(); };\n")
        self.assertIsNone(replay.refactorLinesPlan(self.source))
        self.assertEqual("not-required", self.prepare()["status"])
        self.assertEqual(self.originals["src/monster.cpp"], (self.source / "src/monster.cpp").read_bytes())
        (self.source / "src/gamescene.h").unlink()
        self.assertIsNone(replay.refactorLinesPlan(self.source))

    def testChangedOriginalsAreIgnoredAndAmbiguousLinesAreRejected(self):
        (self.source / "src/tile.cpp").write_bytes(self.originals["src/tile.cpp"] + b"\n")
        self.assertIsNone(replay.refactorLinesPlan(self.source))
        self.assertFalse(preparation.preparationRequired(self.source))
        doubled = self.originals["src/tile.cpp"] * 2
        (self.source / "src/tile.cpp").write_bytes(doubled)
        with patch.dict(replay.STATES[STATE]["src/tile.cpp"], {"sha256": hashlib.sha256(doubled).hexdigest()}):
            with self.assertRaisesRegex(ValueError, "not unique"):
                replay.refactorLinesPlan(self.source)

    def testPortableReplayIsIdempotentAndRejectsChangedOriginals(self):
        result = self.prepare()
        evidence = self.source / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(result))
        for name, data in self.originals.items():
            (self.source / name).write_bytes(data)
        self.assertTrue(replay.prepareRefactorLines(self.source, evidence))
        self.assertFalse(replay.prepareRefactorLines(self.source, evidence))
        (self.source / "src/gamescene.h").write_bytes(b"changed header")
        with self.assertRaisesRegex(ValueError, "original inputs"):
            replay.prepareRefactorLines(self.source, evidence)
        (self.source / "src/gamescene.h").write_bytes(self.header)
        (self.source / "src/monster.cpp").write_bytes(b"changed original")
        with self.assertRaisesRegex(ValueError, "original inputs"):
            replay.prepareRefactorLines(self.source, evidence)
        self.assertEqual(b"changed original", (self.source / "src/monster.cpp").read_bytes())

    def testSymlinkedInputsArePreserved(self):
        protected = self.root / "protected"
        protected.write_bytes(self.originals["src/tile.cpp"])
        (self.source / "src/tile.cpp").unlink()
        (self.source / "src/tile.cpp").symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.prepare()
        self.assertEqual(self.originals["src/tile.cpp"], protected.read_bytes())


class ReviewedRefactorLinesTest(unittest.TestCase):
    def show(self, commit, name):
        try:
            return subprocess.run(
                ["git", "show", f"{commit}:{name}"], cwd=verify.REPO_ROOT, capture_output=True, check=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("Original history is not available in this checkout")

    def testEveryReplacementIsTheDevelopersOwnLineAndEveryInputIsPinned(self):
        self.assertEqual(set(replay.STATES), set(replay.CONTEXT))
        for commit, context in replay.CONTEXT.items():
            for name, expected in context.items():
                self.assertEqual(expected, hashlib.sha256(self.show(commit, name)).hexdigest())
        before = self.show("b20a2bce816b58cae9d510bfdc390aaa2e4d73ec", "src/gamescene.h")
        self.assertNotEqual(replay.INSTANCE_SCENE["src/gamescene.h"], hashlib.sha256(before).hexdigest())
        for commit, files in replay.STATES.items():
            for name, spec in files.items():
                original = self.show(commit, name)
                self.assertEqual(spec["sha256"], hashlib.sha256(original).hexdigest())
                for old, new, source in spec["lines"]:
                    self.assertEqual(1, original.count(old.encode()))
                    self.assertIn(new.encode(), self.show(source, name))


if __name__ == "__main__":
    unittest.main()
