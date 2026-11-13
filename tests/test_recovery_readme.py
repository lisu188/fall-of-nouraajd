# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.recovery_readme import snapshotDocumentation
from scripts.verify_history import REQUIRED_CHECKS, VerificationError
from tests.test_history_smoke import pngBytes


class RecoveryReadmeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.evidence = Path(temporary.name)
        startup = {
            "schemaVersion": 1,
            "status": "ready",
            "checks": {name: True for name in REQUIRED_CHECKS},
            "frame": {
                "path": "/original/build/startup.png",
                "width": 2,
                "height": 1,
                "sha256": hashlib.sha256(pngBytes()).hexdigest(),
            },
        }
        self.report = {
            "sourceCommit": "a" * 40,
            "sourceTree": "b" * 40,
            "status": "success",
            "restoration": {
                "sourceCommit": "a" * 40,
                "sourceTree": "b" * 40,
                "status": "complete",
                "unresolved": [],
                "restoredFilesFingerprint": "c" * 64,
                "restored": [{"path": "map.cpp", "method": "reconstruction", "provenance": "Header-based recovery"}],
            },
            "configure": {"command": ["qmake", "/original/Game.pro"], "returnCode": 0, "timedOut": False},
            "build": {"command": ["make", "-j8"], "returnCode": 0, "timedOut": False},
            "smoke": {
                "command": ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", "Game"],
                "status": "success",
                "returnCode": 0,
                "timedOut": False,
                "startup": startup,
            },
            "toolchain": {
                "qmakeCommand": {"version": "QMake version 3.1\nUsing Qt 5.15"},
                "compilerCommand": {"version": "g++ 15.2"},
            },
            "recipe": {"pythonAbi": "none"},
        }
        (self.evidence / "startup.json").write_text(json.dumps(startup))
        (self.evidence / "startup.png").write_bytes(pngBytes())

    def testVerifiedSnapshotGetsActualImageAndPortableLinks(self):
        files = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual({"README.md", "recovery/startup.png", "recovery/verification.json"}, set(files))
        self.assertIn(b"![Actual startup", files["README.md"])
        self.assertIn(b"qmake Game.pro", files["README.md"])
        self.assertIn(b"Header-based recovery", files["README.md"])
        self.assertEqual(pngBytes(), files["recovery/startup.png"])
        metadata = json.loads(files["recovery/verification.json"])
        self.assertEqual("startup.png", metadata["smoke"]["startup"]["frame"]["path"])
        self.assertEqual("/original/build/startup.png", self.report["smoke"]["startup"]["frame"]["path"])

    def testUnverifiedOrIncompleteRecoveryCannotAttachDocumentation(self):
        for modification in ("status", "restore", "configure", "build", "smoke", "fingerprint"):
            with self.subTest(modification=modification):
                report = copy.deepcopy(self.report)
                if modification == "status":
                    report["status"] = "blocked"
                elif modification == "restore":
                    report["restoration"]["unresolved"] = [{"path": "map.cpp"}]
                elif modification == "fingerprint":
                    report["restoration"].pop("restoredFilesFingerprint")
                else:
                    report[modification]["returnCode"] = 2
                with self.assertRaises(VerificationError):
                    snapshotDocumentation(report, self.evidence)

    def testMissingInvalidOrMismatchedFrameFails(self):
        for image in (b"", b"fake screenshot", pngBytes()[:-5]):
            with self.subTest(image=image):
                (self.evidence / "startup.png").write_bytes(image)
                with self.assertRaises(VerificationError):
                    snapshotDocumentation(self.report, self.evidence)

    def testReadinessReportMustBelongToTheSameRun(self):
        (self.evidence / "startup.json").write_text("{}")
        with self.assertRaisesRegex(VerificationError, "differs"):
            snapshotDocumentation(self.report, self.evidence)

    def testScreenshotBytesMustMatchTheCapturedFingerprint(self):
        self.report["smoke"]["startup"]["frame"]["sha256"] = "d" * 64
        (self.evidence / "startup.json").write_text(json.dumps(self.report["smoke"]["startup"]))
        with self.assertRaisesRegex(VerificationError, "actual verified image bytes"):
            snapshotDocumentation(self.report, self.evidence)

    def testVisibleDesktopStartupCannotBePublishedAsVerified(self):
        self.report["smoke"]["command"] = ["Game"]
        with self.assertRaisesRegex(VerificationError, "Xvfb"):
            snapshotDocumentation(self.report, self.evidence)


if __name__ == "__main__":
    unittest.main()
