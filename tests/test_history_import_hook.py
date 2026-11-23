"""Check portable evidence for the Python 3.4 import-hook transition."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_import_hook as import_hook
from scripts.recovery_readme import snapshotDocumentation


class HistoricalImportHookTest(unittest.TestCase):
    def testPortableEvidenceIncludesTheAuthoredRandomDraws(self):
        directory = self.evidenceDirectory(import_hook.COMMITS[0])
        draws = [int(line) for line in (directory / "startup.log").read_text().splitlines() if line.isdecimal()]
        self.assertEqual(len(draws), 1000)
        self.assertTrue(all(0 <= draw <= 100 for draw in draws))

    def testPortableBuildPreparationFollowsEachProjectLayout(self):
        for index, commit in enumerate(import_hook.COMMITS):
            with self.subTest(commit=commit):
                directory = self.evidenceDirectory(commit)
                report = json.loads((directory / "verification.json").read_bytes())
                documentation = snapshotDocumentation(report, directory)
                self.assertIn("recovery/prepare_import_hook.py", documentation)
                self.assertEqual(report["recipe"]["pythonAbi"], "3.4")
                if index == 1:
                    self.assertEqual(report["runtimeWorkingDirectory"], "game")
                    readme = documentation["README.md"].decode()
                    self.assertIn("cd python && qmake python.pro", readme)
                    self.assertIn("cd game\n", readme)
                    self.assertNotIn("cd resources &&", readme)

                preparation = copy.deepcopy(report["sourcePreparation"])
                preparation["identity"]["importHook"]["files"].clear()
                with self.assertRaises(ValueError):
                    import_hook.validate(commit, preparation)

    def evidenceDirectory(self, commit):
        return Path(__file__).resolve().parents[1] / "recovery" / "evidence" / commit
