"""Check portable runtime and build preparation for the split Qt resource project."""

import copy
import json
from pathlib import Path
import unittest

from scripts import history_prepare_resources_transition as resources
from scripts.recovery_readme import snapshotDocumentation
from scripts.verify_history import VerificationError


class HistoricalResourcesTransitionTest(unittest.TestCase):
    def testPortableCommandsBuildAndRunTheResourceProject(self):
        directory = Path(__file__).resolve().parents[1] / "recovery" / "evidence" / resources.COMMITS[0]
        report = json.loads((directory / "verification.json").read_bytes())
        documentation = snapshotDocumentation(report, directory)
        self.assertIn("recovery/prepare_resources_transition.py", documentation)
        readme = documentation["README.md"].decode()
        self.assertIn("cd resources && qmake resources.pro", readme)
        self.assertIn("cd resources\n", readme)
        self.assertIn("../game/RecoveryGame", readme)
        self.assertIn("QMAKE_AR=gcc-ar-5 cqs", readme)

        incomplete = copy.deepcopy(report)
        incomplete["dependencies"].pop()
        with self.assertRaisesRegex(VerificationError, "Missing reviewed split-project dependencies"):
            snapshotDocumentation(incomplete, directory)

        preparation = copy.deepcopy(report["sourcePreparation"])
        preparation["identity"]["resourcesTransition"]["files"].clear()
        with self.assertRaises(ValueError):
            resources.validate(report["sourceCommit"], preparation)
