# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import history_prepare_pathfinder_cache as cache
from scripts import history_runtime_configs as configs
from scripts.recovery_readme import snapshotDocumentation, VerificationError

EVIDENCE = Path(__file__).resolve().parents[1] / "recovery/evidence"


class HistoryRuntimeTransitionTest(unittest.TestCase):
    def testMissingCacheFromImmediateChild(self):
        directory = EVIDENCE / cache.COMMIT
        preparation = json.loads((directory / "source-preparation.json").read_bytes())
        cache.validate(preparation)
        data = (directory / cache.ATTACHMENT).read_bytes()
        self.assertEqual(configs.digest(data), cache.SHA256)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "project or header"):
                cache.apply(root, data)
            self.assertFalse((root / cache.TARGET).exists())
        altered = copy.deepcopy(preparation)
        altered["identity"]["childPathfinderCache"]["donorCommit"] = cache.COMMIT
        with self.assertRaises(ValueError):
            cache.validate(altered)

    def testRuntimePreparationMustMatchRecordedTransition(self):
        for commit in configs.INPUT_PINS:
            with self.subTest(commit=commit):
                evidence = EVIDENCE / commit
                report = json.loads((evidence / "verification.json").read_bytes())
                report["verifiedFromCommit"] = commit
                docs = snapshotDocumentation(report, evidence)
                self.assertEqual(docs["recovery/prepare_runtime_configs.py"], Path(configs.__file__).read_bytes())
                del report["runtimeConfiguration"]["outputs"]["config/object.json"]
                with self.assertRaisesRegex(VerificationError, "Runtime configuration"):
                    snapshotDocumentation(report, evidence)

    def testExistingConfigurationSurvivesFailedReplay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config").mkdir()
            original = root / "config/tiles.json"
            original.write_bytes(b"existing")
            outputs = {"config/object.json": b"{}", "config/tiles.json": b"replacement"}
            with self.assertRaisesRegex(ValueError, "replace existing"):
                configs.writeOutputs(root, outputs)
            self.assertEqual(original.read_bytes(), b"existing")
            self.assertFalse((root / "config/object.json").exists())
            outputs["config/tiles.json"] = b"existing"
            configs.writeOutputs(root, outputs)
            configs.writeOutputs(root, outputs)
            self.assertEqual((root / "config/object.json").read_bytes(), b"{}")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                configs.writeOutputs(root, {"../other": b"outside"})
