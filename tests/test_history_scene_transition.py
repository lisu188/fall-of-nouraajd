"""Check source preparation only applies to the reviewed scene and tile inputs."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts import history_prepare_scene_transition as transition


class HistoricalSceneTransitionTest(unittest.TestCase):
    def testChangedInputsAreRejectedBeforeAnySourceIsWritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for commit, entries in transition.PINS.items():
                with self.subTest(commit=commit):
                    for name in entries:
                        source = root / name
                        source.parent.mkdir(exist_ok=True, parents=True)
                        source.write_bytes(b"modified")
                    with self.assertRaisesRegex(ValueError, "input differs"):
                        transition.apply(root, commit)
                    self.assertTrue(all((root / name).read_bytes() == b"modified" for name in entries))

    def testEvidenceRequiresExactPreparedHashes(self):
        evidence = Path(__file__).resolve().parents[1] / "recovery" / "evidence"
        for commit in transition.PINS:
            with self.subTest(commit=commit):
                report = json.loads((evidence / commit / "source-preparation.json").read_bytes())
                transition.validate(commit, report)
                report["identity"]["sceneTransition"]["files"].clear()
                with self.assertRaisesRegex(ValueError, "pinned original and repaired bytes"):
                    transition.validate(commit, report)
