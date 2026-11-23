"""Check portable startup and build evidence for the visitor callback revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_visitor_callbacks as callbacks
from scripts.recovery_readme import snapshotDocumentation


class HistoricalVisitorCallbacksTest(unittest.TestCase):
    def testVisitorRevisionsUseTheReviewedMapShutdownOrder(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in callbacks.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_visitor_callbacks.py", snapshotDocumentation(report, directory))
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertEqual(report["smoke"]["returnCode"], 0)

                preparation = copy.deepcopy(report["sourcePreparation"])
                del preparation["identity"]["visitorCallbacks"]["files"]["CGameScene.cpp"]
                with self.assertRaises(ValueError):
                    callbacks.validate(commit, preparation)
