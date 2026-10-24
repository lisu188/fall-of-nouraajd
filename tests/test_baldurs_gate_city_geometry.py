# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source/resource geometry checks, without native loading, gameplay credit, or visual acceptance."""

import ast
from collections import Counter, defaultdict, deque
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import re
import unittest

from scripts.build_baldurs_gate_city import decodeCityData

ROOT = Path(__file__).resolve().parents[1]
MAP_ROOT = ROOT / "res/maps/baldursGate"
FIXTURES = ROOT / "tests/fixtures"
WARD_ROWS = (("AR0100", "AR0200", "AR0300"), ("AR0600", "AR0700", "AR0800"), ("AR1100", "AR1200", "AR1300"))


def readJson(path):
    return json.loads(path.read_text(encoding="utf-8"))


def neighbors(point):
    x, y, z = point
    return ((x - 1, y, z), (x + 1, y, z), (x, y - 1, z), (x, y + 1, z))


def labelComponents(walkable):
    """Visit each native collision cell once; portals are deliberately not ordinary transit."""
    labels, expanded, examined = {}, 0, 0
    for seed in sorted(walkable):
        if seed in labels:
            continue
        component = (seed,)
        labels[seed] = component
        pending = deque([seed])
        while pending:
            point = pending.popleft()
            expanded += 1
            for adjacent in neighbors(point):
                examined += 1
                if adjacent in walkable and adjacent not in labels:
                    labels[adjacent] = component
                    pending.append(adjacent)
    return labels, expanded, examined


def resourceName(area_id, kind, index):
    return "city" + area_id.title() + kind + str(index)


def propertyValues(document):
    pending = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.values())
            yield from value.items()
        elif isinstance(value, list):
            pending.extend(value)
            yield from enumerate(value)


class BaldursGateCityGeometryTest(unittest.TestCase):
    def testSourceActorsUseConstructibleNativeCreaturesWithoutAnEmptyPythonSubclass(self):
        tree = ast.parse((MAP_ROOT / "script.py").read_text(encoding="utf-8"))
        self.assertNotIn("BaldursGateActor", {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)})
        actors = [
            (name, row)
            for name, row in self.config.items()
            if row.get("properties", {}).get("sourceActor") and not row.get("properties", {}).get("sourceCorpse")
        ]
        self.assertTrue(actors)
        for name, row in actors:
            self.assertEqual("CCreature", row["class"], name)
            self.assertTrue(row["properties"].get("sourceCreature"), name)
            self.assertIn("sourceInventory", row["properties"], name)
            self.assertIn("sourceItemSlots", row["properties"], name)

    def testTileLayersDeclareNativeBoundsAndBlockedFallback(self):
        for layer in self.document["layers"]:
            if layer["type"] != "tilelayer":
                continue
            with self.subTest(layer=layer["name"]):
                self.assertEqual(str(self.width - 1), layer["properties"].get("xBound"))
                self.assertEqual(str(self.height - 1), layer["properties"].get("yBound"))
                for key in ("default", "outOfBounds"):
                    self.assertEqual("cityWallTile", layer["properties"].get(key))
                for key in ("level", "default", "outOfBounds", "xBound", "yBound"):
                    self.assertEqual("string", layer["propertytypes"].get(key))


    maxDiff = 1200

    @classmethod
    def setUpClass(cls):
        cls.source = readJson(FIXTURES / "baldurs_gate_city_source.json")
        cls.geometry = readJson(FIXTURES / "baldurs_gate_city_geometry.json")
        cls.document = readJson(MAP_ROOT / "map.json")
        cls.config = readJson(MAP_ROOT / "config.json")
        cls.atlas = cls.geometry["atlas"]
        cls.width, cls.height = cls.document["width"], cls.document["height"]
        cls.tile_layers, cls.objects, cls.object_records = {}, {}, []
        for layer in cls.document["layers"]:
            level = int(layer["properties"]["level"])
            if layer["type"] == "tilelayer":
                cls.tile_layers[level] = layer
            elif layer["type"] == "objectgroup":
                for record in layer["objects"]:
                    cls.object_records.append(record)
                    cls.objects[record["name"]] = (
                        int(record["x"] // cls.document["tilewidth"]),
                        int(record["y"] // cls.document["tileheight"]),
                        level,
                    )
        cls.resources = {}
        for path in sorted((ROOT / "res/config").glob("*.json")):
            cls.resources.update(readJson(path))
        cls.resources.update(cls.config)
        cls.tile_types = {
            tileset["firstgid"] + int(index): properties["type"]
            for tileset in cls.document["tilesets"]
            for index, properties in tileset.get("tileproperties", {}).items()
        }
        cls.portal_positions = {
            point for name, point in cls.objects.items() if cls.config[name].get("class") == "BaldursGatePortal"
        }

    def inArea(self, area_id, point):
        x, y, z, width, height = self.atlas[area_id]["bounds"]
        return point[2] == z and x <= point[0] < x + width and y <= point[1] < y + height

    def canStep(self, point):
        x, y, z = point
        if z not in self.tile_layers or not (0 <= x < self.width and 0 <= y < self.height):
            return False
        gid = self.tile_layers[z]["data"][y * self.width + x]
        tile_id = self.tile_types[gid]
        return self.resources[tile_id]["properties"].get("canStep", False)

    def rawPosition(self, area_id, source_point):
        x, y, z, width, height = self.atlas[area_id]["bounds"]
        return (
            x + min(width - 1, max(0, int(source_point[0]) // 64)),
            y + min(height - 1, max(0, int(source_point[1]) // 64)),
            z,
        )

    def canonicalInventory(self, records):
        excluded = self.source.get("editionExcludedItems", {})
        conversions = self.source.get("editionItemConversions", {})
        return [
            dict(record, sourceIndex=index, item=conversions.get(record["item"], {}).get("original", record["item"]))
            for index, record in enumerate(records)
            if record["item"] and record["item"] not in excluded
        ]

    def testEveryAuditedAreaHasBoundedDisjointAtlasRegionAndSourceScale(self):
        self.assertEqual(212, len(self.source["areas"]))
        self.assertEqual(set(self.source["areas"]), set(self.atlas))
        self.assertFalse(set(self.source["excludedAreaResources"]) & set(self.atlas))
        self.assertEqual(64, self.geometry["sourcePixelsPerNativeCell"])
        self.assertEqual({area for row in WARD_ROWS for area in row}, set(self.source["exteriors"]))
        self.assertEqual(9, len(self.source["exteriors"]))
        occupied = {}
        for area_id, metadata in self.atlas.items():
            with self.subTest(area=area_id):
                x, y, z, width, height = metadata["bounds"]
                self.assertTrue(all(type(value) is int for value in (x, y, z, width, height)))
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertGreaterEqual(min(x, y, z), 0)
                self.assertLessEqual(x + width, self.width)
                self.assertLessEqual(y + height, self.height)
                self.assertEqual(
                    [math.ceil(value / 64) for value in self.source["areas"][area_id]["dimensions"]], [width, height]
                )
                self.assertEqual(z == 0, area_id in self.source["exteriors"])
                for row in range(y, y + height):
                    for col in range(x, x + width):
                        point = (col, row, z)
                        self.assertNotIn(point, occupied, (area_id, occupied.get(point), point))
                        occupied[point] = area_id
        for row in WARD_ROWS:
            self.assertEqual(
                sorted(self.atlas[area]["bounds"][0] for area in row), [self.atlas[a]["bounds"][0] for a in row]
            )
        for column in zip(*WARD_ROWS):
            self.assertEqual(
                sorted(self.atlas[area]["bounds"][1] for area in column), [self.atlas[a]["bounds"][1] for a in column]
            )
        for level, layer in self.tile_layers.items():
            self.assertEqual((self.width, self.height), (layer["width"], layer["height"]))
            self.assertEqual(self.width * self.height, len(layer["data"]))
            for row in range(self.height):
                for col in range(self.width):
                    point = (col, row, level)
                    if point not in occupied:
                        self.assertFalse(self.canStep(point), ("Walkable atlas gap joins unrelated areas", point))

    def testAllPlacedSourceActorsAndContainersHaveUniquePersistentIdentityAndExactOwnership(self):
        names = [record["name"] for record in self.object_records]
        identifiers = [record["id"] for record in self.object_records]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(max(identifiers) + 1, self.document["nextobjectid"])
        self.assertEqual(len(self.objects), len(set(self.objects.values())), "Authored interactive cells overlap")
        counts = Counter()
        exclusions = self.source.get("editionExcludedCreatures", {})
        for area_id, area in self.source["areas"].items():
            for kind, records in (("Actor", area["actors"]), ("Container", area["containers"])):
                for index, source_object in enumerate(records, 1):
                    name = resourceName(area_id, kind, index)
                    if kind == "Actor" and source_object["creature"] in exclusions:
                        self.assertNotIn(name, self.objects, "Known expansion actor leaked into the base city")
                        continue
                    with self.subTest(object=name):
                        self.assertIn(name, self.objects)
                        properties = self.config[name]["properties"]
                        self.assertEqual(area_id, properties["sourceArea"])
                        self.assertEqual(area_id, properties["simulationRegion"])
                        self.assertEqual(source_object["sourceId"], properties["source" + kind])
                        self.assertTrue(self.inArea(area_id, self.objects[name]))
                        self.assertTrue(self.canStep(self.objects[name]))
                        if kind == "Container":
                            self.assertEqual(
                                self.canonicalInventory(source_object["items"]), decodeCityData(properties["contents"])
                            )
                            self.assertEqual(source_object["lock_difficulty"], properties["sourceLockDifficulty"])
                            self.assertEqual(bool(source_object["trapped"]), properties["trapped"])
                            self.assertEqual(source_object["key"], properties["sourceKey"])
                        else:
                            self.assertEqual(source_object["creature"], properties["sourceCreature"])
                            creature_id = source_object.get("creatureMetadata", source_object["creature"])
                            creature = self.source["creatures"].get(creature_id, {})
                            if self.config[name]["class"] == "BaldursGateContainer":
                                self.assertEqual(
                                    0, creature["hit_points"], "Only a factual dead actor can become a corpse"
                                )
                                self.assertTrue(properties["sourceCorpse"])
                                self.assertEqual(
                                    self.canonicalInventory(creature.get("items", [])),
                                    decodeCityData(properties["contents"]),
                                )
                                for field in (
                                    "npc",
                                    "controller",
                                    "fightController",
                                    "actions",
                                    "baseStats",
                                    "sourceKillXp",
                                ):
                                    self.assertNotIn(
                                        field, properties, (name, "A corpse must not fight or pay kill experience")
                                    )
                            else:
                                self.assertEqual("CCreature", self.config[name]["class"])
                                self.assertEqual(source_object["schedule"], properties["sourceSchedule"])
                            native_inventory = decodeCityData(properties["sourceInventory"])
                            self.assertEqual(self.canonicalInventory(creature.get("items", [])), native_inventory)
                            self.assertEqual(
                                creature.get("itemSlots", []), decodeCityData(properties["sourceItemSlots"])
                            )
                            index_items = {record["sourceIndex"]: record["item"] for record in native_inventory}
                            self.assertEqual(len(index_items), len(native_inventory))
                            for source_index, item in enumerate(creature.get("items", [])):
                                if item["item"] in self.source.get("editionExcludedItems", {}):
                                    self.assertNotIn(source_index, index_items)
                            self.assertNotIn("items", properties, "Native and deferred item ownership must not overlap")
                        counts[kind] += 1
        excluded_actors = sum(
            actor["creature"] in exclusions for area in self.source["areas"].values() for actor in area["actors"]
        )
        self.assertEqual(self.source["counts"]["actors"] - excluded_actors, counts["Actor"])
        self.assertEqual(self.source["counts"]["containers"], counts["Container"])
        self.assertEqual(
            counts["Actor"] + sum(record["scopeClassification"] == "city" for record in self.source["campaignNpcs"]),
            sum("sourceActor" in self.config[name].get("properties", {}) for name in self.objects),
        )
        self.assertEqual(
            counts["Container"], sum("sourceContainer" in value.get("properties", {}) for value in self.config.values())
        )

    def testScriptedActorBlueprintsRetainSourceProvenanceAndSingleSerializedPlacement(self):
        facts = {record["sourceId"]: record for record in self.source["scriptedActors"]}
        facts.update(
            {record["sourceId"]: dict(record, areas=[record["area"]]) for record in self.source["campaignNpcs"]}
        )
        definitions = decodeCityData(self.config["cityClock"]["properties"]["actorDefinitions"])
        self.assertEqual(definitions, self.geometry["scriptedActorPlacements"])
        self.assertEqual(len(definitions), len({record["id"] for record in definitions}))
        blueprints = {
            name: resource["properties"]
            for name, resource in self.config.items()
            if "sourceSpawnFact" in resource.get("properties", {})
        }
        self.assertEqual(set(blueprints), {record["id"] for record in definitions})
        cells = set(self.objects.values())
        for record in definitions:
            name, area_id = record["id"], record["sourceArea"]
            properties = blueprints[name]
            fact = facts[properties["sourceSpawnFact"]]
            with self.subTest(blueprint=name):
                self.assertNotIn(name, self.objects, "Deferred encounter has an initial actor plus a spawn template")
                self.assertEqual("CCreature", self.config[name]["class"])
                self.assertNotIn(properties["sourceCreature"], self.source["editionExcludedCreatures"])
                self.assertEqual(fact["creature"], properties["sourceCreature"])
                if fact.get("scopeClassification") in {"boundaryHistory", "externalHistory"}:
                    self.assertEqual(fact["area"], properties["sourceOriginalArea"])
                    self.assertEqual(fact["position"], decodeCityData(properties["sourceOriginalPosition"]))
                    self.assertEqual("AR0800", area_id)
                    self.assertTrue(record["requiresFlag"])
                    self.assertTrue(properties["sourceAdaptation"])
                else:
                    self.assertEqual([area_id], fact["areas"])
                self.assertEqual(
                    (record["phase"], record.get("phaseMax", record["phase"])),
                    (properties["phaseMin"], properties["phaseMax"]),
                )
                point = tuple(record[key] for key in ("x", "y", "z"))
                self.assertTrue(self.inArea(area_id, point))
                self.assertTrue(self.canStep(point))
                self.assertNotIn(point, cells)
                cells.add(point)
                creature = self.source["creatures"][properties["sourceCreature"]]
                self.assertEqual(
                    self.canonicalInventory(creature.get("items", [])), decodeCityData(properties["sourceInventory"])
                )

    def testCampaignNpcsUseTheirAuditedCityPlacementsAndKeepActualInventories(self):
        facts = {
            record["sourceId"]: record
            for record in self.source["campaignNpcs"]
            if record["scopeClassification"] == "city"
        }
        actual = {}
        for name, point in self.objects.items():
            properties = self.config[name].get("properties", {})
            source_id = properties.get("sourceGameNpc")
            if not source_id:
                continue
            self.assertNotIn(source_id, actual)
            actual[source_id] = name
            fact = facts[source_id]
            self.assertEqual(fact["area"], properties["sourceArea"])
            self.assertEqual(fact["creature"], properties["sourceCreature"])
            self.assertEqual(source_id, properties["sourceActor"])
            self.assertTrue(self.inArea(fact["area"], point))
            self.assertTrue(self.canStep(point))
            creature = self.source["creatures"][fact["creatureMetadata"]]
            self.assertEqual(
                self.canonicalInventory(creature.get("items", [])), decodeCityData(properties["sourceInventory"])
            )
            raw = self.rawPosition(fact["area"], fact["position"])
            if point != raw:
                self.assertTrue(
                    any(
                        entry["area"] == fact["area"]
                        and entry.get("source") == fact["position"]
                        and tuple(entry["placed"]) == point
                        for entry in self.geometry["placementAdaptations"]
                    )
                )
        self.assertEqual(set(facts), set(actual))

    def testCanonicalActorRelocationsReserveDistinctReachableSourceScenes(self):
        relocations = decodeCityData(self.config["cityClock"]["properties"]["relocationDefinitions"])
        self.assertEqual(relocations, self.geometry["relocationDefinitions"])
        self.assertEqual(len(relocations), len({record["canonicalActorId"] for record in relocations}))
        facts = {record["sourceId"]: record for record in self.source["scriptedActors"]}
        occupied = set(self.objects.values())
        for relocation in relocations:
            actor = self.config[relocation["canonicalActorId"]]
            self.assertEqual("CCreature", actor["class"])
            self.assertEqual(relocation["sourceCreature"], actor["properties"]["sourceCreature"])
            self.assertEqual(len(relocation["scenes"]), len({scene["id"] for scene in relocation["scenes"]}))
            for scene in relocation["scenes"]:
                with self.subTest(actor=relocation["canonicalActorId"], scene=scene["id"]):
                    point = tuple(scene[key] for key in ("x", "y", "z"))
                    fact = facts[scene["sourceSpawnFact"]]
                    self.assertIn(scene["sourceArea"], fact["areas"])
                    self.assertEqual(fact["position"], scene["sourcePosition"])
                    self.assertEqual(fact["conditions"], scene["sourceConditions"])
                    self.assertTrue(self.inArea(scene["sourceArea"], point))
                    self.assertTrue(self.canStep(point))
                    self.assertNotIn(point, occupied, "Relocated actor overlaps authored interaction or another scene")
                    occupied.add(point)

    def testEverySourceDoorRetainsAnOwnedInteractiveOrGeometryRecord(self):
        expected = {
            f"{area_id}#door{index}": (area_id, door)
            for area_id, area in self.source["areas"].items()
            for index, door in enumerate(area["doors"], 1)
        }
        actual = Counter()
        for name, resource in self.config.items():
            properties = resource.get("properties", {})
            source_id = properties.get("sourceDoor")
            if not source_id:
                continue
            with self.subTest(door=name):
                self.assertIn(source_id, expected)
                area_id, door = expected[source_id]
                self.assertIn(name, self.objects)
                self.assertIn(resource["class"], {"BaldursGatePortal", "BaldursGateDoor"})
                self.assertEqual(area_id, properties["sourceArea"])
                for source_key, property_key in (
                    ("name", "sourceDoorName"),
                    ("flags", "sourceDoorFlags"),
                    ("key", "sourceKey"),
                    ("script", "sourceScript"),
                    ("lock_difficulty", "sourceLockDifficulty"),
                    ("trap_detection", "sourceTrapDetection"),
                    ("trap_removal", "sourceTrapRemoval"),
                ):
                    self.assertEqual(door[source_key], properties[property_key])
                self.assertEqual(bool(door["trapped"]), properties["trapped"])
                self.assertEqual(
                    {key: door[key] for key in ("open_polygon", "closed_polygon", "open_impeded", "closed_impeded")},
                    decodeCityData(properties["sourceDoorGeometry"]),
                )
                actual[source_id] += 1
        for record in decodeCityData(self.config["cityClock"]["properties"]["geometryDoors"]):
            source_id = record["sourceDoor"]
            with self.subTest(geometryDoor=source_id):
                self.assertIn(source_id, expected)
                area_id, door = expected[source_id]
                self.assertEqual(area_id, record["sourceArea"])
                self.assertEqual("geometryOnlyNoClickPolygon", record["classification"])
                self.assertEqual(door, {key: record[key] for key in door})
                for key in ("open_polygon", "closed_polygon", "key", "script", "travel_trigger", "trapped"):
                    self.assertFalse(door[key], (source_id, key))
                actual[source_id] += 1
        self.assertEqual(Counter({source_id: 1 for source_id in expected}), actual)
        self.assertEqual(108, len(expected))

    def testSourceSearchMapRasterRetainsTheDocumentedCollisionProjection(self):
        self.assertEqual([16, 12], self.source["searchMapRule"]["sourceCellPixels"])
        blocked = set(self.source["searchMapRule"]["supportingBlockedIndices"])
        checked, impassable = 0, 0
        for area_id, area in self.source["areas"].items():
            search = area["searchMap"]
            raster = []
            self.assertEqual(search["height"], len(search["terrainRowsRle"]))
            for runs in search["terrainRowsRle"]:
                self.assertEqual(0, len(runs) % 2)
                row = []
                for count, terrain in zip(runs[::2], runs[1::2]):
                    self.assertGreater(count, 0)
                    self.assertIn(terrain, range(16))
                    row.extend([terrain] * count)
                self.assertEqual(search["width"], len(row))
                raster.append(row)
            x, y, z, width, height = self.atlas[area_id]["bounds"]
            for row in range(height):
                for col in range(width):
                    point = (x + col, y + row, z)
                    expected = any(
                        raster[source_y][source_x] not in blocked
                        for source_y in range(row * 64 // 12, min(math.ceil((row + 1) * 64 / 12), search["height"]))
                        for source_x in range(col * 4, min((col + 1) * 4, search["width"]))
                    )
                    self.assertEqual(expected, self.canStep(point), (area_id, point))
                    checked += 1
                    impassable += not expected
        self.assertGreater(impassable, 40000, "The source's inaccessible terrain must remain blocked")
        self.assertLessEqual(checked, 85000, "Fixed city geometry exceeded its collision-cell work budget")

    def testEverySourceConnectionHasItsActualDestinationEntranceAndSafeLanding(self):
        expected = {}
        for area_id, area in self.source["areas"].items():
            for index, region in enumerate(area["regions"], 1):
                if not region["destination"]:
                    continue
                name = resourceName(area_id, "Portal", index)
                self.assertIn(name, self.objects)
                properties = self.config[name]["properties"]
                self.assertEqual(region["sourceId"], properties["sourceRegion"])
                self.assertEqual(region["destination"], properties["destinationArea"])
                self.assertEqual(region["entrance"], properties["sourceEntrance"])
                if region["destination"] in self.atlas:
                    destination = self.source["areas"][region["destination"]]
                    entrance = next(
                        e for e in destination["entrances"] if e["name"].casefold() == region["entrance"].casefold()
                    )
                    expected[name] = (area_id, region["destination"], entrance["position"])
        for index, link in enumerate(self.source["worldMapLinks"], 1):
            name = resourceName(link["source"], "Boundary", index)
            self.assertIn(name, self.objects)
            properties = self.config[name]["properties"]
            self.assertEqual(link["entrance"], properties["sourceEntrance"])
            self.assertEqual(link["direction"], properties["sourceDirection"])
            self.assertEqual(link["travel_time_quarters"], properties["sourceTravelTimeQuarters"])
            if link["destination"] in self.atlas:
                expected[name] = (link["source"], link["destination"], link["destinationPosition"])
            else:
                self.assertFalse(any(key in properties for key in ("targetX", "targetY", "targetZ")))
        actual = {link["object"]: link for link in self.geometry["connections"]}
        self.assertEqual(len(actual), len(self.geometry["connections"]))
        self.assertEqual(set(expected), set(actual))
        adaptations = {
            (entry["area"], tuple(entry["source"]), tuple(entry["placed"]))
            for entry in self.geometry["placementAdaptations"]
            if "source" in entry
        }
        object_adaptations = {
            (entry["area"], entry["object"], tuple(entry["placed"]))
            for entry in self.geometry["placementAdaptations"]
            if "object" in entry
        }
        for entry in self.geometry["placementAdaptations"]:
            self.assertTrue(entry["reason"])
            self.assertTrue(self.inArea(entry["area"], tuple(entry["initial"])))
            self.assertTrue(self.inArea(entry["area"], tuple(entry["placed"])))
        for name, (origin_area, destination_area, source_point) in expected.items():
            with self.subTest(portal=name):
                link, properties = actual[name], self.config[name]["properties"]
                target = tuple(properties[key] for key in ("targetX", "targetY", "targetZ"))
                self.assertEqual((origin_area, destination_area), (link["from"], link["to"]))
                self.assertEqual(self.objects[name], tuple(link["origin"]))
                self.assertEqual(target, tuple(link["target"]))
                self.assertTrue(self.inArea(origin_area, self.objects[name]))
                self.assertTrue(self.inArea(destination_area, target))
                self.assertTrue(self.canStep(self.objects[name]))
                self.assertTrue(self.canStep(target))
                self.assertNotIn(target, self.portal_positions, "Landing triggers another authored portal")
                if target != self.rawPosition(destination_area, source_point):
                    self.assertTrue(
                        (destination_area, tuple(source_point), target) in adaptations
                        or (destination_area, name, target) in object_adaptations,
                        (name, destination_area, source_point, target),
                    )

    def testSourcePalaceLockAndChapterSevenUndergroundGatesRemainExplicit(self):
        underground, palace = [], []
        for link in self.geometry["connections"]:
            properties = self.config[link["object"]]["properties"]
            if link["to"] in {"AR0146", "AR0123", "AR0125"}:
                underground.append(link["object"])
                self.assertEqual(7, properties["phaseMin"], link["object"])
                self.assertEqual("palaceCleared", properties["requiredFlag"], link["object"])
            if link["from"] == "AR0200" and link["to"] == "AR0108":
                palace.append(link["object"])
                self.assertTrue(properties["locked"])
                self.assertEqual(12, properties["lockAgility"])
                self.assertEqual("MISC78", properties["lockKey"])
        self.assertTrue(underground)
        self.assertTrue(palace)

    def testChapterSevenDeparturesRequireTheAuditedDestroySelfScriptAndCannotBeOverridden(self):
        rule = self.source["scriptSourceRules"]["LEAVECH7.BCS"]
        self.assertEqual({"global": "Chapter", "scope": "GLOBAL", "equals": 7}, rule["condition"])
        self.assertEqual(["DestroySelf"], rule["actions"])
        self.assertEqual(self.source["references"]["LEAVECH7.BCS"]["sha256"], rule["sha256"])
        self.assertRegex(rule["sha256"], r"^[0-9a-f]{64}$")
        sources = {actor["sourceId"]: actor for area in self.source["areas"].values() for actor in area["actors"]}
        sources.update({actor["sourceId"]: actor for actor in self.source["campaignNpcs"]})
        departures = []
        for name, resource in self.config.items():
            properties = resource.get("properties", {})
            if not properties.get("sourceActor"):
                continue
            actor = sources.get(properties["sourceActor"], {})
            creature_id = actor.get("creatureMetadata", properties["sourceCreature"])
            creature = self.source["creatures"][creature_id]
            if "LEAVECH7" not in (*actor.get("scripts", []), *creature.get("scripts", [])):
                self.assertNotIn("sourceDepartureScript", properties, name)
                continue
            departures.append(name)
            self.assertEqual("LEAVECH7", properties["sourceDepartureScript"], name)
            self.assertEqual(5, properties["phaseMax"], name)
            self.assertLessEqual(properties.get("phaseMin", 5), 5, name)
        self.assertTrue(departures)
        path = ROOT / "scripts/build_baldurs_gate_city.py"
        spec = importlib.util.spec_from_file_location("city_departure_generator", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for field, value in (
            ("condition", {"global": "Chapter", "scope": "GLOBAL", "equals": 6}),
            ("actions", []),
            ("sha256", "0" * 64),
        ):
            with self.subTest(mutation=field):
                source = deepcopy(self.source)
                source["scriptSourceRules"]["LEAVECH7.BCS"][field] = value
                with self.assertRaisesRegex(ValueError, "departure rule requires a new behavior audit"):
                    module.compileCity(source)

    def testNativeCollisionComponentsReachEveryInteractionWithoutWalkingThroughPortals(self):
        labels, expanded, examined, allocated = {}, 0, 0, 0
        for area_id, metadata in self.atlas.items():
            x, y, z, width, height = metadata["bounds"]
            allocated += width * height
            walkable = {
                (col, row, z)
                for row in range(y, y + height)
                for col in range(x, x + width)
                if self.canStep((col, row, z)) and (col, row, z) not in self.portal_positions
            }
            components, visits, checks = labelComponents(walkable)
            self.assertEqual(len(walkable), visits)
            self.assertEqual(4 * visits, checks)
            expanded += visits
            examined += checks
            labels.update({point: (area_id, component) for point, component in components.items()})
        self.assertLessEqual(expanded, allocated)
        self.assertEqual(4 * expanded, examined)
        self.assertLessEqual(expanded, 40000, "City collision flood-fill exceeded its deterministic cell budget")
        self.assertLessEqual(examined, 160000, "City collision flood-fill exceeded its deterministic edge budget")
        self.assertLessEqual(len(set(labels.values())), 300, "Unexpected fragmented or duplicated atlas regions")
        edges = defaultdict(set)
        for link in self.geometry["connections"]:
            target = labels.get(tuple(link["target"]))
            if target is None:
                continue
            for adjacent in neighbors(tuple(link["origin"])):
                source = labels.get(adjacent)
                if source and source[0] == link["from"]:
                    edges[source].add(target)
        entry = tuple(int(self.document["properties"][key]) for key in ("x", "y", "z"))
        self.assertIn(entry, labels)
        reachable, pending, graph_visits = {labels[entry]}, deque([labels[entry]]), 0
        while pending:
            graph_visits += 1
            for destination in edges[pending.popleft()]:
                if destination not in reachable:
                    reachable.add(destination)
                    pending.append(destination)
        self.assertLessEqual(graph_visits, len(set(labels.values())))
        self.assertEqual(set(self.atlas), {area for area, _component in reachable})
        missing = [
            name
            for name, point in self.objects.items()
            if self.config[name]["class"] in {"CCreature", "BaldursGateContainer", "BaldursGateDoor"}
            and labels.get(point) not in reachable
        ]
        missing.extend(
            record["id"]
            for record in decodeCityData(self.config["cityClock"]["properties"]["actorDefinitions"])
            if labels.get(tuple(record[key] for key in ("x", "y", "z"))) not in reachable
        )
        missing.extend(
            relocation["canonicalActorId"] + ":" + scene["id"]
            for relocation in decodeCityData(self.config["cityClock"]["properties"]["relocationDefinitions"])
            for scene in relocation["scenes"]
            if labels.get(tuple(scene[key] for key in ("x", "y", "z"))) not in reachable
        )
        self.assertEqual([], missing, "Static native collision leaves authored interactions inaccessible")

    def testNativeAssetsReferencesScriptClassesAndResourceStagingExist(self):
        missing_assets = set()
        for key, value in propertyValues(self.config):
            if key == "animation":
                path = ROOT / "res" / value
                if not path.exists() and not path.with_suffix(".png").is_file():
                    missing_assets.add(value)
            elif key == "ref":
                self.assertIn(value, self.resources)
        self.assertEqual(set(), missing_assets)
        script_path = MAP_ROOT / "script.py"
        self.assertTrue(script_path.is_file(), "The generated runtime classes need a staged city script")
        tree = ast.parse(script_path.read_text(encoding="utf-8"))
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        required = {
            entry["class"] for entry in self.config.values() if entry.get("class", "").startswith("BaldursGate")
        }
        self.assertTrue(required <= classes.keys(), required - classes.keys())
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        for name in ("map.json", "config.json", "script.py"):
            self.assertTrue(
                re.search(rf"configure_file\(\s*res/maps/baldursGate/{re.escape(name)}\b", cmake),
                f"Missing CMake staging for res/maps/baldursGate/{name}",
            )
        staged = re.search(r"set\(GAME_STAGED_MAPS\s+(.*?)\)", cmake, flags=re.DOTALL)
        self.assertIsNotNone(staged)
        self.assertIn("baldursGate", staged.group(1).split())

    def testCompilationIsDeterministicAndSerializedRecordCountsDoNotShrink(self):
        path = ROOT / "scripts/build_baldurs_gate_city.py"
        spec = importlib.util.spec_from_file_location("city_geometry_generator", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        document, config, geometry = module.compileCity(self.source)
        restored = json.loads(json.dumps({"map": document, "config": config, "geometry": geometry}))
        self.assertTrue(self.document == restored["map"], "Saved map is stale relative to factual compiler inputs")
        self.assertTrue(
            self.geometry == restored["geometry"], "Geometry provenance is stale relative to compiler inputs"
        )
        self.assertTrue(
            self.config == restored["config"], "Generated resource identities and ownership must be reproducible"
        )
        records = [
            obj for layer in restored["map"]["layers"] if layer["type"] == "objectgroup" for obj in layer["objects"]
        ]
        self.assertEqual(len(self.object_records), len(records))
        self.assertEqual(212, len(restored["geometry"]["atlas"]))
        source_actor_count = sum(
            actor["creature"] not in self.source["editionExcludedCreatures"]
            for area in self.source["areas"].values()
            for actor in area["actors"]
        )
        source_actor_count += sum(record["scopeClassification"] == "city" for record in self.source["campaignNpcs"])
        actor_templates = decodeCityData(restored["config"]["cityClock"]["properties"]["actorDefinitions"])
        self.assertEqual(
            source_actor_count + len(actor_templates),
            sum("sourceActor" in obj.get("properties", {}) for obj in restored["config"].values()),
        )
        self.assertEqual(
            self.source["counts"]["containers"],
            sum("sourceContainer" in obj.get("properties", {}) for obj in restored["config"].values()),
        )

    def testSourceFixtureAndResourcesRetainFactsWithoutPrivatePathsOrOriginalDumps(self):
        self.assertFalse(self.source["originalParityEstablished"])
        self.assertFalse(self.geometry["sourceParityEstablished"])
        for key in ("keySha256", "tlkSha256", "worldMapSha256"):
            self.assertRegex(self.source[key], r"^[0-9a-f]{64}$")
        for name, resource in self.source["references"].items():
            self.assertTrue(
                set(resource)
                <= {
                    "sha256",
                    "size",
                    "origin",
                    "states",
                    "transitions",
                    "storeReferences",
                    "displayName",
                    "overrideDiffers",
                },
                name,
            )
        forbidden = {"tlkStrings", "dialogueDump", "binaryData", "base64", "gameRoot", "installationPath"}
        for document in (self.source, self.geometry, self.config, self.document):
            for key, value in propertyValues(document):
                self.assertNotIn(key, forbidden)
                if isinstance(value, str):
                    self.assertFalse(
                        re.search(r"(?<![A-Za-z])(?:[A-Za-z]:[\\/]|/home/|/Users/|\\\\Users\\)", value), key
                    )
        binary_extensions = {".are", ".bif", ".biff", ".bcs", ".cre", ".dlg", ".itm", ".sto", ".tlk", ".wed"}
        self.assertFalse([path.name for path in MAP_ROOT.rglob("*") if path.suffix.lower() in binary_extensions])
        self.assertFalse(
            [
                path.name
                for path in MAP_ROOT.glob("*.json")
                if path.name not in {"map.json", "config.json", "dialog.json"}
            ]
        )


if __name__ == "__main__":
    unittest.main()
