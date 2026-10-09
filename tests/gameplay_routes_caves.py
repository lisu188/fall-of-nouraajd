# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe ordinary cave callbacks without changing counters or forcing random rolls."""

from functools import lru_cache
import json
from pathlib import Path

RITUAL_ANCHORS = ("anchorNorth", "anchorCrypt", "anchorSanctum")
AMBIENT_CAVES = {
    "nouraajd": "catacombs",
    "ninemarches": "wildEncounter0",
    "vhulmarn": "caveHybridWarren",
    "kadath": "nestLengSpider",
    "sunderedmarch": "pyreGuard",
}


@lru_cache(maxsize=5)
def ambientCaveDefinition(map_name):
    from tests.gameplay_branch_catalog import resolveResource

    root = Path(__file__).resolve().parents[1]
    resources = {}
    for directory in (root / "res/config", root / "res/maps" / map_name):
        for path in sorted(directory.glob("*.json")):
            if path.name == "map.json":
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                resources.update(value)
    document = json.loads((root / "res/maps" / map_name / "map.json").read_text(encoding="utf-8"))
    for layer in document["layers"]:
        if layer.get("type") != "objectgroup":
            continue
        for actor in layer["objects"]:
            if actor.get("name") != AMBIENT_CAVES[map_name]:
                continue
            resource = resolveResource({"ref": actor["type"]}, resources)
            if resource.get("class") != "Cave":
                raise ValueError("The ambient observer requires the actual shared Cave callback")
            properties = {**resource.get("properties", {}), **actor.get("properties", {})}
            result = {
                "name": actor["name"],
                "coords": (
                    int(actor["x"] // document["tilewidth"]),
                    int(actor["y"] // document["tileheight"]),
                    int(layer.get("properties", {}).get("level", 0)),
                ),
                "monsters": int(properties["monsters"]),
                "chance": int(properties["chance"]),
            }
            if not (result["monsters"] > 0 and 0 < result["chance"] <= 100):
                raise ValueError("An ambient spawn witness requires positive authored stock and chance")
            return result
    raise ValueError("Missing ambient cave: " + map_name + ":" + AMBIENT_CAVES[map_name])


def mapIdentities(d):
    return frozenset(actor["__handle__"] for actor in d.call(d.game_map, "getObjects"))


def captureAmbientCave(d):
    """Start only an explicitly declared observer, before the first ordinary map turn."""
    required = {d.map_name + ".cave.timedSpawn", d.map_name + ".cave.exhausted"}
    if d.map_name not in AMBIENT_CAVES or not required <= set(d.case.branches):
        d._ambient_cave = None
        return
    definition = ambientCaveDefinition(d.map_name)
    cave = d.object(definition["name"])
    d.test.assertEqual(0, d.call(d.game_map, "getTurn"), "The ambient cave must be observed before its first turn")
    d.test.assertEqual(definition["coords"], d.coords(cave))
    d.test.assertTrue(d.call(cave, "getBoolProperty", "enabled"))
    for key in ("chance", "monsters"):
        d.test.assertEqual(definition[key], d.call(cave, "getNumericProperty", key))
    template = d.call(cave, "getObjectProperty", "monster")
    d.test.assertIsNotNone(template)
    d._ambient_cave = {
        **definition,
        "cave": cave,
        "map": d.game_map["__handle__"],
        "mapName": d.map_name,
        "templateCoords": d.coords(template),
        "typeId": d.call(template, "getTypeId"),
        "remaining": definition["monsters"],
        "spawnWitnessed": False,
        "zeroTurns": [],
        "complete": False,
        "stage": None,
    }


def beforeAmbientCaveTurn(d):
    observer = getattr(d, "_ambient_cave", None)
    if not observer or observer["complete"]:
        return
    from tests.gameplay_routes_services import nativeCheckpoint

    d.test.assertEqual(observer["map"], d.game_map["__handle__"], "The observed cave's map changed before exhaustion")
    d.test.assertIsNone(observer["stage"], "An ambient-cave turn observer was not completed")
    observer["stage"] = {
        "turn": d.call(d.game_map, "getTurn"),
        "checkpoint": nativeCheckpoint(d),
        "identities": mapIdentities(d) if not observer["spawnWitnessed"] or observer["remaining"] == 0 else None,
    }


def ambientSpawnMovements(d, observer, checkpoint):
    from tests.gameplay_routes_services import nativeEventsSince

    return tuple(
        record
        for record in nativeEventsSince(d, checkpoint, "movement")
        if record.get("committed") is True
        and record.get("object", {}).get("isPlayer") is False
        and record["object"].get("typeId") == observer["typeId"]
        and tuple(record.get("from", {}).get(axis) for axis in "xyz") == observer["templateCoords"]
        and tuple(record.get("to", {}).get(axis) for axis in "xyz") == observer["coords"]
    )


def afterAmbientCaveTurn(d):
    observer = getattr(d, "_ambient_cave", None)
    if not observer or observer["complete"]:
        return
    stage = observer["stage"]
    d.test.assertIsNotNone(stage, "A completed ambient turn needs its prior native checkpoint")
    d.test.assertEqual(observer["map"], d.game_map["__handle__"])
    turn = d.call(d.game_map, "getTurn")
    d.test.assertEqual(stage["turn"] + 1, turn, "Ambient evidence requires one completed ordinary map turn")
    cave = d.object(observer["name"], required=False)
    d.test.assertIsNotNone(cave, "The selected cave was entered before its spawn and exhausted states were witnessed")
    d.test.assertEqual(observer["cave"]["__handle__"], cave["__handle__"])
    remaining = d.call(cave, "getNumericProperty", "monsters")
    decrement = observer["remaining"] - remaining
    d.test.assertIn(decrement, (0, 1), "One Cave.onTurn can consume at most one authored ambient monster")
    d.test.assertGreaterEqual(remaining, 0)
    if decrement == 1 and not observer["spawnWitnessed"]:
        movements = ambientSpawnMovements(d, observer, stage["checkpoint"])
        d.test.assertEqual(1, len(movements), "The decrement needs the actual cave clone's native placement")
        movement = movements[0]
        spawned = d.object(movement["object"]["name"], required=False)
        d.test.assertIsNotNone(spawned, "A fresh matching map identity must accompany the observed cave decrement")
        d.test.assertNotIn(spawned["__handle__"], stage["identities"])
        d.test.assertIn(spawned["__handle__"], mapIdentities(d))
        d.test.assertEqual(observer["typeId"], d.call(spawned, "getTypeId"))
        d.check(
            observer["mapName"] + ".cave.timedSpawn",
            True,
            cave=observer["name"],
            actualTurn=turn,
            remainingBefore=observer["remaining"],
            remainingAfter=remaining,
            spawnedIdentity=spawned["__handle__"],
            nativeMovement=movement,
        )
        observer["spawnWitnessed"] = True
    if observer["remaining"] == 0:
        d.test.assertEqual(0, remaining)
        for movement in ambientSpawnMovements(d, observer, stage["checkpoint"]):
            actor = d.object(movement["object"]["name"], required=False)
            d.test.assertIsNotNone(actor, "An exhausted cave emitted an unaccounted fresh clone placement")
            d.test.assertIn(
                actor["__handle__"], stage["identities"], "An exhausted cave created a fresh matching clone"
            )
        observer["zeroTurns"].append(turn)
        if len(observer["zeroTurns"]) == 2:
            d.test.assertTrue(observer["spawnWitnessed"], "Exhaustion alone cannot prove an actual ambient spawn")
            d.check(
                observer["mapName"] + ".cave.exhausted",
                True,
                cave=observer["name"],
                actualTurns=observer["zeroTurns"],
                remaining=remaining,
            )
            observer["complete"] = True
    observer["remaining"], observer["stage"] = remaining, None


def verifyInactiveRitualCaves(d):
    """The authored anchors cannot create ambient monsters before ritual activation."""
    d.test.assertEqual("ritual", d.map_name)
    d.test.assertFalse(d.flag("ritual_started"))
    d.test.assertFalse(d.flag("ritual_active"))
    d.test.assertEqual(0, d.number("anchors_destroyed_count"))
    anchors = tuple(d.object(name) for name in RITUAL_ANCHORS)
    identities, countdown = mapIdentities(d), d.number("ritual_countdown")
    map_identity = d.game_map["__handle__"]
    turns = []
    for _ in range(2):
        for name, anchor in zip(RITUAL_ANCHORS, anchors):
            d.test.assertEqual(anchor["__handle__"], d.object(name)["__handle__"])
            d.test.assertTrue(d.call(anchor, "getBoolProperty", "enabled"))
            d.test.assertEqual(0, d.call(anchor, "getNumericProperty", "chance"))
            d.test.assertEqual(0, d.call(anchor, "getNumericProperty", "monsters"))
        before = d.call(d.game_map, "getTurn")
        d.tick()
        after = d.call(d.game_map, "getTurn")
        d.test.assertEqual(before + 1, after, "Inactive-cave evidence requires a completed real map turn")
        d.test.assertEqual(map_identity, d.game_map["__handle__"])
        d.test.assertEqual(identities, mapIdentities(d), "An inactive ritual turn created or removed a map actor")
        d.test.assertEqual(countdown, d.number("ritual_countdown"))
        d.test.assertFalse(d.flag("ritual_started"))
        d.test.assertFalse(d.flag("ritual_active"))
        for anchor in anchors:
            d.test.assertEqual(0, d.call(anchor, "getNumericProperty", "monsters"))
        turns.append(after)
    d.check("ritual.cave.inactive", True, anchors=RITUAL_ANCHORS, actualTurns=turns, countdown=countdown)
