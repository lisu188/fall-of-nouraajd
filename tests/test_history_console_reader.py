"""Check the pinned verification boundary for the #204 console reader."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_console_reader as console
from scripts.recovery_readme import snapshotDocumentation

ROOT = Path(__file__).resolve().parents[1]


class HistoryConsoleReaderTest(unittest.TestCase):
    def testConsoleSourceAndEvidenceArePinned(self):
        with self.assertRaisesRegex(ValueError, "reviewed #204 original"):
            console.prepare(console.ORIGINAL)
        evidence = ROOT / "recovery" / "evidence" / console.COMMIT
        report = json.loads((evidence / "verification.json").read_bytes())
        self.assertIn("recovery/prepare_console_reader.py", snapshotDocumentation(report, evidence))
        preparation = copy.deepcopy(report["sourcePreparation"])
        preparation["identity"]["consoleReader"]["outputSha256"] = console.INPUT_SHA256
        with self.assertRaisesRegex(ValueError, "pinned source fingerprints"):
            console.validate(preparation)
