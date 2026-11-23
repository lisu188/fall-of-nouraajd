"""Check portable evidence for the first authored Python effect subclasses."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_python_effects as effects
from scripts.recovery_readme import snapshotDocumentation


class HistoricalPythonEffectsTest(unittest.TestCase):
    def testRevisionsStartTheGameWithTheEffectPackage(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in effects.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_python_effects.py", snapshotDocumentation(report, directory))
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertIn('Loaded configuration: "config/effects.json"', (directory / "startup.log").read_text())

                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["pythonEffects"]["files"].clear()
                with self.assertRaises(ValueError):
                    effects.validate(commit, preparation)
