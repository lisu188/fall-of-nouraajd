# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Original whitespace-only conflict hunks are resolved only in the isolated build copy."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_prepare_conflicts as replay
from scripts import history_source_prep as preparation
from scripts import verify_history as verify

SIDE = b">>>>>>> refs/remotes/origin/master\n"


class HistoricalConflictPreparationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.parents = {
            "include/value.h": b"#pragma once\nint value();\n",
            "value.cpp": b'#include "include/value.h"\nint value() {\n\treturn 7;\n}\n',
        }
        self.inputs = {
            "include/value.h": b"#pragma once\n<<<<<<< HEAD\nint  value();\n\n=======\nint value();\n" + SIDE,
            "value.cpp": (
                b'#include "include/value.h"\nint value() {\n<<<<<<< HEAD\n    return 7;\n=======\n\treturn 7;\n'
                + SIDE
                + b"}\n"
            ),
        }
        for name, data in self.inputs.items():
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        mock = patch.object(
            replay, "INPUTS", {name: hashlib.sha256(data).hexdigest() for name, data in self.inputs.items()}
        )
        mock.start()
        self.addCleanup(mock.stop)

    def runCommand(self, *args):
        self.fail("Conflict resolution cannot execute historical programs")

    def prepare(self):
        return preparation.prepareSources(self.source, self.root / "proof", {}, {}, self.runCommand)

    def testOnlyExactWhitespaceConflictsResolveToTheRecordedSide(self):
        recipe = {"id": "fixture", "pythonAbi": "none", "qmakeArguments": []}
        self.assertEqual([], verify.selectRecipe([recipe], self.source, "fixture")["qmakeArguments"])
        result = self.prepare()
        self.assertEqual("success", result["status"])
        self.assertEqual(["conflictResolution"], [step["name"] for step in result["steps"]])
        self.assertEqual(
            sorted([*self.inputs, replay.SUPPLIED_PATH]), [entry["path"] for entry in result["outputs"]]
        )
        for entry in result["outputs"]:
            if entry["path"] == replay.SUPPLIED_PATH:
                self.assertIsNone(entry["before"])
                self.assertEqual("following commit's omitted source supplied", entry["purpose"])
                continue
            self.assertEqual(replay.INPUTS[entry["path"]], entry["before"]["sha256"])
            self.assertEqual("original whitespace-only merge-conflict hunks resolved", entry["purpose"])
        self.assertEqual(self.parents, {name: (self.source / name).read_bytes() for name in self.parents})
        self.assertEqual(replay.SUPPLIED, (self.source / replay.SUPPLIED_PATH).read_bytes())
        self.assertEqual(replay.SUPPLIED_SHA256, hashlib.sha256(replay.SUPPLIED).hexdigest())
        self.assertEqual(
            {replay.SUPPLIED_PATH: {"sha256": replay.SUPPLIED_SHA256, "sourceCommit": replay.SUPPLIED_COMMIT}},
            result["identity"]["conflictResolution"]["supplied"],
        )

    def testPresentFollowingCommitSourceIsNotSuppliedAndAChangedOneIsRejected(self):
        target = self.source / replay.SUPPLIED_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(replay.SUPPLIED)
        result = self.prepare()
        self.assertEqual({}, result["identity"]["conflictResolution"]["supplied"])
        self.assertNotIn(replay.SUPPLIED_PATH, [entry["path"] for entry in result["outputs"]])
        for name, data in self.inputs.items():
            (self.source / name).write_bytes(data)
        target.write_bytes(b"different")
        self.assertIsNone(replay.conflictResolutionPlan(self.source))
        identity = result["identity"]["conflictResolution"]
        self.assertEqual(replay.BOUNDARY, identity["validationBoundary"])
        self.assertEqual(replay.SIDE, identity["side"])

    def testChangedInputsAreIgnoredAndSemanticConflictsAreRejected(self):
        (self.source / "value.cpp").write_bytes(self.inputs["value.cpp"] + b"\n")
        self.assertIsNone(replay.conflictResolutionPlan(self.source))
        self.assertFalse(preparation.preparationRequired(self.source))
        semantic = self.inputs["value.cpp"].replace(b"\treturn 7;", b"\treturn 8;")
        (self.source / "value.cpp").write_bytes(semantic)
        with patch.dict(replay.INPUTS, {"value.cpp": hashlib.sha256(semantic).hexdigest()}):
            with self.assertRaisesRegex(ValueError, "non-whitespace hunk"):
                replay.conflictResolutionPlan(self.source)
        self.assertIsNone(replay.resolveConflicts(b"<<<<<<< HEAD\na\n=======\na\n>>>>>>> other\n"))
        self.assertIsNone(replay.resolveConflicts(b"no conflict\n"))
        self.assertIsNone(replay.resolveConflicts(b"<<<<<<< HEAD\na\n=======\na\n"))

    def testPortableReplayIsIdempotentAndRejectsChangedOriginals(self):
        result = self.prepare()
        evidence = self.source / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(result))
        for name, data in self.inputs.items():
            (self.source / name).write_bytes(data)
        (self.source / replay.SUPPLIED_PATH).unlink()
        self.assertTrue(replay.prepareConflictResolution(self.source, evidence))
        self.assertEqual(replay.SUPPLIED, (self.source / replay.SUPPLIED_PATH).read_bytes())
        self.assertEqual(self.parents, {name: (self.source / name).read_bytes() for name in self.parents})
        self.assertFalse(replay.prepareConflictResolution(self.source, evidence))
        (self.source / "value.cpp").write_bytes(b"changed original")
        with self.assertRaisesRegex(ValueError, "original inputs"):
            replay.prepareConflictResolution(self.source, evidence)
        self.assertEqual(b"changed original", (self.source / "value.cpp").read_bytes())

    def testSymlinkedInputsArePreserved(self):
        protected = self.root / "protected"
        protected.write_bytes(self.inputs["value.cpp"])
        (self.source / "value.cpp").unlink()
        (self.source / "value.cpp").symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.prepare()
        self.assertEqual(self.inputs["value.cpp"], protected.read_bytes())


if __name__ == "__main__":
    unittest.main()
