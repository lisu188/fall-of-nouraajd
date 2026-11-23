"""Check portable evidence for the first resource-backed Python script loader."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_script_loader as loader
from scripts.recovery_readme import snapshotDocumentation


class HistoricalScriptLoaderTest(unittest.TestCase):
    def testPortableEvidenceRetainsTheAuthoredScriptStartup(self):
        directory = Path(__file__).resolve().parents[1] / "recovery" / "evidence" / loader.COMMITS[0]
        report = json.loads((directory / "verification.json").read_bytes())
        documentation = snapshotDocumentation(report, directory)
        self.assertIn("recovery/prepare_script_loader.py", documentation)
        self.assertIn("I AM BUNDLE", (directory / "startup.log").read_text())

        preparation = copy.deepcopy(report["sourcePreparation"])
        preparation["identity"]["scriptLoader"]["files"].clear()
        with self.assertRaises(ValueError):
            loader.validate(report["sourceCommit"], preparation)
