# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import history_prepare_legacy_timing as timing


class LegacyTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nouraajd-legacy-timing-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        fixture = Path(__file__).parent / "fixtures/history-timing-128"
        shutil.copytree(fixture, self.root)
        self.evidence = Path(self.temp.name) / "evidence"
        self.evidence.mkdir()

    def preparation(self):
        plan = timing.legacyTimingPlan(self.root)
        outputs = [
            {"path": name, "before": None, "after": {"kind": "file", "sha256": sha}}
            for name, sha in plan["sha256"].items()
        ]
        return {
            "status": "success",
            "identity": {"legacyTimingResources": {k: v for k, v in plan.items() if k != "data"}, "outputs": outputs},
            "outputs": outputs,
        }

    def writeEvidence(self, data):
        (self.evidence / "source-preparation.json").write_text(json.dumps(data))

    def testPinnedOriginalStateCopiesExactRenamedBytes(self):
        plan = timing.legacyTimingPlan(self.root)
        self.assertEqual(len(plan["paths"]), 3)
        before = {name: (self.root / name).read_bytes() for name in plan["inputs"]}
        self.assertTrue(timing.writeTimingResources(self.root, plan["data"]))
        self.assertEqual(sum(len(value) for value in plan["data"].values()), 21)
        for name in plan["paths"]:
            self.assertEqual((self.root / name).read_bytes(), (self.root / (name[:-3] + "json")).read_bytes())
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in before})
        self.assertFalse(timing.writeTimingResources(self.root, plan["data"]))

    def testOriginalProviderAndManifestBothRetainOldNames(self):
        manifest = (self.root / "creatures.qrc").read_text()
        provider = (self.root / "animation/animationprovider.cpp").read_text()
        self.assertIn('path+"time.txt"', provider)
        for name in timing.legacyTimingPlan(self.root)["paths"]:
            self.assertIn("<file>" + name + "</file>", manifest)

    def testAuthoredNextManifestDoesNotMatch(self):
        path = self.root / "creatures.qrc"
        path.write_bytes(path.read_bytes().replace(b"time.txt", b"time.json"))
        self.assertIsNone(timing.legacyTimingPlan(self.root))

    def testChangedProviderDoesNotMatch(self):
        path = self.root / "animation/animationprovider.cpp"
        path.write_bytes(path.read_bytes().replace(b"time.txt", b"time.json"))
        self.assertIsNone(timing.legacyTimingPlan(self.root))

    def testEarlierStateWithoutRenamedInputsDoesNotMatch(self):
        path = self.root / "images/monsters/pritz/time.json"
        path.rename(path.with_suffix(".txt"))
        self.assertIsNone(timing.legacyTimingPlan(self.root))

    def testChangedRenamedInputFails(self):
        path = self.root / "images/monsters/pritz/time.json"
        path.write_bytes(b"300 0")
        with self.assertRaisesRegex(ValueError, "renamed input differs"):
            timing.legacyTimingPlan(self.root)

    def testExistingLegacyInputIsNotAnOriginalMatch(self):
        (self.root / "images/monsters/pritz/time.txt").write_bytes(b"0 300")
        self.assertIsNone(timing.legacyTimingPlan(self.root))

    def testConflictingOutputRefusesAllWrites(self):
        plan = timing.legacyTimingPlan(self.root)
        path = self.root / "images/monsters/pritzmage/time.txt"
        path.write_bytes(b"unique retained file")
        with self.assertRaisesRegex(ValueError, "already exists"):
            timing.writeTimingResources(self.root, plan["data"])
        self.assertFalse((self.root / "images/monsters/octobogz/time.txt").exists())
        self.assertEqual(path.read_bytes(), b"unique retained file")

    def testOutputOutsideReviewedPathsFails(self):
        data = timing.legacyTimingPlan(self.root)["data"]
        data["../escape"] = b"0 300"
        with self.assertRaisesRegex(ValueError, "output paths differ"):
            timing.writeTimingResources(self.root, data)
        self.assertFalse((self.root.parent / "escape").exists())

    def testSymlinkedOutputFailsWithoutWriting(self):
        plan = timing.legacyTimingPlan(self.root)
        outside = self.root.parent / "outside"
        outside.write_bytes(b"retained")
        (self.root / "images/monsters/pritz/time.txt").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            timing.writeTimingResources(self.root, plan["data"])
        self.assertEqual(outside.read_bytes(), b"retained")
        self.assertFalse((self.root / "images/monsters/octobogz/time.txt").exists())

    def testPortableReplayChecksProofAndIsIdempotent(self):
        self.writeEvidence(self.preparation())
        self.assertTrue(timing.prepareLegacyTiming(self.root, self.evidence))
        self.assertFalse(timing.prepareLegacyTiming(self.root, self.evidence))
        self.assertIsNone(timing.legacyTimingPlan(self.root))

    def testPortableReplayRejectsTamperedIdentityAndOutputProof(self):
        original = self.preparation()
        modified = copy.deepcopy(original)
        modified["identity"]["legacyTimingResources"]["provenance"]["operation"] = "different"
        self.writeEvidence(modified)
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            timing.prepareLegacyTiming(self.root, self.evidence)
        modified = copy.deepcopy(original)
        modified["outputs"][0]["before"] = {"kind": "file", "sha256": "0" * 64}
        self.writeEvidence(modified)
        with self.assertRaisesRegex(ValueError, "output fingerprints"):
            timing.prepareLegacyTiming(self.root, self.evidence)
        self.assertFalse((self.root / "images/monsters/pritz/time.txt").exists())


if __name__ == "__main__":
    unittest.main()
