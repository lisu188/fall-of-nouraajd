# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

MODULE_PATH = Path(__file__).resolve().parents[1] / "recovery/upstream/resources/reconstruct_resources.py"
SPEC = importlib.util.spec_from_file_location("history_resources", MODULE_PATH)
resources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resources)


class HistoricalResourceConversionTest(unittest.TestCase):
    def testTiledConversionPreservesEveryCellObjectAndTypedProperty(self):
        source = {
            "width": 2,
            "height": 2,
            "tilewidth": 32,
            "tileheight": 32,
            "orientation": "orthogonal",
            "properties": {"x": "1", "y": "0"},
            "tilesets": [
                {
                    "firstgid": 1,
                    "name": "terrain",
                    "tilewidth": 32,
                    "tileheight": 32,
                    "tileproperties": {"0": {"type": "GrassTile"}},
                }
            ],
            "layers": [
                {"type": "tilelayer", "name": "Terrain", "width": 2, "height": 2, "data": [1, 2, 3, 4]},
                {
                    "type": "objectgroup",
                    "name": "Objects",
                    "objects": [
                        {
                            "id": 1,
                            "name": "cave1",
                            "type": "Cave",
                            "x": 32,
                            "y": 64,
                            "properties": {"enabled": True, "chance": "10"},
                        }
                    ],
                },
            ],
        }
        root = ET.fromstring(resources.tiledXml(source))
        self.assertEqual(["1", "2", "3", "4"], [tile.get("gid") for tile in root.findall("layer/data/tile")])
        cave = root.find("objectgroup/object")
        self.assertEqual(("cave1", "Cave", "32", "64"), tuple(cave.get(key) for key in ("name", "type", "x", "y")))
        self.assertEqual("true", cave.find("properties/property[@name='enabled']").get("value"))
        self.assertEqual("GrassTile", root.find("tileset/tile/properties/property").get("value"))

    def testPrototypeAdaptationRetainsObservedStatsAndAnimationPath(self):
        original = {"class": "CArmor", "properties": {"animation": "images/items/armor", "bonus": {"armor": 375}}}
        result = resources.flattenPrototype(original)
        self.assertEqual("Armor", result["class"])
        self.assertEqual("images/items/armor/", result["path"])
        self.assertEqual({"armor": 375}, result["bonus"])
        self.assertEqual("CArmor", original["class"])


if __name__ == "__main__":
    unittest.main()
