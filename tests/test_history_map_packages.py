"""Check build and startup evidence for reconstructed map package paths."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_map_packages as packages
from scripts.recovery_readme import snapshotDocumentation


class HistoricalMapPackagesTest(unittest.TestCase):
    def testMapPackageRevisionsStartWithTheAuthoredResourcePaths(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in packages.COMMITS:
            with self.subTest(commit=commit):
                directory = evidence / commit
                report = json.loads((directory / "verification.json").read_bytes())
                self.assertIn("recovery/prepare_map_packages.py", snapshotDocumentation(report, directory))
                log = (directory / "startup.log").read_text()
                self.assertIn('Loaded configuration: "maps/map1/map.json"', log)
                if commit != packages.COMMITS[0]:
                    self.assertIn('Loaded configuration: "maps/map1/config.json"', log)

                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["mapPackages"]["files"].clear()
                with self.assertRaises(ValueError):
                    packages.validate(commit, preparation)
