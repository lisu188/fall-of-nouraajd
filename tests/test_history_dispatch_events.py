"""Check portable startup and build evidence for the event handler revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_dispatch_events as dispatch_events
from scripts.recovery_readme import snapshotDocumentation


class HistoricalDispatchEventsTest(unittest.TestCase):
    def testDispatchEventsRevisionsUseTheReviewedMapShutdownOrder(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in dispatch_events.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_dispatch_events.py", snapshotDocumentation(report, directory).keys())
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertEqual(report["smoke"]["returnCode"], 0)

                preparation = copy.deepcopy(report["sourcePreparation"])
                del preparation["identity"]["dispatchEvents"]["files"]["CGameScene.cpp"]
                with self.assertRaises(ValueError):
                    dispatch_events.validate(commit, preparation)
