# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply declared visual materials without changing native tile/navigation properties."""

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/art/baldurs_gate_city_floor_materials.json"
BLOCKED = frozenset((0, 8, 10, 12, 13, 14))
VARIANTS = (
    (6, "flagstonePaving"),
    (6, "packedEarth"),
    (6, "grassCourtyard"),
    (6, "woodenFloor"),
    (6, "riverWater"),
    (10, "woodenFloor"),
    (10, "flagstonePaving"),
    (10, "marbleFloor"),
    (10, "dungeonFlagstone"),
    (10, "packedEarth"),
    (10, "sewerWalkway"),
    (10, "sewerWater"),
    (10, "riverWater"),
    (12, "rockWall"),
    (12, "sewerWater"),
    (12, "riverWater"),
)


def materialName(base, material):
    return "cityMaterial" + {6: "Street", 10: "Ground", 12: "Wall"}[base] + material[0].upper() + material[1:] + "Tile"


def samplesAt(area, column, row):
    search = area.get("searchMap")
    if not search:
        return Counter()
    result = Counter()
    left, right = column * 4, min((column + 1) * 4, search["width"])
    top, bottom = row * 64 // 12, min(math.ceil((row + 1) * 64 / 12), search["height"])
    for encoded in search["terrainRowsRle"][top:bottom]:
        offset = 0
        for length, terrain in zip(encoded[::2], encoded[1::2]):
            overlap = max(0, min(offset + length, right) - max(offset, left))
            result[terrain] += overlap
            offset += length
    return +result


def materialFor(base, policy, samples):
    if base == 12:
        dominant = min(samples, key=lambda value: (-samples[value], value)) if samples else None
        if dominant == 12:
            return "sewerWater" if policy["role"] == "sewers" else "riverWater"
        return policy["wallMaterial"]
    available = {value: count for value, count in samples.items() if value not in BLOCKED}
    dominant = min(available, key=lambda value: (-available[value], value)) if available else None
    if base == 6:
        return {
            1: "packedEarth",
            2: "woodenFloor",
            3: "woodenFloor",
            5: "grassCourtyard",
            6: "riverWater",
            7: "streetCobble",
            9: "woodenFloor",
            11: "riverWater",
            15: "grassCourtyard",
        }.get(dominant, policy["floorMaterial"])
    if policy["role"] == "sewers" and dominant in (6, 11):
        return "sewerWater"
    return policy["floorMaterial"]


def applyCityFloorMaterials(source, document, config, geometry):
    """Validate all assignments, then alter only appearances and their palette references."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = manifest["areas"]
    if set(rows) != set(source["areas"]) or set(rows) != set(geometry["atlas"]):
        raise ValueError("City material manifest must cover every declared area exactly")
    if "GroundTile" in config or len(document["tilesets"]) != 1 or document["tilesets"][0]["firstgid"] != 1:
        raise ValueError("City materials require the unchanged native palette and global ground recipe")
    globals_ = json.loads((ROOT / "res/config/tiles.json").read_text(encoding="utf-8"))
    bases = {6: config["cityStreetTile"], 10: globals_["GroundTile"], 12: config["cityWallTile"]}
    variants, reverse, definitions = {}, {}, {}
    for gid, (base, material) in enumerate(VARIANTS, 13):
        name = materialName(base, material)
        value = deepcopy(bases[base])
        if value["class"] != "CTile":
            raise ValueError("City materials must retain native CTile behavior")
        value["properties"]["animation"] = "maps/baldursGate/images/tiles/" + material
        if name in config and config[name] != value:
            raise ValueError("City material recipe changed nonvisual properties: " + name)
        definitions[name], variants[base, material], reverse[gid] = value, gid, base
    variants[6, "streetCobble"], variants[12, "stoneWall"] = 6, 12
    layers = {int(layer["properties"]["level"]): layer for layer in document["layers"] if layer["type"] == "tilelayer"}
    changes, assigned = {}, set()
    width = document["width"]
    for area_id, policy in rows.items():
        area = source["areas"][area_id]
        if (policy["areaSha256"], policy["classification"]) != (area["sha256"], area["classification"]):
            raise ValueError("City material source identity changed: " + area_id)
        if policy["searchMapSha256"] != area.get("searchMap", {}).get("sha256"):
            raise ValueError("City material search-map identity changed: " + area_id)
        x, y, level, w, h = geometry["atlas"][area_id]["bounds"]
        for row in range(h):
            for column in range(w):
                index = (y + row) * width + x + column
                key = level, index
                if key in assigned:
                    raise ValueError("City material areas overlap")
                assigned.add(key)
                current = layers[level]["data"][index]
                base = reverse.get(current, current)
                if base not in bases:
                    raise ValueError("Unexpected source city tile")
                material = materialFor(base, policy, samplesAt(area, column, row))
                replacement = variants.get((base, material))
                if replacement is None or current in reverse and current != replacement:
                    raise ValueError("Unreviewed city material assignment: " + area_id)
                changes[key] = replacement
    palette = deepcopy(document["tilesets"][0])
    for key in ("image", "imageheight", "imagewidth"):
        palette.pop(key, None)
    palette["columns"] = 0
    for gid, name in ((variants[base, material], materialName(base, material)) for base, material in VARIANTS):
        palette["tileproperties"][str(gid - 1)] = {"type": name}
        palette["tilepropertytypes"][str(gid - 1)] = {"type": "string"}
    recipes = {**globals_, **config, **definitions}
    palette["tiles"] = [
        {
            "id": int(index),
            "image": recipes[row["type"]]["properties"]["animation"].replace("maps/baldursGate/", "") + ".png",
        }
        for index, row in sorted(palette["tileproperties"].items(), key=lambda item: int(item[0]))
    ]
    for tile in palette["tiles"]:
        if not tile["image"].startswith("images/"):
            raise ValueError("Unexpected city material image path")
        name = palette["tileproperties"][str(tile["id"])]["type"]
        if not recipes[name]["properties"]["animation"].startswith("maps/baldursGate/"):
            tile["image"] = "../../" + tile["image"]
    palette["tilecount"] = len(palette["tiles"])
    for (level, index), replacement in changes.items():
        layers[level]["data"][index] = replacement
    config.update(definitions)
    document["tilesets"] = [palette]
