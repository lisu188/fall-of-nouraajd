"""Regression coverage for the pre-#183 build-copy compatibility."""

from pathlib import Path
import tempfile
import unittest

from scripts import history_prepare_merged_headers as preparation

ROOT = Path(__file__).resolve().parents[1]


class HistoricalMergedHeadersTest(unittest.TestCase):
    def testGeneratedFilesFollowRevisionBoundaries(self):
        companions = preparation.donorFiles(ROOT)
        first, second, third = [preparation.generatedOutputs(commit, companions) for commit in preparation.COMMITS]
        self.assertIn(b"interaction.h", first["src/buildings/cave.h"])
        self.assertNotIn("src/stats/damage.h", first)
        self.assertEqual(second["src/stats/damage.h"], b'#include "stats.h"\n')
        self.assertEqual(third, {"lib/json/" + name: data for name, data in companions.items()})
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaisesRegex(ValueError, "Unknown"):
                preparation.outputs(Path(work), preparation.DONOR, companions)
            with self.assertRaisesRegex(ValueError, "input differs"):
                preparation.outputs(Path(work), preparation.COMMITS[0], companions)
            companions[preparation.COMPANIONS[0]] = b"tampered"
            with self.assertRaisesRegex(ValueError, "companions differ"):
                preparation.outputs(Path(work), preparation.COMMITS[0], companions)

    def testExistingFilePreventsPreparation(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            existing = root / "present.h"
            existing.write_bytes(b"original")
            with self.assertRaisesRegex(ValueError, "already exists"):
                preparation.apply(root, {"absent.h": b"generated", "present.h": b"replacement"})
            self.assertFalse((root / "absent.h").exists())
            self.assertEqual(existing.read_bytes(), b"original")
