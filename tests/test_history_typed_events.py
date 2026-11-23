"""Check portable startup and build evidence for the typed event and movement revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_typed_events as typed_events
from scripts.recovery_readme import snapshotDocumentation


class HistoricalTypedEventsTest(unittest.TestCase):
    def testTypedEventsRevisionsUseTheReviewedMapShutdownOrder(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in typed_events.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_typed_events.py", snapshotDocumentation(report, directory).keys())
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertEqual(report["smoke"]["returnCode"], 0)

                preparation = copy.deepcopy(report["sourcePreparation"])
                del preparation["identity"]["typedEvents"]["files"]["CGameScene.cpp"]
                with self.assertRaises(ValueError):
                    typed_events.validate(commit, preparation)
