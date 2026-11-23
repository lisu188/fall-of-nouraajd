"""Check that split-project verification retains the reviewed shutdown boundary."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import history_prepare_python_shutdown as shutdown
from scripts.recovery_readme import snapshotDocumentation


ROOT = Path(__file__).resolve().parents[1]


class HistoricalPythonShutdownTest(unittest.TestCase):
    def testRejectChangedEngineBeforeWriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / shutdown.TARGET
            target.parent.mkdir(parents=True)
            target.write_bytes(b"other source")
            with self.assertRaisesRegex(ValueError, "input differs"):
                shutdown.apply(root, shutdown.COMMITS[0])
            self.assertEqual(target.read_bytes(), b"other source")

    def testPortableInstructionsBuildTheDependencyAndRunFromRoot(self):
        directory = ROOT / "recovery" / "evidence" / shutdown.COMMITS[0]
        report = json.loads((directory / "verification.json").read_bytes())
        attachments = snapshotDocumentation(report, directory)
        self.assertIn(b"(cd python && qmake", attachments["README.md"])
        self.assertIn(b"./core/RecoveryGame", attachments["README.md"])
        self.assertIn("recovery/prepare_python_shutdown.py", attachments)
        altered = copy.deepcopy(report["sourcePreparation"])
        altered["identity"]["pythonShutdown"]["inputSha256"] = shutdown.OUTPUT
        with self.assertRaisesRegex(ValueError, "exact source fingerprints"):
            shutdown.validate(shutdown.COMMITS[0], altered)
