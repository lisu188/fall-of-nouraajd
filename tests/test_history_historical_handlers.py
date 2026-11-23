"""Check portable startup and build evidence for the handler, folder and configuration revisions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_historical_handlers as historical_handlers
from scripts.recovery_readme import snapshotDocumentation


class HistoricalHistoricalHandlersTest(unittest.TestCase):
    def testHistoricalHandlersRevisionsUseTheReviewedMapShutdownOrder(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in historical_handlers.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_historical_handlers.py", snapshotDocumentation(report, directory).keys())
                self.assertTrue(report["smoke"]["startup"]["checks"]["player"])
                self.assertEqual(report["smoke"]["returnCode"], 0)

                preparation = copy.deepcopy(report["sourcePreparation"])
                files = preparation["identity"]["historicalHandlers"]["files"]
                del files[next(iter(files))]
                with self.assertRaises(ValueError):
                    historical_handlers.validate(commit, preparation)
