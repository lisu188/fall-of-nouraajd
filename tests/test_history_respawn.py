"""Check portable startup and build evidence for the respawn revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_respawn as respawn
from scripts.recovery_readme import snapshotDocumentation


class HistoricalRespawnTest(unittest.TestCase):
    def testRespawnRevisionsUseTheReviewedMapShutdownOrder(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in respawn.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_respawn.py", snapshotDocumentation(report, directory).keys())
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertEqual(report["smoke"]["returnCode"], 0)

                preparation = copy.deepcopy(report["sourcePreparation"])
                del preparation["identity"]["respawn"]["files"]["CGameScene.cpp"]
                with self.assertRaises(ValueError):
                    respawn.validate(commit, preparation)
