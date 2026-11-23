# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

try:
    from scripts import history_prepare_legacy_tiles as helper
    from scripts import history_source_prep as preparation
except ImportError:
    import history_prepare_legacy_tiles as helper

    preparation = None


class LegacyTileCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        proof_directory = tempfile.TemporaryDirectory()
        self.addCleanup(proof_directory.cleanup)
        self.proof = Path(proof_directory.name)
        (self.root / "src").mkdir()
        (self.root / "config/objects").mkdir(parents=True)
        (self.root / "src/CTile.cpp").write_text('read("config/tiles.json")[name]["path"];\n')
        self.configuration = {
            "GrassTile": {"properties": {"animation": "images/tiles/grass", "canStep": True}},
            "MountainTile": {"properties": {"animation": "images/tiles/mountain", "canStep": False}},
        }
        self.writeConfiguration()
        self.inputs = {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in ("src/CTile.cpp", "config/objects/tiles.json")
        }
        patcher = mock.patch.object(helper, "INPUTS", self.inputs)
        patcher.start()
        self.addCleanup(patcher.stop)
        expected = b'{\n  "GrassTile": {\n    "canStep": true,\n    "path": "images/tiles/grass"\n  },\n  "MountainTile": {\n    "canStep": false,\n    "path": "images/tiles/mountain"\n  }\n}\n'
        output_patcher = mock.patch.object(helper, "OUTPUT_SHA256", hashlib.sha256(expected).hexdigest())
        output_patcher.start()
        self.addCleanup(output_patcher.stop)

    def writeConfiguration(self):
        (self.root / "config/objects/tiles.json").write_text(json.dumps(self.configuration))

    def pinChangedConfiguration(self):
        self.writeConfiguration()
        self.inputs["config/objects/tiles.json"] = hashlib.sha256(
            (self.root / "config/objects/tiles.json").read_bytes()
        ).hexdigest()

    def preparation(self):
        plan = helper.legacyTilePlan(self.root)
        outputs = [{"path": helper.TARGET, "before": None, "after": {"kind": "file", "sha256": plan["sha256"]}}]
        return plan, {
            "status": "success",
            "identity": {
                "legacyTileConfiguration": {key: value for key, value in plan.items() if key != "data"},
                "outputs": outputs,
            },
            "outputs": outputs,
        }

    def evidence(self):
        plan, proof = self.preparation()
        evidence = self.root / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(proof))
        (evidence / helper.ATTACHMENT).write_bytes(plan["data"])
        return evidence, proof

    def testOriginalLegacyLookupFailsThenDerivedConfigurationSuppliesImageAndPassability(self):
        original = {name: (self.root / name).read_bytes() for name in self.inputs}
        target = self.root / helper.TARGET
        with self.assertRaises(FileNotFoundError):
            target.read_bytes()
        plan = helper.legacyTilePlan(self.root)
        self.assertTrue(helper.writeConfiguration(self.root, plan["data"]))
        self.assertEqual(
            json.loads(target.read_bytes()),
            {
                "GrassTile": {"path": "images/tiles/grass", "canStep": True},
                "MountainTile": {"path": "images/tiles/mountain", "canStep": False},
            },
        )
        self.assertFalse(helper.writeConfiguration(self.root, plan["data"]))
        for name, data in original.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def testBuildPreparationRecordsTheNewConfigurationAndPreservesOriginalInputs(self):
        original = {name: (self.root / name).read_bytes() for name in self.inputs}
        self.assertTrue(preparation.preparationRequired(self.root))
        self.assertEqual([], preparation.preparationArguments(self.root))
        result = preparation.prepareSources(self.root, self.proof, {}, {}, mock.Mock())
        self.assertEqual("success", result["status"])
        self.assertEqual(["legacyTileConfiguration"], [step["name"] for step in result["steps"]])
        self.assertEqual(helper.INPUTS, result["identity"]["legacyTileConfiguration"]["inputs"])
        self.assertEqual(result["outputs"], result["identity"]["outputs"])
        self.assertEqual([helper.TARGET], [entry["path"] for entry in result["outputs"]])
        self.assertIsNone(result["outputs"][0]["before"])
        self.assertEqual(helper.OUTPUT_SHA256, result["outputs"][0]["after"]["sha256"])
        for name, data in original.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def testDerivedConfigurationAndOriginalGeneratorOutputsShareOnePreparationProof(self):
        (self.root / "preprocessor.py").write_text("# original generator fixture\n")
        (self.root / "classes.json").write_text("{}\n")

        def run(command, cwd, environment, timeout, log):
            if command[1:] == ["--version"]:
                log.write_text("Python 2.7.18\n")
            else:
                (cwd / "gen").mkdir()
                (cwd / "gen/prop.h").write_text("// generated original properties\n")
                log.write_text("original generator fixture completed\n")
            return {"command": command, "returnCode": 0, "timedOut": False, "log": str(log)}

        result = preparation.prepareSources(
            self.root,
            self.proof,
            {"pythonAbi": "2.7", "environment": {"PYTHONHOME": "/locked/python/2.7.18"}},
            {},
            run,
        )
        self.assertEqual("success", result["status"], result)
        self.assertEqual(
            ["legacyTileConfiguration", "interpreter", "generator"], [step["name"] for step in result["steps"]]
        )
        self.assertEqual({helper.TARGET, "gen/prop.h"}, {entry["path"] for entry in result["outputs"]})
        self.assertEqual(result["outputs"], result["identity"]["outputs"])

    def testChangedOriginalInputDoesNotSelectCompatibility(self):
        (self.root / "src/CTile.cpp").write_text("changed historical loader")
        self.assertIsNone(helper.legacyTilePlan(self.root))
        self.assertFalse((self.root / helper.TARGET).exists())

    def testSchemaAndBooleanPassabilityAreStrict(self):
        self.configuration["GrassTile"]["properties"]["canStep"] = 1
        self.pinChangedConfiguration()
        with self.assertRaisesRegex(ValueError, "types differ"):
            helper.legacyTilePlan(self.root)
        self.configuration["GrassTile"]["properties"]["canStep"] = True
        self.configuration["GrassTile"]["properties"]["future"] = "unsupported"
        self.pinChangedConfiguration()
        with self.assertRaisesRegex(ValueError, "properties differ"):
            helper.legacyTilePlan(self.root)

    def testImagePathEscapeIsRejected(self):
        self.configuration["GrassTile"]["properties"]["animation"] = "images/tiles/../../../outside"
        self.pinChangedConfiguration()
        with self.assertRaisesRegex(ValueError, "original tile image directory"):
            helper.legacyTilePlan(self.root)

    def testSymlinkedOriginalAndOutputAreRejected(self):
        original = self.root / "src/CTile.cpp"
        original.rename(original.with_suffix(".saved"))
        original.symlink_to(original.with_suffix(".saved"))
        with self.assertRaisesRegex(ValueError, "symlink"):
            helper.legacyTilePlan(self.root)
        original.unlink()
        original.with_suffix(".saved").rename(original)
        target = self.root / helper.TARGET
        target.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(ValueError, "symlink"):
            helper.writeConfiguration(self.root, b"{}")

    def testExistingDifferentConfigurationIsPreserved(self):
        target = self.root / helper.TARGET
        target.write_bytes(b"protected existing data")
        with self.assertRaisesRegex(ValueError, "different bytes"):
            helper.writeConfiguration(self.root, helper.legacyTilePlan(self.root)["data"])
        self.assertEqual(target.read_bytes(), b"protected existing data")

    def testPortableReplayRequiresPinnedProofAndIsIdempotent(self):
        evidence, _ = self.evidence()
        self.assertTrue(helper.prepareLegacyTiles(self.root, evidence))
        self.assertFalse(helper.prepareLegacyTiles(self.root, evidence))

    def testTamperedReplayMetadataAndAttachmentAreRejectedWithoutWrites(self):
        evidence, proof = self.evidence()
        proof["identity"]["legacyTileConfiguration"]["provenance"]["inferredCompatibility"] = False
        (evidence / "source-preparation.json").write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            helper.prepareLegacyTiles(self.root, evidence)
        self.assertFalse((self.root / helper.TARGET).exists())
        _, proof = self.preparation()
        (evidence / "source-preparation.json").write_text(json.dumps(proof))
        (evidence / helper.ATTACHMENT).write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "attachment differs"):
            helper.prepareLegacyTiles(self.root, evidence)
        self.assertFalse((self.root / helper.TARGET).exists())

    def testOutputBeforeFingerprintMustRecordNewFile(self):
        evidence, proof = self.evidence()
        proof["outputs"][0]["before"] = {"kind": "file", "sha256": "0" * 64}
        (evidence / "source-preparation.json").write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError, "fingerprints differ"):
            helper.prepareLegacyTiles(self.root, evidence)


if __name__ == "__main__":
    unittest.main()
