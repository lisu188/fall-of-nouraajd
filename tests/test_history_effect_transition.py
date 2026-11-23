"""Check portable proofs for the effect and movement transitions in #280–#281."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_effect_transition as effect
from scripts.recovery_readme import snapshotDocumentation


class HistoricalEffectTransitionTest(unittest.TestCase):
    def testPortableEvidenceForEachReviewedRevision(self):
        base = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in effect.COMMITS:
            with self.subTest(commit=commit):
                directory = base / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_effect_transition.py", snapshotDocumentation(report, directory))
                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["effectTransition"]["files"].clear()
                with self.assertRaises(ValueError):
                    effect.validate(commit, preparation)
