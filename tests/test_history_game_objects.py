"""Check portable startup and build evidence for the game-object and item event revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_game_objects as game_objects
from scripts.recovery_readme import snapshotDocumentation


class HistoricalGameObjectsTest(unittest.TestCase):
    def testGameObjectsRevisionsUseTheReviewedMapShutdownOrder(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in game_objects.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_game_objects.py", snapshotDocumentation(report, directory).keys())
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertEqual(report["smoke"]["returnCode"], 0)

                preparation = copy.deepcopy(report["sourcePreparation"])
                del preparation["identity"]["gameObjects"]["files"]["CGameScene.cpp"]
                with self.assertRaises(ValueError):
                    game_objects.validate(commit, preparation)
