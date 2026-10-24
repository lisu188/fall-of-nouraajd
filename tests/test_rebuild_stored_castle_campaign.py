# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny stored-Castle validation fixtures; never invoke the actual authoring generators."""

import copy
import ast
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def loadTool():
    spec = importlib.util.spec_from_file_location(
        "stored_castle_tool_under_test", ROOT / "scripts/rebuild_stored_castle_campaign.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


class StoredCastleReviewTest(unittest.TestCase):
    def setUp(self):
        self.tool = loadTool()
        self.scenario = self.tool.Scenario("castleHomecoming", "homecoming", 4, 1, 2)

    def fixture(self):
        old = {
            "schemaVersion": 1,
            "mapId": self.scenario.mapId,
            "scenarioId": self.scenario.scenarioId,
            "sourceSha256": self.tool.CAMPAIGN_SHA256,
            "mapSha256": "b" * 64,
            "width": 4,
            "height": 4,
            "layers": 2,
            "terrain": [[[2, 0, 0, 0, 0, 0, 0] for _ in range(16)] for _ in range(2)],
            "templates": [{"index": 0}],
            "objects": [{"index": 958, "template": 0, "visit": [2, 2, 0]}],
            "blockedCells": [],
            "portals": [],
            "boatRoutes": [],
            "diagonalRoutes": [{"kind": "diagonalPassage", "from": [0, 0, 0], "to": [1, 1, 0]}],
        }
        after = copy.deepcopy(old)
        after["diagonalRoutes"].append(
            {"kind": "diagonalPassage", "from": [1, 1, 0], "to": [2, 2, 0], "adaptation": "requiredActorAccess"}
        )
        original = {
            "id": 7,
            "name": "originalActor958",
            "type": "castleGarrison",
            "x": 64,
            "y": 64,
            "properties": {"alive": True, "reward": 0},
        }
        native = {
            "width": 4,
            "height": 4,
            "properties": {"x": "0"},
            "tilesets": [{"native": True}],
            "layers": [
                {"name": "ground", "type": "tilelayer", "data": [1] * 16},
                {
                    "name": "Castle campaign 0",
                    "type": "objectgroup",
                    "properties": {"level": "0"},
                    "objects": [original],
                },
            ],
            "nextobjectid": 8,
        }
        result = copy.deepcopy(native)
        for name, x, y, target, identifier in (
            ("castleHomecomingPortal1A", 32, 32, [2, 2, 0], 8),
            ("castleHomecomingPortal1B", 64, 64, [1, 1, 0], 9),
        ):
            result["layers"][1]["objects"].append(
                {
                    "id": identifier,
                    "name": name,
                    "type": "castlePortal",
                    "x": x,
                    "y": y,
                    "width": 32,
                    "height": 32,
                    "visible": True,
                    "rotation": 0,
                    "properties": {
                        "label": "Narrow passage",
                        "animation": "images/footprint",
                        "campaign_portalKind": "diagonalPassage",
                        "campaign_targetX": target[0],
                        "campaign_targetY": target[1],
                        "campaign_targetZ": target[2],
                    },
                }
            )
        result["nextobjectid"] = 10
        return old, after, native, result

    def fakeModules(self, new_source, new_map, unstable=False):
        calls = []

        def build(source, tileset):
            calls.append("tiny synthetic build")
            source.clear()
            source.update(copy.deepcopy(new_source))
            native = copy.deepcopy(new_map)
            if unstable and len(calls) == 2:
                native["properties"]["unstable"] = True
            return native

        return (
            SimpleNamespace(CAMPAIGN_SHA256=self.tool.CAMPAIGN_SHA256, buildNativeMap=build),
            SimpleNamespace(authorMap=lambda native, source: native),
            calls,
        )

    def testFixedProductionPolicyHasSixLiteralOutputsAndUnchangedBudgets(self):
        self.assertEqual(
            [("castleHomecoming", 72, 21, 26), ("castleGuardianAngels", 36, 8, 8), ("castleGriffinCliff", 72, 4, 17)],
            [(row.mapId, row.width, row.legacyRoutes, row.finalRoutes) for row in self.tool.SCENARIOS],
        )
        self.assertEqual(6, len(self.tool.OUTPUTS))
        self.assertEqual(6, len(set(self.tool.OUTPUTS)))
        self.assertEqual(16 * 1024**2, self.tool.AGGREGATE_LIMIT)

    def testEntryCannotSelectOriginalArchiveReadersOrArbitraryPaths(self):
        source = (ROOT / "scripts/rebuild_stored_castle_campaign.py").read_text()
        tree = ast.parse(source)
        forbidden = {"importCampaign", "readMap", "readLodEntry", "splitCampaign"}
        self.assertFalse(any(isinstance(node, ast.Attribute) and node.attr in forbidden for node in ast.walk(tree)))
        self.assertNotIn('"--source"', source)
        self.assertNotIn('"--heroes-dir"', source)
        self.assertNotIn('"--output-root"', source)

    def testExactLegacySourceObjectsTerrainAndOverlapAreRetained(self):
        old, after, native, result = self.fixture()
        routes = self.tool.validateSourceChange(self.scenario, old, after)
        additions = self.tool.validateMapChange(self.scenario, after, native, result)
        self.assertEqual([after["diagonalRoutes"][-1]], routes)
        self.assertEqual([8, 9], [row["id"] for row in additions])
        self.assertEqual((64, 64), (result["layers"][1]["objects"][-1]["x"], result["layers"][1]["objects"][-1]["y"]))
        self.assertEqual(native["layers"][1]["objects"][0], result["layers"][1]["objects"][0])

    def testSourceChangesRejectEveryNonrouteFieldAndInvalidNewPassage(self):
        for mode in (
            "terrain",
            "sourceVisit",
            "binaryFingerprint",
            "badIdentity",
            "schemaType",
            "badTemplate",
            "oldRoute",
            "water",
            "blocked",
            "wrongKind",
            "missingMarker",
            "nonadjacent",
        ):
            with self.subTest(mode=mode):
                old, after, _, _ = self.fixture()
                if mode == "terrain":
                    after["terrain"][1][0][6] = 1
                elif mode == "sourceVisit":
                    after["objects"][0]["visit"] = [3, 3, 0]
                elif mode == "binaryFingerprint":
                    after["mapSha256"] = "c" * 64
                elif mode == "badIdentity":
                    after["mapId"] = "foreign"
                elif mode == "schemaType":
                    old["schemaVersion"] = after["schemaVersion"] = True
                elif mode == "badTemplate":
                    after["objects"][0]["template"] = 1
                elif mode == "oldRoute":
                    after["diagonalRoutes"][0]["to"] = [2, 2, 0]
                elif mode == "water":
                    old["terrain"][0][10][0] = after["terrain"][0][10][0] = 8
                elif mode == "blocked":
                    old["blockedCells"] = after["blockedCells"] = [[2, 2, 0]]
                elif mode == "wrongKind":
                    after["diagonalRoutes"][-1]["kind"] = "teleport"
                elif mode == "missingMarker":
                    del after["diagonalRoutes"][-1]["adaptation"]
                else:
                    after["diagonalRoutes"][-1]["to"] = [3, 3, 0]
                with self.assertRaises((ValueError, KeyError)):
                    self.tool.validateSourceChange(self.scenario, old, after)

    def testMapChangesRejectOldWritesWrongNewFieldsDuplicatesAndRenumbering(self):
        for mode in (
            "oldId",
            "oldField",
            "oldBoolType",
            "oldOrder",
            "terrain",
            "layer",
            "header",
            "newId",
            "duplicateId",
            "newTarget",
            "newKind",
            "newLayer",
            "foreign",
            "deleted",
            "nextId",
        ):
            with self.subTest(mode=mode):
                _, source, before, after = self.fixture()
                rows = after["layers"][1]["objects"]
                if mode == "oldId":
                    rows[0]["id"] = 6
                elif mode == "oldField":
                    rows[0]["properties"]["reward"] = 1
                elif mode == "oldBoolType":
                    rows[0]["properties"]["alive"] = 1
                elif mode == "oldOrder":
                    rows.reverse()
                elif mode == "terrain":
                    after["layers"][0]["data"][0] = 2
                elif mode == "layer":
                    after["layers"][1]["properties"]["level"] = "1"
                elif mode == "header":
                    after["properties"]["x"] = "1"
                elif mode == "newId":
                    rows[1]["id"] = 10
                elif mode == "duplicateId":
                    rows[2]["id"] = 8
                elif mode == "newTarget":
                    rows[1]["properties"]["campaign_targetX"] = 3
                elif mode == "newKind":
                    rows[1]["type"] = "foreign"
                elif mode == "newLayer":
                    after["layers"][0]["objects"] = [rows.pop()]
                elif mode == "foreign":
                    rows[1]["name"] = "foreign"
                elif mode == "deleted":
                    rows.pop(0)
                else:
                    after["nextobjectid"] = 12
                with self.assertRaises(ValueError):
                    self.tool.validateMapChange(self.scenario, source, before, after)

    def testComputedSerializationReplaysExactlyWithoutRealGenerators(self):
        old, after, native, result = self.fixture()
        importer, author, calls = self.fakeModules(after, result)
        encoded, report = self.tool.computeScenario(
            self.scenario, old, native, {}, importer.buildNativeMap, author.authorMap
        )
        self.assertEqual(2, len(calls))
        self.assertEqual(self.tool.serialize(after, result), encoded)
        self.assertTrue(report["replayIdempotent"])
        importer, author, _ = self.fakeModules(after, result, unstable=True)
        with self.assertRaisesRegex(ValueError, "not idempotent"):
            self.tool.computeScenario(self.scenario, old, native, {}, importer.buildNativeMap, author.authorMap)

    def testAlreadyRegeneratedSourceAndMapRemainUnchanged(self):
        _, after, _, result = self.fixture()
        importer, author, _ = self.fakeModules(after, result)
        encoded, report = self.tool.computeScenario(
            self.scenario, after, result, {}, importer.buildNativeMap, author.authorMap
        )
        self.assertEqual(self.tool.serialize(after, result), encoded)
        self.assertEqual([], report["addedObjects"])
        self.assertEqual([], report["addedRoutes"])

    def testGuardianRefusesEvenOtherwisePermittedNewResources(self):
        old, after, native, result = self.fixture()
        scenario = self.tool.Scenario("castleGuardianAngels", "guardianAngels", 4, 1, 2)
        for source in (old, after):
            source.update(mapId=scenario.mapId, scenarioId=scenario.scenarioId)
        for row in result["layers"][1]["objects"][1:]:
            row["name"] = row["name"].replace("castleHomecoming", "castleGuardianAngels")
        importer, author, _ = self.fakeModules(after, result)
        with self.assertRaisesRegex(ValueError, "Guardian Angels changed"):
            self.tool.computeScenario(scenario, old, native, {}, importer.buildNativeMap, author.authorMap)

    def testGuardianRequiresUnmodifiedRawBytesAsWellAsEqualValues(self):
        source, _, native, _ = self.fixture()
        scenario = self.tool.Scenario("castleGuardianAngels", "guardianAngels", 4, 1, 1)
        source.update(mapId=scenario.mapId, scenarioId=scenario.scenarioId)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (
                "res/campaigns/longLiveTheQueen/sources/castleGuardianAngels.json",
                "res/maps/castleGuardianAngels/map.json",
            )
            for path, raw in zip(paths, self.tool.serialize(source, native)):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            tiles = root / "res/maps/multilevel/map.json"
            tiles.parent.mkdir(parents=True)
            tiles.write_text(json.dumps({"tilesets": [{"tileproperties": {"5": {}}, "tilepropertytypes": {}}]}))
            importer, author, _ = self.fakeModules(source, native)
            with patch.dict(os.environ, GITHUB_ACTIONS="true"), patch.object(
                self.tool, "SCENARIOS", (scenario,)
            ), patch.object(self.tool, "OUTPUTS", paths), patch.object(self.tool, "requireCapacity"), patch.object(
                self.tool, "verifyTracked"
            ), patch.object(
                self.tool, "loadAuthoring", return_value=(importer, author)
            ):
                with patch.object(Path, "write_bytes", side_effect=AssertionError("check wrote")):
                    self.assertEqual([], self.tool.run(root, root, check=True)["changedFiles"])
                (root / paths[0]).write_bytes((root / paths[0]).read_bytes() + b" ")
                with patch.object(
                    Path, "write_bytes", side_effect=AssertionError("refusal wrote")
                ), self.assertRaisesRegex(ValueError, "raw bytes changed"):
                    self.tool.run(root, root)

    def testPathGuardRejectsEscapesAndSymlinkParents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inside").mkdir()
            path = root / "inside/data.json"
            path.write_text("{}")
            (root / "outside.json").write_text("{}")
            self.assertEqual(path, self.tool.safePath(root, "inside/data.json"))
            with self.assertRaisesRegex(ValueError, "escapes"):
                self.tool.safePath(root / "inside", "../outside.json")
            original = Path.is_symlink
            with patch.object(Path, "is_symlink", lambda path: path == root / "inside" or original(path)):
                with self.assertRaisesRegex(ValueError, "Symlink"):
                    self.tool.safePath(root, "inside/data.json")

    def testTrackedPolicyRejectsMissingSymlinkAndUnmergedTargets(self):
        lines = ["100644 " + "a" * 40 + " 0\t" + path for path in self.tool.OUTPUTS]
        for mode in ("valid", "missing", "symlink", "unmerged"):
            selected = list(lines)
            if mode == "missing":
                selected.pop()
            if mode == "symlink":
                selected[0] = selected[0].replace("100644", "120000")
            if mode == "unmerged":
                selected[0] = selected[0].replace(" 0\t", " 1\t")
            with patch.object(self.tool.subprocess, "check_output", return_value=("\0".join(selected) + "\0").encode()):
                if mode == "valid":
                    self.tool.verifyTracked(Path.cwd())
                else:
                    with self.assertRaises(ValueError):
                        self.tool.verifyTracked(Path.cwd())

    def testCapacityRejectsThresholdAndProjectedCrossing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for total, free in (
                (10 * 1024**3, 1024**3),
                (10 * 1024**3, 1100 * 1024**2),
                (512 * 1024**2, 112 * 1024**2),
            ):
                usage = shutil._ntuple_diskusage(total, total - free, free)
                with patch.object(self.tool.shutil, "disk_usage", return_value=usage), self.assertRaises(ValueError):
                    self.tool.requireCapacity(root, root)
            total = 10 * 1024**3
            free = total // 10 + 128 * 1024**2 + 1
            with patch.object(
                self.tool.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(total, total - free, free)
            ):
                self.tool.requireCapacity(root, root)

    def testRealEntryRejectsLocalGenerationBeforeAnyBuilderOrFileAccess(self):
        with patch.dict(os.environ, GITHUB_ACTIONS="false"), patch.object(
            self.tool, "loadAuthoring", side_effect=AssertionError("real generator forbidden")
        ) as load:
            with self.assertRaisesRegex(ValueError, "CI-only"):
                self.tool.run(Path("missing"), Path("missing"))
            load.assert_not_called()

    def testTinyEntryWritesOnlyKnownOutputsThenChecksReadOnlyAndRejectsBudget(self):
        old, after, native, result = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (
                "res/campaigns/longLiveTheQueen/sources/castleHomecoming.json",
                "res/maps/castleHomecoming/map.json",
            )
            for path, raw in zip(paths, self.tool.serialize(old, native)):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            tiles = root / "res/maps/multilevel/map.json"
            tiles.parent.mkdir(parents=True)
            tiles.write_text(json.dumps({"tilesets": [{"tileproperties": {"5": {}}, "tilepropertytypes": {}}]}))
            importer, author, calls = self.fakeModules(after, result)
            with patch.dict(os.environ, GITHUB_ACTIONS="true"), patch.object(
                self.tool, "SCENARIOS", (self.scenario,)
            ), patch.object(self.tool, "OUTPUTS", paths), patch.object(self.tool, "requireCapacity"), patch.object(
                self.tool, "verifyTracked"
            ), patch.object(
                self.tool, "loadAuthoring", return_value=(importer, author)
            ):
                raw_before = {path: (root / path).read_bytes() for path in paths}
                with self.assertRaisesRegex(ValueError, "stale"), patch.object(
                    Path, "write_bytes", side_effect=AssertionError("check wrote a file")
                ):
                    self.tool.run(root, root, check=True)
                self.assertEqual(raw_before, {path: (root / path).read_bytes() for path in paths})
                generated = self.tool.run(root, root)
                self.assertEqual(set(paths), set(generated["changedFiles"]))
                with patch.object(Path, "write_bytes", side_effect=AssertionError("check wrote a file")):
                    checked = self.tool.run(root, root, check=True)
                self.assertEqual([], checked["changedFiles"])
                self.assertEqual(6, len(calls))
                for path, data in raw_before.items():
                    (root / path).write_bytes(data)
                with patch.object(self.tool, "AGGREGATE_LIMIT", sum(map(len, raw_before.values())) + 1), patch.object(
                    Path, "write_bytes", side_effect=AssertionError("budget refusal wrote")
                ):
                    with self.assertRaisesRegex(ValueError, "Aggregate output"):
                        self.tool.run(root, root)
                with patch.object(self.tool, "AGGREGATE_LIMIT", 1), patch.object(
                    self.tool, "loadAuthoring", side_effect=AssertionError("budget must reject before builder")
                ):
                    with self.assertRaisesRegex(ValueError, "Aggregate input"):
                        self.tool.run(root, root)


if __name__ == "__main__":
    unittest.main()
