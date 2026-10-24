# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""CI-only Castle resource review from retained source metadata, without original archives."""

import argparse
import copy
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

MIB = 1024 * 1024
AGGREGATE_LIMIT = 16 * MIB
CAMPAIGN_SHA256 = "73c04fb5d3f6beb7d2398d4bbb0128dfc6450fab74922fd4c855bb83508e0a1f"


@dataclass(frozen=True)
class Scenario:
    mapId: str
    scenarioId: str
    width: int
    legacyRoutes: int
    finalRoutes: int


SCENARIOS = (
    Scenario("castleHomecoming", "homecoming", 72, 21, 26),
    Scenario("castleGuardianAngels", "guardianAngels", 36, 8, 8),
    Scenario("castleGriffinCliff", "griffinCliff", 72, 4, 17),
)
OUTPUTS = tuple(
    path
    for scenario in SCENARIOS
    for path in (
        "res/campaigns/longLiveTheQueen/sources/" + scenario.mapId + ".json",
        "res/maps/" + scenario.mapId + "/map.json",
    )
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def sameValue(first, second):
    if type(first) is not type(second):
        return False
    if isinstance(first, dict):
        return first.keys() == second.keys() and all(sameValue(first[key], second[key]) for key in first)
    if isinstance(first, list):
        return len(first) == len(second) and all(sameValue(a, b) for a, b in zip(first, second))
    return first == second


def verifyTracked(root):
    raw = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z", "--", *OUTPUTS],
        cwd=root,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1"},
        timeout=30,
    )
    rows = [entry.decode().split("\t", 1) for entry in raw.split(b"\0") if entry]
    require(len(rows) == len(OUTPUTS) and {path for _, path in rows} == set(OUTPUTS), "Missing/untracked output target")
    require(
        all(meta.split()[0] == "100644" and meta.split()[2] == "0" for meta, _ in rows),
        "Nonregular/unmerged output target",
    )


def safePath(root, relative):
    root = root.resolve(strict=True)
    path = root / relative
    require(path.resolve(strict=True).is_relative_to(root), "Path escapes checkout")
    require(path.is_file(), "Expected an existing regular file")
    cursor = path
    while cursor != root:
        require(not cursor.is_symlink(), "Symlink input/output is unsupported")
        cursor = cursor.parent
    return path


def requireCapacity(root, temporary):
    volumes = {}
    for path in (root, temporary):
        usage = shutil.disk_usage(path)
        require(usage.total > 0 and usage.used * 10 < usage.total * 9, "90% disk guard")
        key = os.stat(path).st_dev
        if key in volumes:
            require(volumes[key][0] == usage.total, "Inconsistent shared-volume capacity")
            volumes[key] = (usage.total, min(volumes[key][1], usage.free))
        else:
            volumes[key] = (usage.total, usage.free)
    for total, free in volumes.values():
        require(free >= 128 * MIB and (free - 128 * MIB) * 10 > total, "128 MiB reserve would cross disk guard")


def validateSource(scenario, source):
    require(
        type(source.get("schemaVersion")) is int and source["schemaVersion"] == 1, "Unsupported stored-source schema"
    )
    require(
        source.get("mapId") == scenario.mapId and source.get("scenarioId") == scenario.scenarioId,
        "Source identity changed",
    )
    require(source.get("sourceSha256") == CAMPAIGN_SHA256, "Stored campaign fingerprint changed")
    require(re.fullmatch(r"[0-9a-f]{64}", source.get("mapSha256", "")) is not None, "Missing original map fingerprint")
    require(
        source.get("width") == source.get("height") == scenario.width and source.get("layers") == 2,
        "Source dimensions changed",
    )
    terrain, templates, objects = source["terrain"], source["templates"], source["objects"]
    require(len(terrain) == 2 and all(len(layer) == scenario.width**2 for layer in terrain), "Invalid terrain shape")
    require(
        all(
            len(cell) == 7 and all(type(value) is int and 0 <= value <= 255 for value in cell)
            for layer in terrain
            for cell in layer
        ),
        "Invalid terrain fields",
    )
    require(0 < len(templates) <= 2000 and len(objects) <= 10_000, "Source count budget exceeded")
    require(
        all(type(row.get("template")) is int and 0 <= row["template"] < len(templates) for row in objects),
        "Invalid template reference",
    )
    indices = [row["index"] for row in objects]
    require(
        all(type(index) is int and index >= 0 for index in indices) and len(set(indices)) == len(indices),
        "Duplicate source identity",
    )


def validateSourceChange(scenario, before, after):
    validateSource(scenario, before)
    validateSource(scenario, after)
    require(
        sameValue(
            {key: value for key, value in before.items() if key != "diagonalRoutes"},
            {key: value for key, value in after.items() if key != "diagonalRoutes"},
        ),
        "Non-route source fields changed",
    )
    old, routes = before["diagonalRoutes"], after["diagonalRoutes"]
    require(len(old) in (scenario.legacyRoutes, scenario.finalRoutes), "Unexpected source route baseline")
    require(len(routes) == scenario.finalRoutes and len(routes) <= 64, "Final route count/budget changed")
    require(sameValue(routes[: len(old)], old), "Legacy route prefix changed")
    blocked = {tuple(point) for point in after["blockedCells"]}
    for index, route in enumerate(routes):
        required_keys = {"kind", "from", "to"} | ({"adaptation"} if index >= scenario.legacyRoutes else set())
        require(set(route) == required_keys and route["kind"] == "diagonalPassage", "Unexpected route shape")
        if index >= scenario.legacyRoutes:
            require(route["adaptation"] == "requiredActorAccess", "Unclassified new route")
        first, second = route["from"], route["to"]
        require(
            all(
                isinstance(point, list) and len(point) == 3 and all(type(value) is int for value in point)
                for point in (first, second)
            ),
            "Invalid passage coordinate",
        )
        require(
            first[2] == second[2] and abs(first[0] - second[0]) == abs(first[1] - second[1]) == 1, "Nonadjacent passage"
        )
        for x, y, z in (first, second):
            require(0 <= x < scenario.width and 0 <= y < scenario.width and 0 <= z < 2, "Passage outside source")
            require(
                after["terrain"][z][x + y * scenario.width][0] not in (8, 9) and (x, y, z) not in blocked,
                "Passage is not ordinary traversable land",
            )
    return routes[len(old) :]


def expectedPortals(scenario, source):
    result = {}
    offset = len(source["portals"]) + len(source["boatRoutes"])
    for index, route in enumerate(source["diagonalRoutes"]):
        if index < scenario.legacyRoutes:
            continue
        for direction, origin, target in (("A", route["from"], route["to"]), ("B", route["to"], route["from"])):
            name = scenario.mapId + "Portal" + str(offset + index) + direction
            result[name] = (
                "Castle campaign " + str(origin[2]),
                {
                    "name": name,
                    "type": "castlePortal",
                    "x": origin[0] * 32,
                    "y": origin[1] * 32,
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
                },
            )
    return result


def validateMapChange(scenario, source, before, after):
    require(
        sameValue(
            {key: value for key, value in before.items() if key not in ("layers", "nextobjectid")},
            {key: value for key, value in after.items() if key not in ("layers", "nextobjectid")},
        ),
        "Map header/tileset/terrain changed",
    )
    require(len(before["layers"]) == len(after["layers"]), "Layer count changed")
    old_objects, new_objects = {}, {}
    for old_layer, new_layer in zip(before["layers"], after["layers"]):
        require(
            sameValue(
                {key: value for key, value in old_layer.items() if key != "objects"},
                {key: value for key, value in new_layer.items() if key != "objects"},
            ),
            "Layer fields/terrain changed",
        )
        old_rows, new_rows = old_layer.get("objects", []), new_layer.get("objects", [])
        names = {row["name"] for row in old_rows}
        require(
            sameValue(old_rows, [row for row in new_rows if row["name"] in names]),
            "Legacy object fields/order/identity changed",
        )
        require(sameValue(old_rows, new_rows[: len(old_rows)]), "New objects were not appended last")
        for rows, objects, layer in ((old_rows, old_objects, old_layer), (new_rows, new_objects, new_layer)):
            for row in rows:
                require(row["name"] not in objects, "Duplicate object name")
                objects[row["name"]] = (layer.get("name"), row)
    for objects in (old_objects, new_objects):
        ids = [row["id"] for _, row in objects.values()]
        require(
            all(type(value) is int and value > 0 for value in ids) and len(ids) == len(set(ids)),
            "Duplicate/invalid numeric object ID",
        )
    expected = expectedPortals(scenario, source)
    require(set(new_objects) == set(old_objects) | set(expected), "Unexpected added/deleted object")
    for name, (layer, row) in expected.items():
        actual_layer, actual = new_objects[name]
        require(
            actual_layer == layer and sameValue({key: value for key, value in actual.items() if key != "id"}, row),
            "New portal fields/placement changed",
        )
    additions = [new_objects[name][1] for name in expected if name not in old_objects]
    next_id = before["nextobjectid"]
    require(
        type(next_id) is int and next_id > max((row["id"] for _, row in old_objects.values()), default=0),
        "Invalid old nextobjectid",
    )
    require(
        [row["id"] for row in additions] == list(range(next_id, next_id + len(additions))),
        "New IDs were not allocated last",
    )
    require(
        type(after["nextobjectid"]) is int and after["nextobjectid"] == next_id + len(additions),
        "Unexpected nextobjectid change",
    )
    return additions


def serialize(source, native_map):
    return (
        (json.dumps(source, separators=(",", ":")) + "\n").encode(),
        (json.dumps(native_map, indent=2) + "\n").encode(),
    )


def computeScenario(scenario, old_source, old_map, tileset, build_native, author_map):
    validateSource(scenario, old_source)
    source = copy.deepcopy(old_source)
    native_map = author_map(build_native(source, copy.deepcopy(tileset)), source)
    routes = validateSourceChange(scenario, old_source, source)
    additions = validateMapChange(scenario, source, old_map, native_map)
    require(len(additions) == 2 * len(routes), "Source/map update stages disagree")
    replay_source = copy.deepcopy(source)
    replay_map = author_map(build_native(replay_source, copy.deepcopy(tileset)), replay_source)
    encoded = serialize(source, native_map)
    require(serialize(replay_source, replay_map) == encoded, "Stored-source replay is not idempotent")
    require(len(encoded[0]) < 600_000 and len(encoded[1]) <= 8 * MIB, "Output file budget exceeded")
    if scenario.mapId == "castleGuardianAngels":
        require(sameValue(source, old_source) and sameValue(native_map, old_map), "Guardian Angels changed")
    return encoded, {
        "mapId": scenario.mapId,
        "oldRoutes": len(old_source["diagonalRoutes"]),
        "finalRoutes": len(source["diagonalRoutes"]),
        "addedRoutes": routes,
        "addedObjects": additions,
        "legacyObjectsSourceAndTerrainExact": True,
        "replayIdempotent": True,
    }


def loadAuthoring(root):
    modules = []
    for name in ("import_castle_campaign", "author_castle_campaign"):
        path = safePath(root, "scripts/" + name + ".py")
        spec = importlib.util.spec_from_file_location("stored_castle_" + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def run(root, temporary, check=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Real stored-source regeneration is CI-only")
    requireCapacity(root, temporary)
    verifyTracked(root)
    raw = {}
    for relative in OUTPUTS:
        path = safePath(root, relative)
        limit = 600_000 if "/sources/" in relative else 8 * MIB
        require(
            path.stat().st_size < limit if "/sources/" in relative else path.stat().st_size <= limit,
            "Input file budget exceeded",
        )
        raw[relative] = path.read_bytes()
    require(sum(map(len, raw.values())) <= AGGREGATE_LIMIT, "Aggregate input budget exceeded")
    tileset_path = safePath(root, "res/maps/multilevel/map.json")
    require(tileset_path.stat().st_size <= MIB, "Tileset input budget exceeded")
    tileset = json.loads(tileset_path.read_bytes())["tilesets"][0]
    tileset["tileproperties"]["5"]["type"] = "castleRoadTile"
    for index, tile_type in ((13, "castleRiverTile"), (14, "castleBridgeTile")):
        tileset["tileproperties"][str(index)] = {"type": tile_type}
        tileset["tilepropertytypes"][str(index)] = {"type": "string"}
    importer, author = loadAuthoring(root)
    require(importer.CAMPAIGN_SHA256 == CAMPAIGN_SHA256, "Importer source edition changed")
    outputs, reports = {}, []
    for index, scenario in enumerate(SCENARIOS):
        source_path, map_path = OUTPUTS[index * 2 : index * 2 + 2]
        encoded, report = computeScenario(
            scenario,
            json.loads(raw[source_path]),
            json.loads(raw[map_path]),
            tileset,
            importer.buildNativeMap,
            author.authorMap,
        )
        outputs.update(zip((source_path, map_path), encoded))
        if scenario.mapId == "castleGuardianAngels":
            require(encoded == (raw[source_path], raw[map_path]), "Guardian Angels raw bytes changed")
        reports.append(report)
    require(sum(map(len, outputs.values())) <= AGGREGATE_LIMIT, "Aggregate output budget exceeded")
    changed = [path for path in OUTPUTS if outputs[path] != raw[path]]
    report = {
        "kind": "StoredCastleResourceReview",
        "scenarios": reports,
        "changedFiles": changed,
        "before": {path: fingerprint(data) for path, data in raw.items()},
        "after": {path: fingerprint(data) for path, data in outputs.items()},
        "originalArchivesRead": False,
        "nativeExecuted": False,
        "mcpExecuted": False,
        "sourceOrOriginalAcceptance": False,
        "resourceDiffAccepted": False,
        "checkOnly": check,
    }
    encoded_report = (json.dumps(report, indent=2) + "\n").encode()
    require(len(encoded_report) <= 256 * 1024, "Logical report budget exceeded")
    if check:
        require(not changed, "Stored Castle resources are stale")
    else:
        requireCapacity(root, temporary)
        for path, data in outputs.items():
            safePath(root, path).write_bytes(data)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare serialized outputs without writing resources")
    args = parser.parse_args()
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Real stored-source regeneration is CI-only")
    sys.dont_write_bytecode = True
    report = run(Path(__file__).resolve().parents[1], Path(os.environ["RUNNER_TEMP"]).resolve(strict=True), args.check)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
