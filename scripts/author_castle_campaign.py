# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Populate imported Castle geography without changing its terrain or footprints.

The Heroes importer calls authorMap after converting the user's local campaign.
Only gameplay markers are authored here; no original images, dialogue, or audio
are read or copied. Source object indexes provide deterministic resource names.
"""

import copy
import json

RANDOM_MONSTER_REPRESENTATIVES = {71: 70, 72: 70, 73: 72, 74: 74, 75: 78, 162: 80, 163: 80, 164: 54}

SCENARIOS = {
    "homecoming": {
        "mapId": "castleHomecoming",
        "reward": 200,
        "nextMap": "castleGuardianAngels",
        "intro": "Catherine's expedition has landed. Speak with Catherine and Christian, take supplies at loyal "
        "strongholds, and capture Terraneus beneath the central hills. Defeat its garrison before claiming the town.",
    },
    "guardianAngels": {
        "mapId": "castleGuardianAngels",
        "reward": 300,
        "nextMap": "castleGriffinCliff",
        "intro": "The angels' homeland is divided by the invasion. Capture all four enemy strongholds and defeat "
        "all four enemy commanders. Friendly angels and loyal settlements offer supplies along the way.",
    },
    "griffinCliff": {
        "mapId": "castleGriffinCliff",
        "reward": 400,
        "nextMap": "",
        "intro": "Catherine needs the griffins. Defeat the guards at each of the seven northern Griffin Towers, "
        "then claim their banners. Other towns and enemy commanders are optional objectives.",
    },
}


def isEnemy(source_object):
    return source_object.get("owner", 255) not in (0, 255)


def authoredObjectives(source_data):
    scenario_id = source_data["scenarioId"]
    objects = source_data["objects"]
    if scenario_id == "homecoming":
        target = source_data["victory"]["target"]
        selected = [obj for obj in objects if obj["type"] in (77, 98) and obj["visit"] == target]
        if len(selected) != 1:
            raise ValueError("Homecoming must identify one Terraneus town at the original victory coordinate")
    elif scenario_id == "guardianAngels":
        selected = [obj for obj in objects if obj["type"] in (77, 98) and isEnemy(obj)]
        if len(selected) != 4:
            raise ValueError("Guardian Angels must retain its four source enemy strongholds")
    elif scenario_id == "griffinCliff":
        selected = [obj for obj in objects if obj["type"] == 17 and obj["subtype"] == 25]
        if len(selected) != 7:
            raise ValueError("Griffin Cliff must retain exactly seven source Griffin Towers")
    else:
        raise ValueError("Unknown Castle campaign scenario: " + scenario_id)
    return selected


def creatureArt(creature_id):
    if 0 <= creature_id <= 13:
        return ("pikeman", "marksman", "griffin", "swordsman", "monk", "cavalier", "angel")[creature_id // 2]
    if 70 <= creature_id <= 77:
        return "troglodyte"
    if 78 <= creature_id <= 83:
        return "minotaur"
    if 54 <= creature_id <= 55:
        return "devil"
    return "demon"


def compressedArmy(source_object, chapter, elite=False, griffin=False):
    """One representative per source army, with a bounded encounter budget.

    Hero armies and town garrisons become one defender each, rather than a
    strategic stack system. Quantity affects its strength within a small band;
    source random quantities (zero) receive the deterministic minimum.
    """
    army = source_object.get("army") or []
    total = sum(max(0, stack.get("count", 0)) for stack in army)
    quantity_bonus = min(3, total // 30)
    rank = chapter + quantity_bonus + int(elite)
    creature_id = (
        4 if griffin else RANDOM_MONSTER_REPRESENTATIVES.get(source_object["type"], army[0]["creature"] if army else 70)
    )
    stamina = 3 + rank
    return {
        "label": "Griffin Tower defender" if griffin else ("Invading commander" if elite else "Occupation garrison"),
        "animation": "images/castle/" + creatureArt(creature_id),
        "description": (
            "A vigilant defender of the occupied griffin roost."
            if griffin
            else "An armed invader holding the roads and strongholds of Erathia."
        ),
        "campaign_sourceArmy": "castleArmy:" + json.dumps(army, separators=(",", ":")),
        "campaign_sourceIndex": source_object["index"],
        "campaign_sourceType": source_object["type"],
        "campaign_representativeCreature": creature_id,
        "baseStats": {
            "class": "CStats",
            "properties": {
                "mainStat": "strength",
                "stamina": stamina,
                "strength": 2 + rank,
                "agility": 2 + rank,
                "intelligence": 2,
                "hit": 65 + min(rank, 5),
                "crit": 0,
                "dmgMin": 2 + rank,
                "dmgMax": 4 + rank,
            },
        },
        "hp": stamina * 7,
        "level": max(1, chapter),
        "gold": 5 + rank * 3,
        "actions": [{"ref": "Attack"}],
    }


def authorMap(map_data, source_data):
    """Return a populated native map; never write files or reshape geography."""
    result = copy.deepcopy(map_data)
    scenario_id = source_data["scenarioId"]
    scenario = SCENARIOS[scenario_id]
    map_id = scenario["mapId"]
    chapter = tuple(SCENARIOS).index(scenario_id) + 1
    source_objects = source_data["objects"]
    required = {obj["index"] for obj in authoredObjectives(source_data)}
    tower_numbers = {
        obj["index"]: index + 1
        for index, obj in enumerate(sorted(authoredObjectives(source_data), key=lambda item: item["visit"][0]))
    }
    generated_layers = {}
    result["layers"] = [layer for layer in result["layers"] if not layer.get("name", "").startswith("Castle campaign ")]
    existing_ids = [obj.get("id", 0) for layer in result["layers"] for obj in layer.get("objects", [])]
    next_id = max(existing_ids, default=0) + 1
    reserved = set()

    def addObject(name, type_id, coords, properties=None):
        nonlocal next_id
        x, y, z = coords
        if not (0 <= x < source_data["width"] and 0 <= y < source_data["height"] and 0 <= z < source_data["layers"]):
            raise ValueError(f"Object {name} is outside source bounds: {coords}")
        if z not in generated_layers:
            generated_layers[z] = {
                "type": "objectgroup",
                "name": f"Castle campaign {z}",
                "draworder": "topdown",
                "opacity": 1,
                "visible": True,
                "properties": {"level": str(z)},
                "objects": [],
            }
        obj = {
            "id": next_id,
            "name": name,
            "type": type_id,
            "x": x * 32,
            "y": y * 32,
            "width": 32,
            "height": 32,
            "visible": True,
            "rotation": 0,
            "properties": properties or {},
        }
        next_id += 1
        generated_layers[z]["objects"].append(obj)
        reserved.add(tuple(coords))
        return obj

    capture_ids, objective_ids, defender_ids, enemy_hero_ids = [], [], [], []
    for source_object in source_objects:
        index = source_object["index"]
        kind = source_object["type"]
        coords = source_object["visit"]
        is_tower = kind == 17 and source_object["subtype"] == 25 and scenario_id == "griffinCliff"
        if kind in (77, 98) or is_tower:
            if source_object.get("owner") == 0 and not is_tower:
                addObject(map_id + "Supply" + str(index), "castleSupply", coords, {"label": "Loyal Castle stronghold"})
                continue
            object_id = map_id + "Objective" + str(index)
            guard_id = map_id + "Guard" + str(index)
            label = "Griffin Tower " + str(tower_numbers[index]) if is_tower else "Occupied stronghold"
            if scenario_id == "homecoming" and index in required:
                label = "Terraneus"
            addObject(
                object_id,
                "castleObjective",
                coords,
                {
                    "label": label,
                    "animation": "images/castle/" + ("griffinTower" if is_tower else "castleTown"),
                    "campaign_objectiveId": object_id,
                    "campaign_sourceIndex": index,
                    "campaign_guards": guard_id,
                    "campaign_rewardGold": 50,
                },
            )
            guard_properties = compressedArmy(source_object, chapter, griffin=is_tower)
            guard_properties["label"] = label + " defender"
            addObject(guard_id, "castleGarrison", coords, guard_properties)
            capture_ids.append(object_id)
            defender_ids.append(guard_id)
            if index in required:
                objective_ids.append(object_id)
        elif kind in (34, 70) and isEnemy(source_object):
            actor_id = map_id + "EnemyHero" + str(index)
            addObject(actor_id, "castleGarrison", coords, compressedArmy(source_object, chapter, elite=True))
            defender_ids.append(actor_id)
            if scenario_id == "guardianAngels":
                enemy_hero_ids.append(actor_id)
        elif kind == 54 or kind in RANDOM_MONSTER_REPRESENTATIVES:
            if source_object.get("disposition") == 0:
                art = creatureArt(RANDOM_MONSTER_REPRESENTATIVES.get(kind, source_object.get("subtype", 0)))
                addObject(
                    map_id + "Ally" + str(index),
                    "castleSupply",
                    coords,
                    {
                        "label": "Friendly " + art,
                        "animation": "images/castle/" + art,
                        "campaign_aidMessage": (
                            "An angel folds its wings beside you. Light closes your wounds, and a healing draught "
                            "is placed in your hands. The angels will stand with Catherine and Erathia."
                            if art == "angel"
                            else "The loyal soldiers share their medicine and dress your wounds before the next march."
                        ),
                    },
                )
            else:
                actor_id = map_id + "Encounter" + str(index)
                addObject(actor_id, "castleGarrison", coords, compressedArmy(source_object, chapter))
                defender_ids.append(actor_id)

    if scenario_id == "guardianAngels" and len(enemy_hero_ids) != 4:
        raise ValueError("Guardian Angels must retain its four invading commanders")

    routes = source_data.get("portals", []) + source_data.get("boatRoutes", []) + source_data.get("diagonalRoutes", [])
    for index, portal in enumerate(routes):
        if portal.get("kind") == "whirlpool":
            continue
        for direction, origin, target in (("A", portal["from"], portal["to"]), ("B", portal["to"], portal["from"])):
            kind = portal.get("kind", "boat")
            addObject(
                map_id + "Portal" + str(index) + direction,
                "castlePortal",
                origin,
                {
                    "label": (
                        "Narrow passage"
                        if kind == "diagonalPassage"
                        else ("Expedition ferry" if kind in ("boat", "ferry", "whirlpool") else "Passage")
                    ),
                    "animation": (
                        "images/footprint"
                        if kind == "diagonalPassage"
                        else "images/buildings/" + ("stairs_down" if kind == "crossZ" else "teleporter")
                    ),
                    "campaign_portalKind": kind,
                    "campaign_targetX": target[0],
                    "campaign_targetY": target[1],
                    "campaign_targetZ": target[2],
                },
            )

    tile_layers = {
        int(layer["properties"]["level"]): layer for layer in result["layers"] if layer["type"] == "tilelayer"
    }
    tile_types = result["tilesets"][0]["tileproperties"]

    def passable(coords):
        x, y, z = coords
        layer = tile_layers.get(z)
        if not layer or not (0 <= x < layer["width"] and 0 <= y < layer["height"]):
            return False
        gid = layer["data"][x + y * layer["width"]]
        tile_type = tile_types.get(str(gid - 1), {}).get("type", layer["properties"].get("default", "GrassTile"))
        return tile_type not in ("WaterTile", "MountainTile")

    spawn = source_data["spawn"]
    if not passable(spawn):
        raise ValueError("Original hero arrival must remain walkable")
    reserved.add(tuple(spawn))
    for officer, art in (("Catherine", "catherine"), ("Christian", "christian")):
        candidates = [
            (spawn[0] + dx, spawn[1] + dy, spawn[2])
            for radius in range(1, 5)
            for dy in range(-radius, radius + 1)
            for dx in range(-radius, radius + 1)
            if max(abs(dx), abs(dy)) == radius
        ]
        location = next(
            (candidate for candidate in candidates if candidate not in reserved and passable(candidate)), None
        )
        if location is None:
            raise ValueError("No unoccupied ground for " + officer + " beside the original arrival")
        addObject(
            "castle" + officer,
            "castleOfficer",
            location,
            {"label": officer, "animation": "images/castle/" + art, "campaign_dialog": "castle" + officer + "Dialog"},
        )

    support_units = {
        "homecoming": ("pikeman", "marksman", "swordsman"),
        "guardianAngels": ("monk", "angel"),
        "griffinCliff": ("griffin", "cavalier"),
    }
    for art in support_units[scenario_id]:
        candidates = [
            (spawn[0] + dx, spawn[1] + dy, spawn[2])
            for radius in range(1, 6)
            for dy in range(-radius, radius + 1)
            for dx in range(-radius, radius + 1)
            if max(abs(dx), abs(dy)) == radius
        ]
        location = next(
            (candidate for candidate in candidates if candidate not in reserved and passable(candidate)), None
        )
        if location is None:
            raise ValueError("No unoccupied arrival ground for allied " + art)
        addObject(
            map_id + "Support" + art.title(),
            "castleSupply",
            location,
            {
                "label": "Allied " + art,
                "animation": "images/castle/" + art,
                "campaign_rewardGold": 0,
                "campaign_aidMessage": (
                    "The angel raises a shining hand. Your wounds close, and a healing draught is offered for the "
                    "road. Erathia's cause now has friends in the skies."
                    if art == "angel"
                    else "Catherine's allies tend your wounds and give you a healing draught from the expedition stores."
                ),
            },
        )

    mission = {
        "scenarioId": scenario_id,
        "questId": map_id + "Quest",
        "objectiveIds": objective_ids,
        "captureIds": capture_ids,
        "defenderIds": defender_ids,
        "enemyHeroIds": enemy_hero_ids,
        "victoryGold": scenario["reward"],
        "nextMap": scenario["nextMap"],
        "intro": scenario["intro"],
    }
    mission_object = addObject(
        "castleMission",
        "castleMission",
        spawn,
        {"campaign_mission": "castleMission:" + json.dumps(mission, separators=(",", ":"))},
    )
    # Register named triggers before defenders receive any possible onCreate event.
    mission_layer = generated_layers[spawn[2]]["objects"]
    mission_layer.remove(mission_object)
    mission_layer.insert(0, mission_object)
    result["layers"].extend(generated_layers[level] for level in sorted(generated_layers))
    result["nextobjectid"] = next_id
    return result
