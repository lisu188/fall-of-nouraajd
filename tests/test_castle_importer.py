"""Synthetic RoE fixtures; no Heroes III installation is needed for these tests."""

import copy
import gzip
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from scripts import import_castle_campaign as importer


def packString(value=b""):
    return struct.pack("<I", len(value)) + value


def syntheticTemplate(object_type, subtype=0, block_mask=None, visit_mask=None):
    block_mask = block_mask or [255] * 6
    visit_mask = visit_mask or [0] * 6
    return (
        packString(b"SYNTHETIC.DEF")
        + bytes(block_mask + visit_mask)
        + struct.pack("<HHIIBB", 0, 1023, object_type, subtype, 0, 0)
        + bytes(16)
    )


def syntheticHero():
    return (
        bytes([0, 255, 1])
        + packString(b"Discard this original name")
        + struct.pack("<I", 1)
        + bytes([0, 0, 0, 0, 0, 255])
        + bytes(16)
    )


def syntheticMap(object_type=70):
    header = (
        struct.pack("<IBIB", 14, 0, 36, 1)
        + packString(b"Discard this scenario title")
        + packString(b"Discard this scenario prose")
        + bytes(1 + 8 * 8)
        + bytes([255, 255, 0])
        + bytes(16 + 31)
        + struct.pack("<I", 0)
    )
    terrain = bytes([2, 3, 1, 2, 3, 4, 5]) * (36 * 36) + bytes([6, 4, 0, 0, 0, 0, 1]) * (36 * 36)
    templates = struct.pack("<I", 2)
    templates += syntheticTemplate(object_type, block_mask=[255] * 5 + [191], visit_mask=[0] * 5 + [64])
    templates += syntheticTemplate(134, block_mask=[255] * 5 + [254])
    objects = struct.pack("<I", 2)
    objects += bytes([10, 10, 0]) + struct.pack("<I", 0) + bytes(5)
    if object_type == 70:
        objects += syntheticHero()
    objects += bytes([20, 20, 1]) + struct.pack("<I", 1) + bytes(5)
    return header + terrain + templates + objects + struct.pack("<I", 0)


def syntheticLod(payload, compressed):
    stored = zlib.compress(payload) if compressed else payload
    header = bytearray(92)
    header[:4] = b"LOD\0"
    struct.pack_into("<I", header, 8, 1)
    entry = b"GOOD1.H3C".ljust(16, b"\0") + struct.pack("<IIII", 124, len(payload), 0, len(stored) if compressed else 0)
    return bytes(header) + entry + stored


class CastleImporterTest(unittest.TestCase):
    def testFullSyntheticExportUsesPortableNewlinesAndRejectsUnverifiedEditions(self):
        members = [struct.pack("<I", 5)] + [syntheticMap()] * 3
        campaign = b"".join(gzip.compress(member, mtime=0) for member in members)
        scenarios = (("castleFixtureOne", 36), ("castleFixtureTwo", 36), ("castleFixtureThree", 36))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "synthetic.lod"
            archive.write_bytes(syntheticLod(campaign, True))
            output = root / "maps"
            metadata = root / "metadata"
            with self.assertRaisesRegex(importer.ImportError, "verified source edition"):
                importer.importCampaign(archive, output, metadata_root=metadata)
            self.assertFalse(output.exists())
            with mock.patch.object(
                importer, "CAMPAIGN_SHA256", hashlib.sha256(campaign).hexdigest()
            ), mock.patch.object(importer, "SCENARIOS", scenarios):
                sources = importer.importCampaign(archive, output, metadata_root=metadata)
            self.assertEqual(3, len(sources))
            for source in sources:
                for path in (output / source["mapId"] / "map.json", metadata / (source["mapId"] + ".json")):
                    self.assertTrue(path.read_bytes().endswith(b"\n"))
                    self.assertEqual(0, path.read_bytes().count(b"\r"), str(path))
                    self.assertNotIn("Discard this", path.read_text())

    def testReadsRawAndCompressedLodEntries(self):
        for compressed in (False, True):
            with self.subTest(compressed=compressed), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "synthetic.lod"
                path.write_bytes(syntheticLod(b"Synthetic campaign payload", compressed))
                self.assertEqual(importer.readLodEntry(path), b"Synthetic campaign payload")

    def testRejectsMissingOrTruncatedArchiveEntry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.lod"
            path.write_bytes(syntheticLod(b"payload", False))
            with self.assertRaisesRegex(importer.ImportError, "found 0"):
                importer.readLodEntry(path, "OTHER.H3C")
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(importer.ImportError, "Truncated LOD resource"):
                importer.readLodEntry(path)

    def testRejectsDecompressionBombAndInvalidBoundary(self):
        with self.assertRaisesRegex(importer.ImportError, "size limit"):
            importer.decompressBounded(zlib.compress(b"x" * (importer.MAX_MEMBER_SIZE + 1)))
        with self.assertRaisesRegex(importer.ImportError, "boundary"):
            importer.decompressBounded(zlib.compress(b"x") + b"unexpected")

    def testPreservesGzipMemberBoundaries(self):
        members = [struct.pack("<I", 5), b"map one", b"map two", b"map three"]
        campaign = b"".join(gzip.compress(member, mtime=0) for member in members)
        self.assertEqual(importer.splitCampaign(campaign), members)
        with self.assertRaisesRegex(importer.ImportError, "trailing data"):
            importer.splitCampaign(campaign + b"garbage")
        with self.assertRaisesRegex(importer.ImportError, "three maps"):
            importer.splitCampaign(gzip.compress(members[0], mtime=0))

    def testMapPreservesBothLevelsAndSevenTerrainFields(self):
        source = importer.readMap(syntheticMap(), "castleGuardianAngels")
        self.assertEqual((source["width"], source["height"], source["layers"]), (36, 36, 2))
        self.assertEqual(source["terrain"][0][0], [2, 3, 1, 2, 3, 4, 5])
        self.assertEqual(source["terrain"][1][-1], [6, 4, 0, 0, 0, 0, 1])
        self.assertEqual(source["objects"][0]["anchor"], [10, 10, 0])
        self.assertEqual(source["objects"][0]["visit"], [9, 10, 0])
        self.assertNotIn("Discard this", json.dumps(source))

    def testMaskOrientationUsesBottomRightAnchorAndZeroMeansBlocked(self):
        template = {"blockMask": [255] * 5 + [254], "visitMask": [0] * 5 + [64]}
        self.assertEqual(importer.footprint(template, [20, 20, 1], "blockMask", True), [[13, 20, 1]])
        self.assertEqual(importer.footprint(template, [20, 20, 1], "visitMask"), [[19, 20, 1]])

    def testRejectsUnknownObjectPayloadAndMapVersion(self):
        with self.assertRaisesRegex(importer.ImportError, "Unsupported RoE object type 999"):
            importer.readMap(syntheticMap(999), "castleGuardianAngels")
        with self.assertRaisesRegex(importer.ImportError, "version 14"):
            importer.readMap(struct.pack("<I", 21) + syntheticMap()[4:], "castleGuardianAngels")

    def testRejectsTruncatedObjectsAndUnexpectedTrailingBytes(self):
        data = syntheticMap()
        with self.assertRaises(importer.ImportError):
            importer.readMap(data[:-10], "castleGuardianAngels")
        with self.assertRaisesRegex(importer.ImportError, "trailing map data"):
            importer.readMap(data + b"unexpected", "castleGuardianAngels")

    def testChecksBooleanAndStringBounds(self):
        with self.assertRaisesRegex(importer.ImportError, "boolean"):
            importer.Reader(b"\x02").boolean()
        with self.assertRaisesRegex(importer.ImportError, "Unbounded string"):
            importer.Reader(struct.pack("<I", 100001)).string()

    def testCreatureArmyConsumesAllSevenSlots(self):
        payload = bytes([4]) + struct.pack("<H", 12) + (bytes([255]) + bytes(2)) * 6 + b"tail"
        reader = importer.Reader(payload)
        self.assertEqual(importer.readArmy(reader), [{"creature": 4, "count": 12}])
        self.assertEqual(reader.take(4), b"tail")

    def testMonsterPayloadIncludesGuardedRewardFields(self):
        record = {"type": 54, "subtype": 12}
        payload = struct.pack("<HBB", 3, 0, 1) + packString(b"Never exported")
        payload += struct.pack("<7i", 0, 0, 0, 0, 0, 0, 200) + bytes([7, 1, 1, 0, 0])
        reader = importer.Reader(payload)
        importer.readPayload(reader, record)
        self.assertEqual(record["army"], [{"creature": 12, "count": 3}])
        self.assertEqual(record["resources"][-1], 200)
        self.assertEqual(record["artifact"], 7)
        self.assertEqual(reader.position, len(payload))

    def testSeerQuestExtractsCreatureRewardWithoutProse(self):
        reader = importer.Reader(bytes([72, 10, 12, 10, 0, 0, 0]))
        record = {}
        importer.readSeer(reader, record)
        self.assertEqual(record["questArtifact"], 72)
        self.assertEqual(record["rewardArmy"], [{"creature": 12, "count": 10}])
        self.assertEqual(reader.position, len(reader.data))

    def testCaveAndMonolithPairingUsesVisitableLocations(self):
        objects = [
            {"index": 1, "type": 103, "subtype": 0, "anchor": [8, 8, 0], "visit": [7, 8, 0]},
            {"index": 2, "type": 103, "subtype": 0, "anchor": [8, 7, 1], "visit": [7, 7, 1]},
            {"index": 3, "type": 45, "subtype": 1, "anchor": [1, 1, 0], "visit": [1, 1, 0]},
            {"index": 4, "type": 45, "subtype": 1, "anchor": [20, 20, 0], "visit": [20, 20, 0]},
        ]
        pairs = importer.pairPortals(objects)
        self.assertEqual(pairs[0]["from"], [7, 8, 0])
        self.assertEqual(pairs[0]["to"], [7, 7, 1])
        self.assertEqual(pairs[1]["kind"], "twoWay")
        with self.assertRaisesRegex(importer.ImportError, "Unpaired"):
            importer.pairPortals(objects[:1])

    def testNativeTerrainUsesLoaderGidMinusOneAndPreservesInteractionAccess(self):
        source = importer.readMap(syntheticMap(), "castleGuardianAngels")
        tileset = {
            "tileproperties": {
                "5": {"type": "castleRoadTile"},
                "13": {"type": "castleRiverTile"},
                "14": {"type": "castleBridgeTile"},
            }
        }
        native_map = importer.buildNativeMap(source, copy.deepcopy(tileset))
        self.assertEqual(native_map["properties"], {"x": "9", "y": "10", "z": "0"})
        self.assertEqual(native_map["layers"][0]["data"][0], 15)
        self.assertEqual(native_map["layers"][0]["data"][10 * 36 + 9], 15)
        self.assertEqual(native_map["layers"][2]["data"][20 * 36 + 13], 12)
        self.assertNotIn([9, 10, 0], source["blockedCells"])
        self.assertIn([13, 20, 1], source["blockedCells"])

    def testDiagonalAdaptationConnectsRequiredCorridorAndPrunesOptionalBranch(self):
        land = {(0, 0), (1, 1), (2, 2), (3, 3), (0, 2)}
        source = {
            "width": 4,
            "terrain": [[[2 if (x, y) in land else 9, 0, 0, 0, 0, 0, 0] for y in range(4) for x in range(4)]],
            "objects": [{"type": 17, "visit": [3, 3, 0], "visitable": True}],
            "portals": [],
            "boatRoutes": [],
            "spawn": [0, 0, 0],
        }
        before = copy.deepcopy(source)
        routes = importer.buildDiagonalRoutes(source, set())
        self.assertEqual(len(routes), 3)
        self.assertEqual(source, before)
        self.assertEqual(routes, importer.buildDiagonalRoutes(source, set()))
        self.assertTrue(all(route["kind"] == "diagonalPassage" for route in routes))
        self.assertNotIn([0, 2, 0], [point for route in routes for point in (route["from"], route["to"])])

    def testDiagonalAdaptationCannotInventStepsAcrossBlockedTerrain(self):
        source = {
            "width": 3,
            "terrain": [[[2 if index in (0, 8) else 9, 0, 0, 0, 0, 0, 0] for index in range(9)]],
            "objects": [{"type": 17, "visit": [2, 2, 0], "visitable": True}],
            "portals": [],
            "boatRoutes": [],
            "spawn": [0, 0, 0],
        }
        with self.assertRaisesRegex(importer.ImportError, "cannot connect"):
            importer.buildDiagonalRoutes(source, set())


if __name__ == "__main__":
    unittest.main()
