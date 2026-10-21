# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Factual region projection/unsupported-effect contracts; no native execution or parity credit."""

import copy
import json
from pathlib import Path
import unittest

from scripts.build_baldurs_gate_city_regions import buildRegions, regionCells

ROOT = Path(__file__).resolve().parents[1]


def sampleRegion(**changes):
    row = {
        "sourceId": "AR0100#region1",
        "name": "Trap1",
        "type": 0,
        "destination": "",
        "flags": 8,
        "text_strref": 0,
        "trap_difficulty": 40,
        "trap_removal": 40,
        "trapped": 1,
        "key": "",
        "script": "GTFB",
        "bounding_box": [0, 0, 128, 64],
        "polygon": [[0, 0], [128, 0], [128, 64], [0, 64]],
        "use_point": [0, 0],
    }
    row.update(changes)
    return row


class BaldursGateCityRegionTest(unittest.TestCase):
    def setUp(self):
        self.source = {
            "areas": {"AR0100": {"sha256": "a" * 64, "regions": [sampleRegion()]}},
            "references": {"GTFB.BCS": {"sha256": "b" * 64}},
        }
        self.atlas = {"AR0100": [4, 5, 2, 4, 4]}
        self.config = {}
        self.objects = {2: [{"id": 50, "name": "existing"}]}
        self.calls = []

    def usablePosition(self, area_id, point, *, reserve):
        self.calls.append((area_id, point, reserve))
        x, y, z, width, height = self.atlas[area_id]
        return (x + min(width - 1, max(0, point[0] // 64)), y + min(height - 1, max(0, point[1] // 64)), z)

    def build(self, **kwargs):
        return buildRegions(
            self.source, self.atlas, self.config, self.objects, usablePosition=self.usablePosition, **kwargs
        )

    def properties(self):
        return self.config["cityAr0100Region1"]["properties"]

    def testPolygonCoversEveryIntersectingCellWithoutFillingConcaveHoles(self):
        polygon = [[0, 0], [192, 0], [192, 64], [64, 64], [64, 192], [0, 192]]
        cells, candidates = regionCells(polygon, [10, 20, 3, 3, 3])
        self.assertEqual([[10, 20, 3], [11, 20, 3], [12, 20, 3], [10, 21, 3], [10, 22, 3]], cells)
        self.assertEqual(9, candidates)

    def testThinPolygonAndBoundaryContactUsePositiveAreaOverlap(self):
        cells, _ = regionCells([[0, 0], [128, 0], [128, 1], [0, 1]], [0, 0, 0, 3, 3])
        self.assertEqual([[0, 0, 0], [1, 0, 0]], cells)
        cells, candidates = regionCells([[0, 0], [64, 0], [64, 64], [0, 64]], [0, 0, 0, 3, 3])
        self.assertEqual([[0, 0, 0]], cells)
        self.assertEqual(1, candidates)

    def testSourcePropertiesRemainExactAndObjectIdsContinueAfterSparseExistingIds(self):
        before = copy.deepcopy(self.source)
        manifest = self.build()
        props = self.properties()
        self.assertEqual(before, self.source)
        self.assertEqual("AR0100#region1", props["sourceRegion"])
        self.assertEqual("b" * 64, props["sourceScriptSha256"])
        self.assertEqual(40, props["sourceTrapDetection"])
        self.assertEqual(40, props["sourceTrapRemoval"])
        self.assertEqual(16, props["disarmAgility"])
        self.assertEqual(
            self.source["areas"]["AR0100"]["regions"][0]["polygon"], json.loads(props["sourceRegionPolygon"])
        )
        self.assertEqual([[4, 5, 2], [5, 5, 2]], json.loads(props["regionCells"]))
        self.assertEqual(51, self.objects[2][-1]["id"])
        self.assertTrue(self.calls[0][2])
        self.assertFalse(manifest["originalParityEstablished"])

    def testRecognizableTrapNameNeverCreatesGuessedDamageOrDisarmCredit(self):
        manifest = self.build()
        props = self.properties()
        self.assertEqual("unsupportedScript", props["regionScriptStatus"])
        self.assertTrue(props["regionScriptPending"])
        self.assertFalse(props["regionEffectApproved"])
        self.assertFalse(props["regionDamageSupported"])
        self.assertFalse(self.objects[2][-1]["visible"])
        self.assertEqual("", props["animation"])
        self.assertTrue({"damage", "damageMin", "damageMax", "dmgMin", "dmgMax", "xp", "disarmed"}.isdisjoint(props))
        self.assertEqual(["GTFB"], manifest["unsupportedScripts"])

    def testInfoTextNeedsAnAuthoredRewriteAndNoStringFlagTakesPrecedence(self):
        self.source["areas"]["AR0100"]["regions"][0] = sampleRegion(type=1, script="", trapped=0, text_strref=14985)
        self.build()
        props = self.properties()
        self.assertTrue(props["regionInfoTextPending"])
        self.assertEqual(14985, props["sourceTextStrref"])
        self.assertNotIn("infoText", props)
        self.assertEqual("noScript", props["regionScriptStatus"])
        self.assertTrue(self.objects[2][-1]["visible"])
        self.source["areas"]["AR0100"]["regions"][0]["flags"] = 128
        self.config.clear()
        self.build()
        self.assertFalse(self.properties()["regionInfoTextPending"])

    def testSourceFlagActivationAndUndetectableThresholdsArePreserved(self):
        for flags, difficulty in ((8, 99), (8, 100), (64, 40), (256, 0), (32, 0)):
            with self.subTest(flags=flags, difficulty=difficulty):
                self.config.clear()
                region = self.source["areas"]["AR0100"]["regions"][0]
                region.update(flags=flags, trap_difficulty=difficulty)
                self.build()
                props = self.properties()
                self.assertEqual(not bool(flags & 8) or difficulty >= 100, props["forbidDetecting"])
                self.assertEqual(not bool(flags & (32 | 256)), props["regionEnabled"])
                self.assertEqual(bool(flags & 64), props["sourceAnyoneActivates"])

    def testAlternativeUsePointAndCallerManifestAreRetainedWithoutMovingActivationCells(self):
        self.source["areas"]["AR0100"]["regions"][0].update(flags=1024, use_point=[191, 191])
        supplied = {"stale": True}
        result = self.build(region_manifest=supplied)
        self.assertIs(supplied, result)
        self.assertNotIn("stale", result)
        self.assertEqual([191, 191], self.calls[0][1])
        self.assertEqual([6, 7, 2], result["regions"][0]["position"])
        self.assertTrue(result["regions"][0]["anchorOutsideProjectedRegion"])
        self.assertEqual([[4, 5, 2], [5, 5, 2]], result["regions"][0]["cells"])

    def testTravelRegionsRemainOwnedByTheExistingPortalBuilder(self):
        self.source["areas"]["AR0100"]["regions"][0]["destination"] = "AR0200"
        result = self.build()
        self.assertEqual([], result["regions"])
        self.assertEqual({}, self.config)
        self.assertEqual(1, len(self.objects[2]))

    def testMalformedDuplicateOrOutOfBoundsGeometryFailsClosed(self):
        for polygon in ([], [[0, 0], [1, 1], [2, 2]], [[1000, 1000], [1010, 1000], [1010, 1010]]):
            with self.subTest(polygon=polygon), self.assertRaises(ValueError):
                regionCells(polygon, [0, 0, 0, 3, 3])
        with self.assertRaises(ValueError):
            regionCells([[0, 0], [100000, 0], [100000, 100000], [0, 100000]], [0, 0, 0, 2000, 2000])
        self.source["areas"]["AR0100"]["regions"].append(copy.deepcopy(self.source["areas"]["AR0100"]["regions"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.build()

    def testUnknownScriptIsExplicitAndEscapedNativeAnchorIsRejected(self):
        self.source["areas"]["AR0100"]["regions"][0]["script"] = "UNKNOWN"
        self.build()
        self.assertEqual("missingScript", self.properties()["regionScriptStatus"])
        self.config.clear()
        with self.assertRaisesRegex(ValueError, "escaped"):
            buildRegions(
                self.source,
                self.atlas,
                self.config,
                self.objects,
                usablePosition=lambda *args, **kwargs: [999, 999, 999],
            )

    def testAllAuditedNonTravelRegionsHaveOnePersistentIdentityAndBoundedProjectionWork(self):
        source = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf-8"))
        geometry = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_geometry.json").read_text(encoding="utf-8"))
        atlas, config, objects = geometry["atlas"], {}, {}

        def anchor(area_id, point, *, reserve):
            x, y, z, width, height = atlas[area_id]["bounds"]
            return [x + min(width - 1, max(0, point[0] // 64)), y + min(height - 1, max(0, point[1] // 64)), z]

        expected = {
            row["sourceId"]: (area_id, row)
            for area_id, area in source["areas"].items()
            for row in area["regions"]
            if not row["destination"]
        }
        manifest = buildRegions(source, atlas, config, objects, usablePosition=anchor)
        self.assertEqual(set(expected), {row["sourceId"] for row in manifest["regions"]})
        self.assertEqual(188, len(expected))
        self.assertEqual(188, len(config))
        self.assertEqual(188, sum(map(len, objects.values())))
        self.assertLessEqual(manifest["counts"]["candidateCells"], 3000)
        self.assertLessEqual(manifest["counts"]["projectedCells"], manifest["counts"]["candidateCells"])
        for row in manifest["regions"]:
            props = config[row["object"]]["properties"]
            area_id, original = expected[row["sourceId"]]
            self.assertEqual(original["flags"], props["sourceFlags"])
            self.assertEqual(original["text_strref"], props["sourceTextStrref"])
            self.assertEqual(original["script"], props["sourceScript"])
            self.assertFalse(props["regionEffectApproved"])
            self.assertFalse(props["regionDamageSupported"])
            x, y, z, width, height = atlas[area_id]["bounds"]
            self.assertTrue(
                all(
                    point[2] == z and x <= point[0] < x + width and y <= point[1] < y + height for point in row["cells"]
                )
            )


if __name__ == "__main__":
    unittest.main()
