"""Check portable build and startup evidence for the fight system revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_fight_system as fight
from scripts.recovery_readme import snapshotDocumentation


class HistoricalFightSystemTest(unittest.TestCase):
    def testReplayedSnapshotsBuildAndEquipThePlayer(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in fight.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_fight_system.py", snapshotDocumentation(report, directory))
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertIn('"Assasin" equipped "Dagger"', (directory / "startup.log").read_text())

                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["fightSystem"]["files"].clear()
                with self.assertRaises(ValueError):
                    fight.validate(commit, preparation)
