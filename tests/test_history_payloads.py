# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""The committed recovery payloads must match the SHA-256 pins that reference them."""

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

RECOVERY_ROOT = Path(__file__).resolve().parents[1] / "recovery"


def payloadPins():
    pins = {}
    overrides = RECOVERY_ROOT / "overrides.json"
    if overrides.is_file():
        for entry in json.loads(overrides.read_text(encoding="utf-8")).get("entries", []):
            if entry.get("source"):
                pins.setdefault(entry["source"], set()).add(entry["sha256"])
    for catalog in sorted((RECOVERY_ROOT / "upstream").rglob("catalog.json")):
        for entry in json.loads(catalog.read_text(encoding="utf-8")).get("entries", []):
            source = (catalog.parent / entry["source"]).relative_to(RECOVERY_ROOT).as_posix()
            pins.setdefault(source, set()).add(entry["sha256"])
    return pins


class HistoryPayloadPinsTest(unittest.TestCase):
    def testEveryPinnedPayloadKeepsItsExactBytes(self):
        pins = payloadPins()
        if not pins:
            self.skipTest("No recovery payloads are committed")
        mismatched = []
        for source, digests in sorted(pins.items()):
            self.assertEqual(1, len(digests), f"Conflicting pins for {source}")
            path = RECOVERY_ROOT / source
            self.assertTrue(path.is_file(), f"Pinned payload is missing: {source}")
            if hashlib.sha256(path.read_bytes()).hexdigest() not in digests:
                mismatched.append(source)
        self.assertEqual([], mismatched, "Payload bytes differ from their pins (line-ending normalization?)")

    def testPayloadDirectoriesAreExemptFromLineEndingNormalization(self):
        for directory in ("upstream", "payloads"):
            probe = f"recovery/{directory}/probe.cpp"
            result = subprocess.run(
                ["git", "-C", str(RECOVERY_ROOT.parent), "check-attr", "text", "--", probe],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                self.skipTest("Git attributes are unavailable outside a Git checkout")
            self.assertTrue(result.stdout.strip().endswith(": text: unset"), result.stdout)


if __name__ == "__main__":
    unittest.main()
