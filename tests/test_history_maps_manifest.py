import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts import history_prepare_maps_manifest as helper
from scripts import history_source_prep as source_prep

ORIGINAL = b"""<RCC>
    <qresource prefix="/">
        <file>maps/map1/script.py</file>
        <file>maps/map1/map.json</file>
        <file>maps/map1/config.json</file>
        <file>maps/map1/trigger.json</file>
    </qresource>
</RCC>
"""


class MapsManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "maps.qrc").write_bytes(ORIGINAL)
        (self.root / "maps/map1").mkdir(parents=True)
        for name in ["script.py", "map.json", "config.json"]:
            (self.root / "maps/map1" / name).write_text("{}\n")

    def evidence(self):
        plan = helper.mapsManifestPlan(self.root)
        evidence = self.root / "recovery"
        evidence.mkdir(exist_ok=True)
        outputs = [{"path": helper.TARGET, "before": None, "after": {"kind": "file", "sha256": plan["sha256"]}}]
        report = {
            "status": "success",
            "qmakeArguments": helper.ARGUMENTS,
            "identity": {
                "mapsManifest": {key: value for key, value in plan.items() if key != "data"},
                "outputs": outputs,
            },
            "outputs": outputs,
        }
        (evidence / "source-preparation.json").write_text(json.dumps(report))
        (evidence / helper.ATTACHMENT).write_bytes(plan["data"])
        return evidence

    def testOnlyMissingResourceIsRemoved(self):
        plan = helper.mapsManifestPlan(self.root)

        def missing(data):
            return [entry.text for entry in ET.fromstring(data).iter("file") if not (self.root / entry.text).is_file()]

        self.assertEqual(missing(ORIGINAL), ["maps/map1/trigger.json"])
        self.assertEqual(missing(plan["data"]), [])
        self.assertEqual(plan["data"], ORIGINAL.replace(helper.REMOVED_LINE, b""))
        self.assertEqual(hashlib.sha256(plan["data"]).hexdigest(), helper.OUTPUT_SHA256)
        self.assertEqual(
            plan["qmakeArguments"], ["-after", "RESOURCES-=maps.qrc", "RESOURCES+=$$_PRO_FILE_PWD_/recovery_maps.qrc"]
        )

    def testSourcePreparationPinsOnlyNewManifestAndPreservesOriginal(self):
        output = self.root / "preparation-output"
        # Preparation logs belong outside the copied source tree.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = source_prep.prepareSources(
                self.root,
                output,
                {"pythonAbi": "3.4"},
                {},
                lambda *args, **kwargs: self.fail("Manifest generation needs no external generator"),
            )
        self.assertEqual(report["status"], "success")
        self.assertEqual([step["name"] for step in report["steps"]], ["mapsManifest"])
        self.assertEqual(report["qmakeArguments"], helper.ARGUMENTS)
        self.assertEqual(source_prep.preparationArguments(self.root), helper.ARGUMENTS)
        self.assertEqual([entry["path"] for entry in report["outputs"]], [helper.TARGET])
        self.assertIsNone(report["outputs"][0]["before"])
        self.assertEqual((self.root / "maps.qrc").read_bytes(), ORIGINAL)

    def testPresentTriggerNeedsNoCompatibility(self):
        (self.root / helper.ABSENT_INPUTS[0]).write_text("{}")
        self.assertIsNone(helper.mapsManifestPlan(self.root))

    def testDifferentAndAlreadyFixedOriginalsAreNotSelected(self):
        for data in [ORIGINAL + b"\n", ORIGINAL.replace(helper.REMOVED_LINE, b"")]:
            (self.root / "maps.qrc").write_bytes(data)
            self.assertIsNone(helper.mapsManifestPlan(self.root))

    def testReplayIsIdempotentAndPreservesOriginal(self):
        evidence = self.evidence()
        self.assertTrue(helper.prepareMapsManifest(self.root, evidence))
        self.assertFalse(helper.prepareMapsManifest(self.root, evidence))
        self.assertEqual((self.root / "maps.qrc").read_bytes(), ORIGINAL)
        self.assertFalse((self.root / helper.ABSENT_INPUTS[0]).exists())

    def testOutputConflictRejected(self):
        evidence = self.evidence()
        (self.root / helper.TARGET).write_text("different")
        with self.assertRaisesRegex(ValueError, "different bytes"):
            helper.prepareMapsManifest(self.root, evidence)

    def testSymlinkedInputOutputAndAbsentInputRejected(self):
        evidence = self.evidence()
        outside = self.root / "other"
        outside.write_text("private")
        target = self.root / helper.TARGET
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            helper.prepareMapsManifest(self.root, evidence)
        target.unlink()
        absent = self.root / helper.ABSENT_INPUTS[0]
        absent.symlink_to(self.root / "does-not-exist")
        with self.assertRaisesRegex(ValueError, "symlink"):
            helper.mapsManifestPlan(self.root)
        absent.unlink()
        original = self.root / "maps.qrc"
        original.unlink()
        original.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            helper.mapsManifestPlan(self.root)

    def testTamperedAttachmentEvenWithSelfConsistentHashesRejected(self):
        evidence = self.evidence()
        data = b"forged"
        p = evidence / "source-preparation.json"
        report = json.loads(p.read_text())
        sha = hashlib.sha256(data).hexdigest()
        report["identity"]["mapsManifest"]["sha256"] = sha
        report["outputs"][0]["after"]["sha256"] = sha
        report["identity"]["outputs"] = report["outputs"]
        p.write_text(json.dumps(report))
        (evidence / helper.ATTACHMENT).write_bytes(data)
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            helper.prepareMapsManifest(self.root, evidence)

    def testChangedAbsenceStateRejectedDuringReplay(self):
        evidence = self.evidence()
        (self.root / helper.ABSENT_INPUTS[0]).write_text("{}")
        with self.assertRaisesRegex(ValueError, "absence state"):
            helper.prepareMapsManifest(self.root, evidence)

    def testForgedArgumentsAndOutputFingerprintsRejected(self):
        evidence = self.evidence()
        p = evidence / "source-preparation.json"
        original = p.read_text()
        report = json.loads(original)
        report["qmakeArguments"] = helper.ARGUMENTS[1:]
        p.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            helper.prepareMapsManifest(self.root, evidence)
        report = json.loads(original)
        report["identity"]["outputs"] = []
        p.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "fingerprints differ"):
            helper.prepareMapsManifest(self.root, evidence)


if __name__ == "__main__":
    unittest.main()
