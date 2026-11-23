"""Check portable proofs for the two Python ownership layouts used in #277–#279."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_panel_refresh_transition as panel
from scripts.recovery_readme import snapshotDocumentation


class HistoricalPanelRefreshTransitionTest(unittest.TestCase):
    def testPortableEvidenceForEachReviewedRevision(self):
        base = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in panel.PROFILES:
            with self.subTest(commit=commit):
                directory = base / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_panel_refresh_transition.py", snapshotDocumentation(report, directory))
                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["panelRefreshTransition"]["files"].clear()
                with self.assertRaises(ValueError):
                    panel.validate(commit, preparation)
