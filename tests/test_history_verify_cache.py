# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""The per-fingerprint success cache must never turn moved artifacts into startup failures."""

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from scripts import verify_history as verify


def pngBytes():
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    return (
        verify.PNG_SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\xff\0\xff\0\xff"))
        + chunk(b"IEND", b"")
    )


class ReusableCachedResultTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.artifacts = self.root / "snapshot/smoke"
        self.artifacts.mkdir(parents=True)
        self.cache = self.root / "results/fingerprint.json"
        self.cache.parent.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def writeCache(self, report: Path, status: str = "success") -> None:
        self.cache.write_text(
            json.dumps({"status": status, "smoke": {"startupReport": str(report)}, "artifactDir": str(self.artifacts)})
        )

    def writeReport(self, checks: dict) -> Path:
        frame = self.artifacts / "startup.png"
        frame.write_bytes(pngBytes())
        report = self.artifacts / "startup.json"
        report.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "status": "ready",
                    "mode": "game",
                    "checks": checks,
                    "frame": {
                        "path": str(frame),
                        "width": 2,
                        "height": 1,
                        "sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
                    },
                }
            )
        )
        return report

    def testAbsentOrUnsuccessfulEntriesAreMisses(self):
        self.assertIsNone(verify.reusableCachedResult(self.cache, "game"))
        self.writeCache(self.writeReport({name: True for name in verify.REQUIRED_CHECKS}), status="failed")
        self.assertIsNone(verify.reusableCachedResult(self.cache, "game"))

    def testMovedWorkDirectoryIsAMissNotAStartupFailure(self):
        self.writeCache(self.root / "moved-away/smoke/startup.json")
        self.assertIsNone(verify.reusableCachedResult(self.cache, "game"))

    def testPresentValidArtifactsAreReused(self):
        self.writeCache(self.writeReport({name: True for name in verify.REQUIRED_CHECKS}))
        self.assertEqual("success", verify.reusableCachedResult(self.cache, "game")["status"])

    def testPresentInvalidArtifactsStillFail(self):
        self.writeCache(self.writeReport({"map": True}))
        with self.assertRaises(verify.VerificationError):
            verify.reusableCachedResult(self.cache, "game")


if __name__ == "__main__":
    unittest.main()
