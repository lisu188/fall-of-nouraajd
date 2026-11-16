# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Merged-away header forwarders are build-only and never replace original files."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_prepare_forwarders as replay
from scripts import history_source_prep as preparation
from scripts import verify_history as verify

STATE = "0" * 40


class HistoricalForwarderPreparationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.includers = {"src/main.cpp": b'#include <src/items/armor.h>\nint main() { return 0; }\n'}
        self.targets = {"src/items/item.h": b"class Item {};\nclass Armor : public Item {};\n"}
        for name, data in {**self.includers, **self.targets}.items():
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        pin = lambda files: {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        for mock in (
            patch.object(replay, "INCLUDERS", pin(self.includers)),
            patch.object(replay, "FORWARDERS", {"src/items/armor.h": ("src/items/item.h",)}),
            patch.object(
                replay, "STATES", {STATE: {"targets": pin(self.targets), "forwarders": ["src/items/armor.h"]}}
            ),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def runCommand(self, *args):
        self.fail("Forwarding header preparation cannot execute historical programs")

    def prepare(self):
        return preparation.prepareSources(self.source, self.root / "proof", {}, {}, self.runCommand)

    def testOnlyExactOriginalStatesReceiveForwardersThatIncludeTheMergedHeader(self):
        recipe = {"id": "fixture", "pythonAbi": "none", "qmakeArguments": []}
        self.assertEqual([], verify.selectRecipe([recipe], self.source, "fixture")["qmakeArguments"])
        result = self.prepare()
        self.assertEqual("success", result["status"])
        self.assertEqual(["forwardingHeaders"], [step["name"] for step in result["steps"]])
        self.assertEqual(["src/items/armor.h"], [entry["path"] for entry in result["outputs"]])
        self.assertIsNone(result["outputs"][0]["before"])
        self.assertEqual("forwarding header for a merged-away original header", result["outputs"][0]["purpose"])
        forwarder = (self.source / "src/items/armor.h").read_bytes()
        self.assertIn(b"#include <src/items/item.h>\n", forwarder)
        self.assertEqual(STATE, result["identity"]["forwardingHeaders"]["state"])
        for name, data in {**self.includers, **self.targets}.items():
            self.assertEqual(data, (self.source / name).read_bytes())
        (self.source / "src/items/armor.h").unlink()
        for name, data in {**self.includers, **self.targets}.items():
            (self.source / name).write_bytes(data + b"\n")
            self.assertIsNone(replay.forwarderPlan(self.source))
            self.assertFalse(preparation.preparationRequired(self.source))
            (self.source / name).write_bytes(data)

    def testExistingDifferentHeaderIsPreservedAndSymlinksAreRejected(self):
        target = self.source / "src/items/armor.h"
        target.write_bytes(b"class Armor {};\n")
        self.assertIsNone(replay.forwarderPlan(self.source))
        self.assertEqual("not-required", self.prepare()["status"])
        self.assertEqual(b"class Armor {};\n", target.read_bytes())
        target.unlink()
        protected = self.root / "protected"
        protected.write_bytes(b"preserve")
        target.symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.prepare()
        self.assertEqual(b"preserve", protected.read_bytes())

    def testPortableReplayIsIdempotentAndRejectsChangedOriginals(self):
        result = self.prepare()
        evidence = self.source / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(result))
        (self.source / "src/items/armor.h").unlink()
        self.assertTrue(replay.prepareForwarders(self.source, evidence))
        self.assertFalse(replay.prepareForwarders(self.source, evidence))
        (self.source / "src/items/armor.h").unlink()
        (self.source / "src/main.cpp").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "original inputs"):
            replay.prepareForwarders(self.source, evidence)
        self.assertFalse((self.source / "src/items/armor.h").exists())


if __name__ == "__main__":
    unittest.main()
