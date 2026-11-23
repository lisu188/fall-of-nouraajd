"""Check that the authored #366 source and build-copy repair remain distinct."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_map_position as position
from scripts.recovery_readme import snapshotDocumentation


class HistoricalMapPositionTest(unittest.TestCase):
    def testPortablePreparationRequiresTheReviewedOutput(self):
        directory = Path(__file__).resolve().parents[1] / "recovery" / "evidence" / position.COMMIT
        report = json.loads((directory / "verification.json").read_bytes())
        preparation = report["sourcePreparation"]
        self.assertIn("recovery/prepare_map_position.py", snapshotDocumentation(report, directory))
        altered = copy.deepcopy(preparation)
        edited = next(row for row in altered["outputs"] if row["path"] == position.TARGET)
        edited["after"]["sha256"] = position.INPUT
        with self.assertRaisesRegex(ValueError, "pinned proof"):
            position.validate(altered)
