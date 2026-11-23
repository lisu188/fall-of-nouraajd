"""Validate portable build preparation for the scripted potion revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_potion_movement as movement
from scripts.recovery_readme import snapshotDocumentation


class HistoricalPotionMovementTest(unittest.TestCase):
    def testReplayedSnapshotsStartWithTheirScriptedPotionInventory(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in movement.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_potion_movement.py", snapshotDocumentation(report, directory))
                log = (directory / "startup.log").read_text()
                self.assertIn('Loaded configuration: "config/potions.json"', log)
                self.assertIn('Loaded animation: "images/items/potions/life"', log)
                self.assertIn('Loaded animation: "images/items/potions/mana"', log)

                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["potionMovement"]["files"].clear()
                with self.assertRaises(ValueError):
                    movement.validate(commit, preparation)
