"""Check the #352 trigger decorator evidence and tamper rejection."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import history_prepare_trigger_decorator as trigger
from scripts.recovery_readme import snapshotDocumentation


class HistoricalTriggerDecoratorTest(unittest.TestCase):
    def testRejectChangedDecorator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / trigger.TARGET
            path.parent.mkdir(parents=True)
            path.write_bytes(trigger.OLD)
            with self.assertRaisesRegex(ValueError, "reviewed original"):
                trigger.apply(root)
            self.assertEqual(path.read_bytes(), trigger.OLD)

    def testPortableEvidenceRequiresTheRepairedFingerprint(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence" / trigger.COMMIT
        report = json.loads((evidence / "verification.json").read_bytes())
        self.assertIn("recovery/prepare_trigger_decorator.py", snapshotDocumentation(report, evidence))
        preparation = copy.deepcopy(report["sourcePreparation"])
        preparation["identity"]["triggerDecorator"]["outputSha256"] = trigger.INPUT
        with self.assertRaisesRegex(ValueError, "pinned proof"):
            trigger.validate(preparation)
