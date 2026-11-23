"""Check portable startup and build evidence for the turn callback and factory revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_object_factories as object_factories
from scripts.recovery_readme import snapshotDocumentation


class HistoricalObjectFactoriesTest(unittest.TestCase):
    def testObjectFactoriesRevisionsUseTheReviewedMapShutdownOrder(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in object_factories.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_object_factories.py", snapshotDocumentation(report, directory).keys())
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertEqual(report["smoke"]["returnCode"], 0)

                preparation = copy.deepcopy(report["sourcePreparation"])
                del preparation["identity"]["objectFactories"]["files"]["CGameScene.cpp"]
                with self.assertRaises(ValueError):
                    object_factories.validate(commit, preparation)
