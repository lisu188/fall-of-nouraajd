# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Renamed-resource alias compatibility preserves the original manifest, sources and renamed files."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_prepare_resource_aliases as replay
from scripts import history_source_prep as preparation
from scripts import verify_history as verify


class HistoricalResourceAliasPreparationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.inputs = {
            "creatures.qrc": (
                b'<RCC>\n    <qresource prefix="/">\n'
                + b"".join(f"        <file>{target}</file>\n".encode() for target in sorted(replay.ALIASES))
                + b"    </qresource>\n</RCC>\n"
            ),
            "animation/animationprovider.cpp": b'time.open((path+"time.txt").c_str());\n',
            "images/monsters/octobogz/time.json": b"300\n300\n",
            "images/monsters/pritz/time.json": b"300\n300\n",
            "images/monsters/pritzmage/time.json": b"100\n200\n300\n400\n",
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
        self.fail("Resource alias preparation cannot execute historical programs")

    def prepare(self):
        return preparation.prepareSources(self.source, self.root / "proof", {}, {}, self.runCommand)

    def testOnlyExactOriginalInputsReceiveByteIdenticalAliases(self):
        recipe = {"id": "fixture", "pythonAbi": "none", "qmakeArguments": []}
        self.assertEqual([], verify.selectRecipe([recipe], self.source, "fixture")["qmakeArguments"])
        self.assertTrue(preparation.preparationRequired(self.source))
        result = self.prepare()
        self.assertEqual("success", result["status"])
        self.assertNotIn("qmakeArguments", result)
        self.assertEqual(["resourceAliases"], [step["name"] for step in result["steps"]])
        self.assertEqual(sorted(replay.ALIASES), [entry["path"] for entry in result["outputs"]])
        for entry in result["outputs"]:
            self.assertIsNone(entry["before"])
            self.assertEqual("manifest-named alias of an original renamed resource", entry["purpose"])
        self.assertEqual(self.inputs, {name: (self.source / name).read_bytes() for name in self.inputs})
        for target, source in replay.ALIASES.items():
            self.assertEqual(self.inputs[source], (self.source / target).read_bytes())
        identity = result["identity"]["resourceAliases"]
        self.assertEqual(replay.BOUNDARY, identity["validationBoundary"])
        self.assertEqual(replay.PROVENANCE, identity["provenance"])
        for name, data in self.inputs.items():
            for target in replay.ALIASES:
                (self.source / target).unlink(missing_ok=True)
            (self.source / name).write_bytes(data + b"\n")
            self.assertIsNone(replay.resourceAliasPlan(self.source))
            self.assertFalse(preparation.preparationRequired(self.source))
            (self.source / name).write_bytes(data)

    def testPortableReplayIsIdempotentAndRejectsChangedOriginals(self):
        result = self.prepare()
        evidence = self.source / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(result))
        for target in replay.ALIASES:
            (self.source / target).unlink()
        self.assertTrue(replay.prepareResourceAliases(self.source, evidence))
        self.assertFalse(replay.prepareResourceAliases(self.source, evidence))
        for target in replay.ALIASES:
            (self.source / target).unlink()
        (self.source / "creatures.qrc").write_bytes(b"changed manifest")
        with self.assertRaisesRegex(ValueError, "original inputs"):
            replay.prepareResourceAliases(self.source, evidence)
        self.assertFalse(any((self.source / target).exists() for target in replay.ALIASES))

    def testConflictingAndSymlinkedOutputsArePreserved(self):
        target = self.source / sorted(replay.ALIASES)[0]
        target.write_bytes(b"user bytes")
        self.assertIsNone(replay.resourceAliasPlan(self.source))
        self.assertEqual("not-required", self.prepare()["status"])
        self.assertEqual(b"user bytes", target.read_bytes())
        target.unlink()
        protected = self.root / "protected"
        protected.write_bytes(b"preserve")
        target.symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.prepare()
        self.assertEqual(b"preserve", protected.read_bytes())

    @unittest.skipUnless(shutil.which("rcc"), "Qt rcc is needed for the manifest regression")
    def testOriginalManifestFailsBeforeAndCompilesAfter(self):
        command = [shutil.which("rcc"), "creatures.qrc", "-o", str(self.root / "qrc_creatures.cpp")]
        before = subprocess.run(command, cwd=self.source, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(0, before.returncode)
        self.assertIn("time.txt", before.stderr)
        self.prepare()
        after = subprocess.run(command, cwd=self.source, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, after.returncode, after.stderr)


if __name__ == "__main__":
    unittest.main()
