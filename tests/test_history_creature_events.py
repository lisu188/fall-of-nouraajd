"""Validate portable build evidence for the creature-aware event revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_creature_events as events
from scripts.recovery_readme import snapshotDocumentation


class HistoricalCreatureEventsTest(unittest.TestCase):
    def testReplayedSnapshotsBuildAndStartWithTheCreatureBindings(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in events.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_creature_events.py", snapshotDocumentation(report, directory))
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertIn('"Assasin" equipped "Dagger"', (directory / "startup.log").read_text())

                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["creatureEvents"]["files"].clear()
                with self.assertRaises(ValueError):
                    events.validate(commit, preparation)
