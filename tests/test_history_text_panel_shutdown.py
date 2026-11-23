"""Check the pinned #274 interpreter repairs."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_text_panel_shutdown as panel
from scripts.recovery_readme import snapshotDocumentation


class HistoricalPanelTransitionTest(unittest.TestCase):
    def testPortableProofRequiresThePreparedFile(self):
        directory = Path(__file__).resolve().parents[1] / "recovery" / "evidence" / panel.COMMIT
        report = json.loads((directory / "verification.json").read_bytes())
        self.assertIn("recovery/prepare_text_panel_shutdown.py", snapshotDocumentation(report, directory))
        changed = copy.deepcopy(report["sourcePreparation"])
        changed["outputs"] = [row for row in changed["outputs"] if row["path"] != "game/CScriptEngine.cpp"]
        with self.assertRaises(ValueError):
            panel.validate(changed)
