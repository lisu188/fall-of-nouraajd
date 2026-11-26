# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""City-local environment artwork contracts; no native gameplay or original-art parity credit."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unittest

from scripts import build_baldurs_gate_city as builder

ROOT = Path(__file__).resolve().parents[1]
MAP_ROOT = ROOT / "res/maps/baldursGate"
# Test-owned source identities and old paths are independent of the production appearance table.
REVIEWED_BUILDING_TARGETS = {
    "timberHouse": {
        "cityAr0100Portal4": "AR0162",
        "cityAr0100Portal5": "AR0157",
        "cityAr0100Portal9": "AR0167",
        "cityAr0600Portal1": "AR0617",
        "cityAr0600Portal9": "AR0619",
        "cityAr0700Portal11": "AR0715",
        "cityAr0800Portal9": "AR0805",
        "cityAr1200Portal8": "AR1213",
        "cityAr1200Portal11": "AR1209",
        "cityAr1200Portal12": "AR1211",
        "cityAr1300Portal2": "AR1312",
        "cityAr1300Portal18": "AR0813",
    },
    "stoneTownhouse": {
        "cityAr0100Portal1": "AR0101",
        "cityAr0100Portal8": "AR0161",
        "cityAr0700Portal20": "AR0143",
        "cityAr0700Portal5": "AR0719",
        "cityAr0700Portal6": "AR0719",
    },
    "merchantShop": {
        "cityAr0800Portal8": "AR0803",
        "cityAr0800Portal11": "AR0809",
        "cityAr0800Portal12": "AR0810",
        "cityAr1100Portal3": "AR1115",
        "cityAr1100Portal6": "AR1112",
        "cityAr1100Portal13": "AR1116",
        "cityAr1100Portal14": "AR1117",
        "cityAr1300Portal6": "AR1320",
        "cityAr1300Portal8": "AR1302",
        "cityAr1300Portal9": "AR1302",
    },
    "innTavern": {
        "cityAr0100Portal7": "AR0116",
        "cityAr0200Portal9": "AR0119",
        "cityAr0300Portal3": "AR0114",
        "cityAr0300Portal4": "AR0103",
        "cityAr0700Portal3": "AR0720",
        "cityAr0700Portal4": "AR0720",
        "cityAr0800Portal5": "AR0154",
        "cityAr0800Portal10": "AR0705",
        "cityAr1100Portal2": "AR1113",
        "cityAr1100Portal8": "AR1109",
        "cityAr1200Portal7": "AR1215",
        "cityAr1300Portal1": "AR0105",
    },
    "magicShop": {"cityAr0800Portal6": "AR0703"},
    "temple": {"cityAr0200Portal1": "AR0002", "cityAr0600Portal7": "AR0131", "cityAr1200Portal5": "AR0609"},
    "cityGate": {"cityAr0800Boundary18": "AR0900"},
    "guardBarracks": {"cityAr1100Portal1": "AR0607"},
    "ducalPalace": {"cityAr0200Portal13": "AR0108"},
    "guildhall": {"cityAr1100Portal5": "AR0127", "cityAr1100Portal4": "AR0601", "cityAr0300Portal6": "AR0307"},
    "dockWarehouse": {
        "cityAr1200Portal9": "AR1207",
        "cityAr1200Portal10": "AR1208",
        "cityAr1300Portal11": "AR1303",
        "cityAr0700Portal2": "AR0721",
    },
}
REVIEWED_TILE_ASSETS = (
    "streetCobble",
    "flagstonePaving",
    "packedEarth",
    "grassCourtyard",
    "woodenFloor",
    "marbleFloor",
    "dungeonFlagstone",
    "sewerWalkway",
    "sewerWater",
    "riverWater",
    "stoneWall",
    "rockWall",
)


def reviewedEnvironmentAnimations():
    result = {
        name: (
            "maps/baldursGate/images/buildings/" + appearance,
            "images/misc/signpost" if appearance == "cityGate" else "images/buildings/town_hall",
        )
        for appearance, targets in REVIEWED_BUILDING_TARGETS.items()
        for name in targets
    }
    result.update(
        {
            "cityStreetTile": ("maps/baldursGate/images/tiles/streetCobble", "images/tiles/road"),
            "cityWallTile": ("maps/baldursGate/images/tiles/stoneWall", "images/tiles/wasteland"),
        }
    )
    return result


def normalizeEnvironmentAnimations(config):
    for name, (current, original) in reviewedEnvironmentAnimations().items():
        if config[name]["properties"].get("animation") != current:
            raise ValueError("Unexpected reviewed City environment animation: " + name)
        config[name]["properties"]["animation"] = original


def readJson(path):
    return json.loads(path.read_text(encoding="utf-8"))


class BaldursGateCityEnvironmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = readJson(ROOT / "tests/fixtures/baldurs_gate_city_source.json")
        cls.document, cls.config, cls.geometry = builder.compileCity(deepcopy(cls.source))

    def testOnlyReviewedOutdoorLandmarksReceiveBuildingSprites(self):
        expected = reviewedEnvironmentAnimations()
        self.assertEqual(55, len(expected))
        actual = {
            name: row["properties"]["animation"]
            for name, row in self.config.items()
            if row.get("properties", {}).get("animation", "").startswith("maps/baldursGate/images/buildings/")
        }
        self.assertEqual(
            {name: paths[0] for name, paths in expected.items() if "Portal" in name or "Boundary" in name}, actual
        )
        for appearance, targets in REVIEWED_BUILDING_TARGETS.items():
            for name, destination in targets.items():
                with self.subTest(name=name):
                    row = self.config[name]
                    properties = row["properties"]
                    self.assertEqual("BaldursGatePortal", row["class"])
                    self.assertEqual(name[4:10].upper(), properties["sourceArea"])
                    self.assertEqual(destination, properties["destinationArea"])
                    self.assertEqual("exterior", self.source["areas"][properties["sourceArea"]]["classification"])
                    if appearance == "cityGate":
                        self.assertEqual("east", properties["sourceDirection"])
                    else:
                        self.assertEqual("interior", self.source["areas"][destination]["classification"])

    def testTwoExistingTileRecipesChangeOnlyTheirTextureReferences(self):
        self.assertNotIn("GroundTile", self.config, "City artwork must not shadow the global ground recipe")
        expected = {
            "cityStreetTile": {
                "class": "CTile",
                "properties": {
                    "animation": "maps/baldursGate/images/tiles/streetCobble",
                    "canStep": True,
                    "label": "City paving",
                    "tileType": "cityStreet",
                },
            },
            "cityWallTile": {
                "class": "CTile",
                "properties": {
                    "animation": "maps/baldursGate/images/tiles/stoneWall",
                    "canStep": False,
                    "label": "City masonry",
                    "tileType": "cityWall",
                },
            },
        }
        for name, row in expected.items():
            self.assertEqual(row, self.config[name])
        types = self.document["tilesets"][0]["tileproperties"]
        self.assertEqual("cityStreetTile", types["5"]["type"])
        self.assertEqual("GroundTile", types["9"]["type"])
        self.assertEqual("cityWallTile", types["11"]["type"])
        self.assertNotIn("staticTerrainData", self.document["properties"])
        for layer in self.document["layers"]:
            if layer["type"] == "tilelayer":
                self.assertEqual({6, 12} if layer["properties"]["level"] == "0" else {10, 12}, set(layer["data"]))

    def testEnvironmentPassIsDeterministicAndChangesNoNonAppearanceFields(self):
        self.assertTrue(callable(getattr(builder, "applyCityEnvironmentAppearances", None)))
        config = dict(reversed(list(deepcopy(self.config).items())))
        before, source = deepcopy(config), deepcopy(self.source)
        assets = builder.applyCityEnvironmentAppearances(source, config)
        self.assertEqual(assets, builder.applyCityEnvironmentAppearances(source, config))
        self.assertEqual(before, config)
        normalizeEnvironmentAnimations(before)
        normalizeEnvironmentAnimations(config)
        self.assertEqual(before, config)
        self.assertEqual(self.source, source)
        for name, (_current, original) in reviewedEnvironmentAnimations().items():
            config[name]["properties"]["animation"] = original
        legacy = deepcopy(config)
        builder.applyCityEnvironmentAppearances(source, config)
        normalizeEnvironmentAnimations(config)
        self.assertEqual(legacy, config)

    def testEnvironmentValidationFailsBeforeChangingAnyOtherTarget(self):
        for mutation in ("missing", "interior", "wrongClass", "wrongGate"):
            config, source = deepcopy(self.config), deepcopy(self.source)
            if mutation == "missing":
                del config["cityAr0200Portal13"]
            elif mutation == "interior":
                config["cityAr0200Portal13"]["properties"]["sourceArea"] = "AR0108"
            elif mutation == "wrongClass":
                config["cityWallTile"]["class"] = "RoadTile"
            else:
                config["cityAr0800Boundary18"]["properties"]["sourceDirection"] = "west"
            before = deepcopy(config)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "Unreviewed City"):
                builder.applyCityEnvironmentAppearances(source, config)
            self.assertEqual(before, config)

    def testFrozenGameplayGuardStillDetectsNonVisualMutations(self):
        from tests.test_baldurs_gate_city_appearances import digest, withoutAppearance, GAMEPLAY_SHA256_WITH_SEVEN_SUNS

        dialogs = builder.compileDialogs(self.config, readJson(ROOT / "tests/fixtures/baldurs_gate_city_quests.json"))
        for name, field, value in (
            ("cityStreetTile", "canStep", False),
            ("cityWallTile", "tileType", "water"),
            ("cityWallTile", "movementCost", 7),
            ("cityAr0200Portal13", "targetX", -999),
            ("cityAr0200Portal13", "locked", False),
            ("cityPoisonMarek1", "gold", 123456),
            ("cityPoisonMarek1", "sourceInventory", "city-json:[]"),
        ):
            config = deepcopy(self.config)
            config[name]["properties"][field] = value
            with self.subTest(name=name, field=field):
                self.assertNotEqual(
                    GAMEPLAY_SHA256_WITH_SEVEN_SUNS,
                    digest(withoutAppearance(self.document, config, self.geometry, dialogs)),
                )
        config = deepcopy(self.config)
        config["cityAr0200Portal13"]["properties"]["animation"] = "maps/baldursGate/images/buildings/timberHouse"
        with self.assertRaisesRegex(ValueError, "Unexpected reviewed City environment animation"):
            normalizeEnvironmentAnimations(config)
        document = deepcopy(self.document)
        document["layers"][0]["data"][0] = 6
        self.assertNotEqual(
            GAMEPLAY_SHA256_WITH_SEVEN_SUNS,
            digest(withoutAppearance(document, self.config, self.geometry, dialogs)),
        )

    def testDeclarationsIncludeAllTwentyFourEnvironmentAssetsAndOnlyTwoActiveTileTextures(self):
        expected = {
            "images/buildings/" + appearance + ".png" for appearance in (*REVIEWED_BUILDING_TARGETS, "ruinedTemple")
        } | {"images/tiles/" + appearance + ".png" for appearance in REVIEWED_TILE_ASSETS}
        assets = self.document["assets"]
        self.assertEqual(73, len(assets))
        self.assertEqual(assets, sorted(assets, key=lambda row: row["path"]))
        self.assertEqual(len(assets), len({row["path"] for row in assets}))
        environment = [row for row in assets if row["path"].startswith(("images/buildings/", "images/tiles/"))]
        self.assertEqual(expected, {row["path"] for row in environment})
        for row in environment:
            self.assertEqual({"path", "kind"}, set(row))
            self.assertEqual("file", row["kind"])
            path = PurePosixPath(row["path"])
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertEqual(".png", path.suffix)
        active_tiles = {
            row["properties"]["animation"]
            for row in self.config.values()
            if row.get("properties", {}).get("animation", "").startswith("maps/baldursGate/images/tiles/")
        }
        self.assertEqual(
            {"maps/baldursGate/images/tiles/streetCobble", "maps/baldursGate/images/tiles/stoneWall"}, active_tiles
        )


class BaldursGateCityEnvironmentAssetTest(unittest.TestCase):
    def testPromptManifestMatchesEverySelectedPng(self):
        manifest = readJson(ROOT / "docs/art/baldurs_gate_city_environment_prompts.json")
        self.assertEqual(1, manifest["schemaVersion"])
        self.assertEqual(24, len(manifest["assets"]))
        expected = {
            "res/maps/baldursGate/" + row["path"]
            for row in readJson(MAP_ROOT / "map.json")["assets"]
            if row["path"].startswith(("images/buildings/", "images/tiles/"))
        }
        self.assertEqual(expected, {row["path"] for row in manifest["assets"]})
        self.assertEqual(24, len({row["sha256"] for row in manifest["assets"]}))
        for row in manifest["assets"]:
            with self.subTest(asset=row["id"]):
                relative = PurePosixPath(row["path"])
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                raw = (ROOT / row["path"]).read_bytes()
                self.assertEqual(row["bytes"], len(raw))
                self.assertEqual(row["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(row["path"].removeprefix("res/").removesuffix(".png"), row["animation"])
                self.assertTrue(row["creationPrompt"].strip())
                self.assertTrue(all(prompt.strip() for prompt in row["followupPrompts"]))
                self.assertFalse(row["pixelEditsAfterGeneration"])
        self.assertNotRegex(json.dumps(manifest), r"[A-Za-z]:[\\/]")

    def testPngsFitNativePixelBudgetAndUseNativeSafeCornerAlpha(self):
        try:
            from PIL import Image
        except ImportError as error:
            self.skipTest("Existing development Pillow dependency is unavailable: " + str(error))
        native = (ROOT / "src/gui/CTextureCache.cpp").read_text(encoding="utf-8")
        limit = re.search(r"constexpr int MAX_ALPHA_MASK_PIXELS = ([\d']+);", native)
        self.assertIsNotNone(limit)
        pixel_budget = int(limit.group(1).replace("'", ""))
        assets = [
            row
            for row in readJson(MAP_ROOT / "map.json")["assets"]
            if row["path"].startswith(("images/buildings/", "images/tiles/"))
        ]
        self.assertEqual(24, len(assets))
        hashes = set()
        for row in assets:
            path = MAP_ROOT / row["path"]
            with self.subTest(path=row["path"]):
                self.assertTrue(path.is_file())
                raw = path.read_bytes()
                self.assertTrue(raw)
                sha = hashlib.sha256(raw).hexdigest()
                self.assertNotIn(sha, hashes)
                hashes.add(sha)
                with Image.open(path) as image:
                    image.load()
                    self.assertEqual("PNG", image.format)
                    self.assertGreater(image.width, 0)
                    self.assertGreater(image.height, 0)
                    self.assertLessEqual(image.width * image.height, pixel_budget)
                    rgba = image.convert("RGBA")
                    corners = [
                        rgba.getpixel(point)
                        for point in (
                            (0, 0),
                            (image.width - 1, 0),
                            (0, image.height - 1),
                            (image.width - 1, image.height - 1),
                        )
                    ]
                    if row["path"].startswith("images/tiles/"):
                        self.assertEqual((255, 255), rgba.getchannel("A").getextrema())
                        self.assertGreater(
                            len(set(corners)), 1, "Equal opaque corners trigger native color-key masking"
                        )
                    else:
                        self.assertEqual("RGBA", image.mode)
                        self.assertTrue(all(pixel[3] == 0 for pixel in corners))
                        self.assertEqual(0, rgba.getchannel("A").getextrema()[0])
                        self.assertGreater(rgba.getchannel("A").getextrema()[1], 0)


if __name__ == "__main__":
    unittest.main()
