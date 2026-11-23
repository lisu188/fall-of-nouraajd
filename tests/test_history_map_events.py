"""Verify portable evidence for the map-directory and effect transitions."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_map_events as map_events
from scripts.recovery_readme import snapshotDocumentation


class HistoricalMapEventsTest(unittest.TestCase):
    def testRevisionsBuildAndLoadTheMovedMap(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in map_events.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                documentation = snapshotDocumentation(report, directory)
                self.assertIn("recovery/prepare_map_events.py", documentation)
                log = (directory / "startup.log").read_text()
                self.assertIn('Loaded configuration: "maps/1/map.json"', log)
                self.assertIn('"Assasin" equipped "Dagger"', log)
                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["mapEvents"]["files"].clear()
                with self.assertRaises(ValueError):
                    map_events.validate(commit, preparation)
