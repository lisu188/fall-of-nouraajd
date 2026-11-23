"""Check the pinned #275 sparse map transition repairs."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_sparse_map_transition as panel
from scripts.recovery_readme import snapshotDocumentation


class HistoricalPanelTransitionTest(unittest.TestCase):
    def testPortableProofRequiresBothPreparedFiles(self):
        directory = Path(__file__).resolve().parents[1] / "recovery" / "evidence" / panel.COMMIT
        report = json.loads((directory / "verification.json").read_bytes())
        self.assertIn("recovery/prepare_sparse_map_transition.py", snapshotDocumentation(report, directory))
        changed = copy.deepcopy(report["sourcePreparation"])
        changed["outputs"] = [row for row in changed["outputs"] if row["path"] != "game/CScriptEngine.cpp"]
        with self.assertRaises(ValueError):
            panel.validate(changed)
