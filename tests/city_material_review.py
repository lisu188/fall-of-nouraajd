# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent area/material decisions and exact cell/recipe conservation for city artwork."""

from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_AREA_MATERIALS = {
    "marbleFloor": "AR0002 AR0101 AR0102 AR0108 AR0109 AR0110 AR0111 AR0130 AR0131 AR0132 AR0609 AR0703 AR0704".split(),
    "flagstonePaving": (
        "AR0127 AR0128 AR0129 AR0307 AR0308 AR0601 AR0602 AR0606 AR0607 AR0608 AR0612 AR0613 AR0614 AR0615 "
        "AR0616 AR0621 AR0721 AR0803 AR0804 AR0809 AR0810 AR1112 AR1115 AR1116 AR1117 AR1207 AR1208 AR1301 "
        "AR1302 AR1303 AR1320"
    ).split(),
    "dungeonFlagstone": "AR0112 AR0125 AR0137 AR0138 AR0139 AR0140 AR0141 AR0142 AR0146 AR0603 AR0611".split(),
    "packedEarth": ["AR0123"],
    "sewerWalkway": "AR0224 AR0225 AR0226".split(),
    "streetCobble": "AR0100 AR0200 AR0300 AR0600 AR0700 AR0800 AR1100 AR1200 AR1300".split(),
    "woodenFloor": (
        "AR0004 AR0005 AR0006 AR0007 AR0008 AR0009 AR0010 AR0011 AR0012 AR0013 AR0014 AR0015 AR0016 AR0017 "
        "AR0018 AR0019 AR0020 AR0021 AR0103 AR0104 AR0105 AR0106 AR0107 AR0114 AR0115 AR0116 AR0117 AR0118 "
        "AR0119 AR0120 AR0121 AR0126 AR0133 AR0134 AR0135 AR0136 AR0143 AR0144 AR0145 AR0148 AR0149 AR0150 "
        "AR0151 AR0152 AR0153 AR0154 AR0155 AR0156 AR0157 AR0158 AR0159 AR0160 AR0161 AR0162 AR0163 AR0164 "
        "AR0165 AR0166 AR0167 AR0168 AR0169 AR0170 AR0171 AR0302 AR0303 AR0304 AR0305 AR0306 AR0617 AR0618 "
        "AR0619 AR0620 AR0702 AR0705 AR0706 AR0707 AR0708 AR0709 AR0710 AR0711 AR0712 AR0713 AR0714 AR0715 "
        "AR0716 AR0717 AR0718 AR0719 AR0720 AR0722 AR0723 AR0724 AR0725 AR0726 AR0801 AR0802 AR0805 AR0806 "
        "AR0807 AR0808 AR0811 AR0812 AR0813 AR0814 AR1101 AR1102 AR1103 AR1104 AR1105 AR1106 AR1107 AR1108 "
        "AR1109 AR1110 AR1111 AR1113 AR1114 AR1201 AR1202 AR1203 AR1204 AR1205 AR1206 AR1209 AR1210 AR1211 "
        "AR1212 AR1213 AR1214 AR1215 AR1304 AR1305 AR1306 AR1307 AR1308 AR1309 AR1310 AR1311 AR1312 AR1313 "
        "AR1314 AR1315 AR1316 AR1317"
    ).split(),
}
REVIEWED_VARIANTS = (
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
ROCK_AREAS = frozenset("AR0123 AR0146 AR0224 AR0225 AR0226".split())
SEWERS = frozenset("AR0224 AR0225 AR0226".split())
BASES = {
    6: {
        "class": "CTile",
        "properties": {
            "animation": "maps/baldursGate/images/tiles/streetCobble",
            "canStep": True,
            "label": "City paving",
            "tileType": "cityStreet",
        },
    },
    10: {
        "class": "CTile",
        "properties": {"animation": "images/tiles/ground", "canStep": True, "label": "Ground", "tileType": "ground"},
    },
    12: {
        "class": "CTile",
        "properties": {
            "animation": "maps/baldursGate/images/tiles/stoneWall",
            "canStep": False,
            "label": "City masonry",
            "tileType": "cityWall",
        },
    },
}


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def reviewedRecipes():
    result = {}
    for gid, (base, material) in enumerate(REVIEWED_VARIANTS, 13):
        name = (
            "cityMaterial" + {6: "Street", 10: "Ground", 12: "Wall"}[base] + material[0].upper() + material[1:] + "Tile"
        )
        value = deepcopy(BASES[base])
        value["properties"]["animation"] = "maps/baldursGate/images/tiles/" + material
        result[gid] = (base, name, value)
    return result


@lru_cache(maxsize=1)
def reviewedMaterialCells():
    source = read("tests/fixtures/baldurs_gate_city_source.json")
    atlas = read("tests/fixtures/baldurs_gate_city_geometry.json")["atlas"]
    baseline = read("tests/fixtures/baldurs_gate_city_material_baseline.json")
    assignments = {area: material for material, areas in REVIEWED_AREA_MATERIALS.items() for area in areas}
    if len(assignments) != 212 or set(assignments) != set(source["areas"]):
        raise ValueError("Reviewed material decisions do not cover every declared area")
    old_cells = {level: [12] * (224 * 192) for level in range(5)}
    expected = deepcopy(old_cells)
    gids = {(base, material): gid for gid, (base, material) in enumerate(REVIEWED_VARIANTS, 13)}
    gids.update({(6, "streetCobble"): 6, (12, "stoneWall"): 12})
    for area_id, facts in source["areas"].items():
        search = facts.get("searchMap")
        raster = []
        if search:
            for encoded in search["terrainRowsRle"]:
                raster.append([terrain for count, terrain in zip(encoded[::2], encoded[1::2]) for _ in range(count)])
        x, y, level, w, h = atlas[area_id]["bounds"]
        for row in range(h):
            for column in range(w):
                samples = []
                if search:
                    samples = [
                        raster[sy][sx]
                        for sy in range(row * 64 // 12, min(math.ceil((row + 1) * 64 / 12), search["height"]))
                        for sx in range(column * 4, min((column + 1) * 4, search["width"]))
                    ]
                passable = [value for value in samples if value not in (0, 8, 10, 12, 13, 14)]
                base = (6 if area_id in source["exteriors"] else 10) if passable or not raster else 12
                counts = Counter(passable if base != 12 else samples)
                dominant = max(counts, key=lambda value: (counts[value], -value)) if counts else None
                if base == 12:
                    material = (
                        ("sewerWater" if area_id in SEWERS else "riverWater")
                        if dominant == 12
                        else ("rockWall" if area_id in ROCK_AREAS else "stoneWall")
                    )
                elif base == 6:
                    if dominant in (5, 15):
                        material = "grassCourtyard"
                    elif dominant == 1:
                        material = "packedEarth"
                    elif dominant in (2, 3, 9):
                        material = "woodenFloor"
                    elif dominant in (6, 11):
                        material = "riverWater"
                    else:
                        material = "streetCobble"
                else:
                    material = "sewerWater" if area_id in SEWERS and dominant in (6, 11) else assignments[area_id]
                index = (y + row) * 224 + x + column
                old_cells[level][index], expected[level][index] = base, gids[base, material]
    for level, cells in old_cells.items():
        digest = hashlib.sha256(json.dumps(cells, separators=(",", ":")).encode()).hexdigest()
        if digest != baseline["layerDataSha256"][str(level)]:
            raise ValueError("Independent source projection no longer reproduces the reviewed legacy cell mask")
    return old_cells, expected, baseline


def normalizeFloorMaterials(document, config, geometry):
    old_cells, expected, baseline = reviewedMaterialCells()
    recipes = reviewedRecipes()
    if document["width"] != 224 or document["height"] != 192 or len(document["tilesets"]) != 1:
        raise ValueError("Unreviewed city material dimensions or palette")
    for gid, (_base, name, recipe) in recipes.items():
        if config.get(name) != recipe:
            raise ValueError("Unreviewed city material recipe: " + name)
    palette = deepcopy(baseline["tilesets"][0])
    for key in ("image", "imagewidth", "imageheight"):
        del palette[key]
    palette["columns"] = 0
    for gid, (_base, name, _recipe) in recipes.items():
        palette["tileproperties"][str(gid - 1)] = {"type": name}
        palette["tilepropertytypes"][str(gid - 1)] = {"type": "string"}
    global_recipes = read("res/config/tiles.json")
    global_recipes.update({"cityStreetTile": BASES[6], "cityWallTile": BASES[12]})
    global_recipes.update({name: recipe for _base, name, recipe in recipes.values()})
    palette["tiles"] = []
    for index, row in sorted(palette["tileproperties"].items(), key=lambda item: int(item[0])):
        animation = global_recipes[row["type"]]["properties"]["animation"]
        path = (
            animation.removeprefix("maps/baldursGate/")
            if animation.startswith("maps/baldursGate/")
            else "../../" + animation
        )
        palette["tiles"].append({"id": int(index), "image": path + ".png"})
    palette["tilecount"] = len(palette["tiles"])
    if document["tilesets"] != [palette]:
        raise ValueError("Unreviewed city material palette")
    observed = set()
    for layer in document["layers"]:
        if layer["type"] != "tilelayer":
            continue
        level = int(layer["properties"]["level"])
        if level in observed or layer["data"] != expected[level]:
            raise ValueError("Unreviewed city material cell assignment: " + str(level))
        observed.add(level)
    if observed != set(expected):
        raise ValueError("Unreviewed city material levels")
    for layer in document["layers"]:
        if layer["type"] == "tilelayer":
            layer["data"] = list(old_cells[int(layer["properties"]["level"])])
    document["tilesets"] = deepcopy(baseline["tilesets"])
    for _base, name, _recipe in recipes.values():
        del config[name]
