# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import struct
import unittest
from unittest import mock

from scripts import prepare_history_overrides as proposals
from scripts import recover_history as recovery
from tests import test_history_recovery as fixtures


class HistoryDonorProposalsTest(unittest.TestCase):
    setUp = fixtures.HistoricalRecoveryTest.setUp
    git = fixtures.HistoricalRecoveryTest.git
    blob = fixtures.HistoricalRecoveryTest.blob
    commit = fixtures.HistoricalRecoveryTest.commit
    marker = fixtures.HistoricalRecoveryTest.marker

    def testMatchingHeaderBeatsNearerIncompatibleDonor(self):
        header = b"class Creature { public: void move(); };\n"
        compatible = b"void Creature::move() {}\n"
        older = self.commit({"creature.h": header, "creature.cpp": compatible})
        newer = self.commit(
            {
                "creature.h": b"class Creature { public: void explode(); };\n",
                "creature.cpp": b"void Creature::explode() {}\n",
            },
            [older],
        )
        target = self.commit({"creature.h": header, "creature.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}, [newer])
        # Undamaged donor snapshots enter through explicitly selected commits.
        catalog = recovery.auditHistory(self.repo)
        manifest, report, _ = proposals.proposeOverrides(self.repo, catalog, [older, newer], False)
        entry = next(entry for entry in manifest["entries"] if entry["path"] == "creature.cpp")
        self.assertEqual(self.blob(compatible), entry["blob"])
        self.assertIn("headerMatch=1", entry["provenance"])
        self.assertEqual("proposals-unverified", report["status"])
        output = self.root / "materialized"
        recovery.restoreSnapshot(self.repo, catalog, target, output, manifest)
        self.assertEqual(compatible, (output / "creature.cpp").read_bytes())

    def testExistingAndExactOriginalsNeverProduceDonorOverrides(self):
        exact = self.marker(b"int exact;\n")
        commit = self.commit(
            {
                "exact.cpp" + recovery.MARKER_SUFFIX: exact,
                "intact.cpp": b"int intact;\n",
                "intact.cpp" + recovery.MARKER_SUFFIX: b"f" * 40,
            }
        )
        manifest, report, payloads = proposals.proposeOverrides(self.repo, recovery.auditHistory(self.repo), [], False)
        self.assertEqual([], manifest["entries"])
        self.assertEqual(2, report["exactOrExistingCount"])
        self.assertEqual({}, payloads)

    def testUnsupportedSourceRemainsUnresolvedAndBlocksMaterialization(self):
        commit = self.commit({"missing.cpp" + recovery.MARKER_SUFFIX: b"f" * 40})
        catalog = recovery.auditHistory(self.repo)
        manifest, report, _ = proposals.proposeOverrides(self.repo, catalog, [], False)
        self.assertEqual(1, report["unresolvedCount"])
        self.assertEqual([], manifest["entries"])
        with self.assertRaisesRegex(recovery.RecoveryError, "unresolved required"):
            recovery.restoreSnapshot(self.repo, catalog, commit, self.root / "blocked", manifest)

    def testAssetSemanticPathMatchesFlatAndFramedArtwork(self):
        content = proposals.imagePlaceholder("original donor")
        donor = self.commit({"images/tiles/grass.png": content, "images/other/grass.png": b"unrelated"})
        target = self.commit({"images/tiles/grass/0.png" + recovery.MARKER_SUFFIX: b"f" * 40}, [donor])
        manifest, report, payloads = proposals.proposeOverrides(
            self.repo, recovery.auditHistory(self.repo), [donor], False
        )
        self.assertEqual(self.blob(content), manifest["entries"][0]["blob"])
        self.assertEqual(1, report["donorEntryCount"])
        self.assertEqual({}, payloads)

    def testMissingArtworkProducesDeterministicVisible32PixelPng(self):
        self.commit({"images/unrecoverable.png" + recovery.MARKER_SUFFIX: b"f" * 40})
        catalog = recovery.auditHistory(self.repo)
        first = proposals.proposeOverrides(self.repo, catalog, [], False)
        self.assertEqual(first, proposals.proposeOverrides(self.repo, catalog, [], False))
        manifest, report, payloads = first
        entry = manifest["entries"][0]
        png = payloads[entry["source"]]
        self.assertEqual(b"\x89PNG\r\n\x1a\n", png[:8])
        self.assertEqual((32, 32), struct.unpack("!II", png[16:24]))
        self.assertEqual(hashlib.sha256(png).hexdigest(), entry["sha256"])
        self.assertIn("placeholder", entry["provenance"])
        self.assertEqual(1, report["placeholderEntryCount"])

    def testEarliestCompatibilityImportsWholeDonorDifference(self):
        original = self.commit({"main.cpp": b"int old;\n", "Game.pro" + recovery.MARKER_SUFFIX: b"f" * 40})
        donor = self.commit(
            {"main.cpp": b"int corrected;\n", "Game.pro": b"SOURCES += main.cpp\n", "helper.h": b"void helper();\n"},
            [original],
        )
        catalog = recovery.auditHistory(self.repo)
        with mock.patch.object(proposals, "EARLIEST_ORIGINAL", original), mock.patch.object(
            proposals, "EARLIEST_DONOR", donor
        ):
            manifest, report, _ = proposals.proposeOverrides(self.repo, catalog, [donor])
        entries = {entry["path"]: entry for entry in manifest["entries"]}
        self.assertEqual(3, report["compatibilityEntryCount"])
        self.assertTrue(entries["main.cpp"]["replaceExisting"])
        self.assertTrue(entries["helper.h"]["add"])
        self.assertNotIn("add", entries["Game.pro"])
        output = self.root / "earliest"
        recovery.restoreSnapshot(self.repo, catalog, original, output, manifest)
        self.assertEqual(b"int corrected;\n", (output / "main.cpp").read_bytes())
        self.assertEqual(b"void helper();\n", (output / "helper.h").read_bytes())

    def testSameContextChoosesNearestHistoricalDonor(self):
        header = b"class Map { public: void turn(); };\n"
        old = self.commit({"map.h": header, "map.cpp": b"void Map::turn() { int old = 0; }\n"})
        nearest_content = b"void Map::turn() { int recent = 0; }\n"
        nearest = self.commit({"map.h": header, "map.cpp": nearest_content}, [old])
        self.commit({"map.h": header, "map.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}, [nearest])
        manifest, _, _ = proposals.proposeOverrides(self.repo, recovery.auditHistory(self.repo), [old, nearest], False)
        self.assertEqual(self.blob(nearest_content), manifest["entries"][0]["blob"])

    def testClassPrefixMatchingAllowsOldSourceDirectoryMoves(self):
        donor = self.commit({"object/CCreature.cpp": b"void Creature::move() {}\n"})
        self.commit({"creatures/creature.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}, [donor])
        manifest, report, _ = proposals.proposeOverrides(self.repo, recovery.auditHistory(self.repo), [donor], False)
        self.assertEqual(1, report["donorEntryCount"])
        self.assertIn("object/CCreature.cpp", manifest["entries"][0]["provenance"])

    def testHistoricalInteractionTypoUsesMatchingActualClassDonor(self):
        donor = self.commit({"CInteraction.cpp": b"void CInteraction::onAction() {}\n"})
        self.commit({"src/CIteraction.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}, [donor])
        manifest, report, _ = proposals.proposeOverrides(self.repo, recovery.auditHistory(self.repo), [donor], False)
        self.assertEqual(1, report["donorEntryCount"])
        self.assertEqual("src/CIteraction.cpp", manifest["entries"][0]["path"])

    def testImageWithoutExtensionUsesMatchingFramedAsset(self):
        image = proposals.imagePlaceholder("real donor")
        donor = self.commit({"images/items/armor/0.png": image})
        self.commit({"images/items/armor/0" + recovery.MARKER_SUFFIX: b"f" * 40}, [donor])
        manifest, report, _ = proposals.proposeOverrides(self.repo, recovery.auditHistory(self.repo), [donor], False)
        self.assertEqual(1, report["donorEntryCount"])
        self.assertEqual(self.blob(image), manifest["entries"][0]["blob"])

    def testUpstreamPayloadsAreVerifiedAndScopedWithTheirLicense(self):
        commit = self.commit({"json/value.h" + recovery.MARKER_SUFFIX: b"f" * 40})
        source = self.repo / "recovery" / "upstream" / "jsoncpp"
        source.mkdir(parents=True)
        content, license_text = b"class Value {};\n", b"MIT license fixture\n"
        (source / "value.h").write_bytes(content)
        (source / "LICENSE").write_bytes(license_text)
        recovery.writeJson(
            source / "catalog.json",
            {
                "entries": [
                    {
                        "path": "json/value.h",
                        "source": "value.h",
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "provenance": "unverified upstream matching release",
                    },
                    {
                        "path": "json/LICENSE",
                        "source": "LICENSE",
                        "sha256": hashlib.sha256(license_text).hexdigest(),
                        "provenance": "upstream distribution license",
                        "add": True,
                        "whenPrefix": "json/",
                    },
                ]
            },
        )
        manifest, report, payloads = proposals.proposeOverrides(self.repo, recovery.auditHistory(self.repo), [], False)
        self.assertEqual(0, report["unresolvedCount"])
        self.assertEqual(2, report["upstreamEntryCount"])
        self.assertEqual(content, payloads["upstream/jsoncpp/value.h"])
        self.assertTrue(next(entry for entry in manifest["entries"] if entry["path"] == "json/LICENSE")["add"])
        (source / "value.h").write_bytes(b"tampered")
        with self.assertRaisesRegex(recovery.RecoveryError, "SHA-256 mismatch"):
            proposals.proposeOverrides(self.repo, recovery.auditHistory(self.repo), [], False)


if __name__ == "__main__":
    unittest.main()
