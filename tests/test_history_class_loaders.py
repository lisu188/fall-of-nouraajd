"""Check the portable evidence for script-defined classes and native resource imports."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_class_loaders as loaders
from scripts.recovery_readme import snapshotDocumentation


class HistoricalClassLoadersTest(unittest.TestCase):
    def testScriptClassRevisionsStartFromTheAuthoredMap(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in loaders.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_class_loaders.py", snapshotDocumentation(report, directory))
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertIn('Loaded configuration: "maps/1/map.json"', (directory / "startup.log").read_text())

                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["classLoaders"]["files"].clear()
                with self.assertRaises(ValueError):
                    loaders.validate(commit, preparation)
