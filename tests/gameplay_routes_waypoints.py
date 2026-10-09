# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe authored connector publication before and after actual map turns."""

from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAYPOINT_MAPS = frozenset({"ninemarches", "sunderedmarch", "test"})


@lru_cache(maxsize=3)
def waypointDefinitions(map_name):
    from tests.gameplay_branch_catalog import resolveResource

    resources = {}
    for directory in (ROOT / "res/config", ROOT / "res/maps" / map_name):
        for path in sorted(directory.glob("*.json")):
            if path.name == "map.json":
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                resources.update(value)
    document = json.loads((ROOT / "res/maps" / map_name / "map.json").read_text(encoding="utf-8"))
    actors, seen = {}, set()
    for layer in document["layers"]:
        if layer.get("type") != "objectgroup":
            continue
        for actor in layer["objects"]:
            name, type_id = actor.get("name", ""), actor.get("type", "")
            resolved = resolveResource({"ref": type_id}, resources) if type_id in resources else {"class": type_id}
            class_id = resolved.get("class", type_id)
            if class_id in {"Teleporter", "GroundHole"}:
                properties = {**resolved.get("properties", {}), **actor.get("properties", {})}
                enabled = properties.get("enabled", False)
                if isinstance(enabled, str):
                    enabled = enabled.lower() == "true"
                coords = (
                    int(actor["x"] / actor["width"]),
                    int(actor["y"] / actor["height"]),
                    int(layer.get("properties", {}).get("level", 0)),
                )
                exit_name = properties.get("exit", "")
                actors[name] = {
                    "name": name,
                    "class": class_id,
                    "coords": coords,
                    "enabled": bool(enabled) if class_id == "Teleporter" else True,
                    "exit": exit_name,
                    "targetAvailableOnCreate": exit_name in seen if class_id == "Teleporter" else True,
                }
            seen.add(name)
    for actor in actors.values():
        if actor["class"] == "GroundHole":
            x, y, z = actor["coords"]
            actor["target"] = (x, y, z - 1)
        else:
            target = actors.get(actor["exit"])
            actor["target"] = target["coords"] if target else None
            if actor["enabled"] and target is None:
                raise ValueError("Missing authored teleporter target: " + map_name + ":" + actor["name"])
    return tuple(actors.values())


def waypointSnapshot(d, definitions, *, creation):
    result = []
    for definition in definitions:
        name, source, target = definition["name"], definition["coords"], definition["target"]
        actor = d.object(name)
        d.test.assertEqual(source, d.coords(actor))
        available = definition["enabled"] and (not creation or definition["targetAvailableOnCreate"])
        if available:
            d.test.assertIsNotNone(target)
            d.test.assertTrue(d.canStep(target), ("Authored waypoint landing is blocked", name, target))
        published = d.call(actor, "getBoolProperty", "waypoint")
        d.test.assertIs(available, published, ("Waypoint publication state", name, creation))
        neighbors = tuple(
            tuple(value) for value in d.call(d.game_map, "getNavigationNeighbors", d._coordinateHandle(source))
        )
        if not available:
            x, y, z = source
            ordinary = {(x - 1, y, z), (x + 1, y, z), (x, y - 1, z), (x, y + 1, z)}
            d.test.assertEqual(
                ordinary, set(neighbors), ("Unpublished connector added a navigation target", name, creation)
            )
        if target is not None:
            d.test.assertTrue(
                source[2] != target[2] or sum(abs(a - b) for a, b in zip(source, target)) > 1,
                "An ordinary adjacent neighbor cannot prove publication of a connector edge",
            )
            d.test.assertEqual(int(available), neighbors.count(target), ("Observable connector target", name, creation))
        if available:
            stored = tuple(d.call(actor, "getNumericProperty", axis) for axis in "xyz")
            d.test.assertEqual(target, stored)
        result.append({"name": name, "published": published, "target": target, "observableTargetCount": int(available)})
    return tuple(result)


def captureWaypointCreation(d):
    """Called after startMap's initial pump, before any route can advance a turn."""
    if d.map_name not in WAYPOINT_MAPS:
        return
    turn = d.call(d.game_map, "getTurn")
    d.test.assertEqual(0, turn, "Creation publication must be captured before the first real map turn")
    definitions = waypointDefinitions(d.map_name)
    d.test.assertTrue(definitions)
    d._waypoint_creation = {
        "map": d.game_map["__handle__"],
        "turn": turn,
        "records": waypointSnapshot(d, definitions, creation=True),
    }


def verifyWaypointPublication(d):
    """A real later turn must repair forward references and retain enabled targets."""
    creation = getattr(d, "_waypoint_creation", None)
    d.test.assertIsNotNone(creation, "The initial native connector snapshot is required")
    d.test.assertEqual(d.game_map["__handle__"], creation["map"])
    turn = d.call(d.game_map, "getTurn")
    d.test.assertGreater(turn, creation["turn"], "Publication needs an actual authored map turn")
    records = waypointSnapshot(d, waypointDefinitions(d.map_name), creation=False)
    d.check(
        d.map_name + ".waypoint.published",
        True,
        creation=creation["records"],
        afterTurn=turn,
        afterTurnRecords=records,
        proof="Native neighbor targets are deduplicated; this does not count internal edge records.",
    )
