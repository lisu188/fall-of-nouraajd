# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""City appearance source/model and resource checks; these do not award native or source-parity credit."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_baldurs_gate_city as builder
from tests.test_baldurs_gate_city_environment import normalizeEnvironmentAnimations

ROOT = Path(__file__).resolve().parents[1]
MAP_ROOT = ROOT / "res/maps/baldursGate"
PREFIX = "maps/baldursGate/images/npc/"
# The reviewed Seven Suns integration adds its stock, warning quest and dialogue metadata to the ff0b baseline.
# Tamoko dc857585 + c735c1b7 were independently merged against c68f22b1 before extending this baseline.
# That union changes three journal definitions, Tamoko options and two quest definitions only.
# Restore reviewed environment paths and remove source actor artwork/assets; all gameplay fields remain frozen.
GAMEPLAY_SHA256_WITH_SEVEN_SUNS = "3c60eb657a34894c39a898444861db2ad28b16e77e0144b65b9f61c29ae9219e"


def readJson(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sourceActors(config):
    return {
        name: row
        for name, row in config.items()
        if row.get("properties", {}).get("sourceCreature")
        and (
            row.get("class") == "CCreature"
            or (row.get("class") == "BaldursGateContainer" and row["properties"].get("sourceCorpse"))
        )
    }


def withoutAppearance(document, config, geometry, dialogs):
    document, config = deepcopy(document), deepcopy(config)
    document.pop("assets", None)
    normalizeEnvironmentAnimations(config)
    for row in sourceActors(config).values():
        row["properties"].pop("animation", None)
    return {"map": document, "config": config, "geometry": geometry, "dialogs": dialogs}


class BaldursGateCityAppearanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = readJson(ROOT / "tests/fixtures/baldurs_gate_city_source.json")
        cls.quests = readJson(ROOT / "tests/fixtures/baldurs_gate_city_quests.json")
        cls.document, cls.config, cls.geometry = builder.compileCity(deepcopy(cls.source))
        cls.dialogs = builder.compileDialogs(cls.config, cls.quests)

    def requireAppearanceHelper(self):
        self.assertTrue(callable(getattr(builder, "applyCityAppearances", None)), "A final appearance pass is required")
        return builder.applyCityAppearances

    def testNamedActorsUseAuditedRolesInsteadOfOneSharedHumanSprite(self):
        expected = {
            "cityAr0100Actor43": "guardMan",
            "cityAr0002Actor1": "priestMan",
            "cityAr0105Actor2": "priestWoman",
            "cityAr0100Actor3": "nobleMan",
            "cityAr0012Actor1": "boy",
            "cityAr0162Actor1": "girl",
            "cityAr0004Actor1": "elfMan",
            "cityAr0132Actor2": "elfWoman",
            "cityAr0157Actor1": "dwarfMan",
            "cityAr0167Actor1": "dwarfWoman",
            "cityAr0116Actor5": "halflingMan",
            "cityCampaignNpc1": "halflingWoman",
            "cityCampaignNpc13": "gnomeMan",
            "cityAr0005Actor2": "cat",
            "cityAr0224Actor10": "rat",
            "cityAr0706Actor1": "merchantWoman",
            "cityAr0153Actor5": "rogueWoman",
            "cityAr0703Actor2": "mageMan",
        }
        for name, role in expected.items():
            with self.subTest(actor=name, role=role):
                self.assertEqual(PREFIX + role, self.config[name]["properties"]["animation"])
        self.assertEqual("CATP", self.config["cityAr0005Actor2"]["properties"]["sourceCreature"])
        self.assertEqual("Angel the Cat", self.config["cityAr0005Actor2"]["properties"]["label"])

    def testGuardAndStorePrecedencePreserveActualSourcePresentationAndDisguises(self):
        guard = self.config["cityAr0100Actor43"]["properties"]
        priest = self.config["cityAr0002Actor1"]["properties"]
        self.assertEqual("FLAMGATE", guard["sourceCreature"])
        self.assertEqual("PRIHEL", priest["sourceCreature"])
        self.assertEqual(PREFIX + "guardMan", guard["animation"])
        self.assertEqual(PREFIX + "priestMan", priest["animation"])
        expected = {
            "cityAr0706Actor1": ("ALYTH", "merchantWoman"),
            "cityAr0153Actor5": ("BLACKL", "rogueWoman"),
            "cityAr0703Actor2": ("HALBAZ", "mageMan"),
        }
        for name, (code, role) in expected.items():
            with self.subTest(actor=name):
                properties = self.config[name]["properties"]
                self.assertEqual(code, properties["sourceCreature"])
                self.assertTrue(properties.get("sourceStore") or properties.get("sourceStores"))
                self.assertEqual(PREFIX + role, properties["animation"])
        for suffix in ("", "1", "2", "3", "4", "5"):
            with self.subTest(disguise=suffix):
                properties = self.config["cityAr0108ScriptActorNoblpa" + suffix]["properties"]
                self.assertEqual("NOBLPA" + suffix, properties["sourceCreature"])
                self.assertEqual(PREFIX + "nobleMan", properties["animation"])
        self.assertFalse(
            any("player" in row["properties"]["animation"].lower() for row in sourceActors(self.config).values())
        )

    def testFinalPassReachesTheActualPoisonFactoryClonesAndTheSourceCorpse(self):
        from tests.test_baldurs_gate_city_content import CityModel

        expected = {
            "cityPoisonMarek1": ("MAREK1", "mageMan"),
            "cityPoisonLothander": ("LOTHAN", "rogueMan"),
            "cityPoisonTenya2": ("TENYA2", "priestWoman"),
        }
        model = CityModel()
        model.resources.update(deepcopy(self.config))
        instances = []
        for name, (code, role) in expected.items():
            with self.subTest(factory=name):
                properties = self.config[name]["properties"]
                self.assertEqual(code, properties["sourceCreature"])
                self.assertEqual(name, properties["sourceActor"])
                self.assertEqual(PREFIX + role, properties["animation"])
                instance = model.createObject(name)
                instances.append(instance)
                self.assertEqual(code, instance.getStringProperty("sourceCreature"))
                self.assertEqual(PREFIX + role, instance.getStringProperty("animation"))
        self.assertEqual(3, len({id(instance) for instance in instances}))
        corpses = [
            row["properties"]
            for row in self.config.values()
            if row.get("class") == "BaldursGateContainer"
            and row.get("properties", {}).get("sourceCreature")
            and row["properties"].get("sourceCorpse")
        ]
        self.assertEqual(1, len(corpses))
        self.assertEqual("EMITAR2", corpses[0]["sourceCreature"])
        self.assertEqual(PREFIX + "corpse", corpses[0]["animation"])

    def testOnlySourceActorAppearanceAndDeclaredAssetsDifferFromFrozenGameplay(self):
        actors = sourceActors(self.config)
        self.assertEqual(1327, len(actors.keys() - {"citySevenSunsRevealedDoppss"}))
        self.assertEqual(PREFIX + "doppelganger", actors["citySevenSunsRevealedDoppss"]["properties"]["animation"])
        self.assertEqual(
            GAMEPLAY_SHA256_WITH_SEVEN_SUNS,
            digest(withoutAppearance(self.document, self.config, self.geometry, self.dialogs)),
            "Actor identity, ownership, stats, placement, schedules, quests, dialogue and collision must remain intact",
        )
        apply = self.requireAppearanceHelper()
        config = deepcopy(self.config)
        name = "cityPoisonMarek1"
        config[name]["properties"].update(
            gold=321,
            sourceInventory='city-json:[{"item":"DAGG01","sourceIndex":7}]',
            sourceSchedule=12345,
        )
        config[name]["properties"]["baseStats"]["properties"]["strength"] = 91
        before = deepcopy(config)
        apply(self.source, config)
        for key, row in sourceActors(before).items():
            row["properties"].pop("animation")
            changed = deepcopy(config[key])
            changed["properties"].pop("animation")
            self.assertEqual(row, changed, key)
        untouched = self.config.keys() - sourceActors(self.config).keys()
        self.assertEqual({key: before[key] for key in untouched}, {key: config[key] for key in untouched})

    def testAppearanceCoverageIsCompleteStableAndIndependentOfInputOrdering(self):
        apply = self.requireAppearanceHelper()
        groups = builder.CITY_APPEARANCE_SOURCE_GROUPS
        codes = [code for values in groups.values() for code in values]
        self.assertEqual(425, len(codes))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(
            {row["properties"]["sourceCreature"] for row in sourceActors(self.config).values()}, set(codes)
        )
        source = deepcopy(self.source)
        source["creatures"] = dict(reversed(list(source["creatures"].items())))
        before_source = deepcopy(source)
        config = dict(reversed(list(deepcopy(self.config).items())))
        reversed_groups = {key: list(reversed(values)) for key, values in reversed(list(groups.items()))}
        with patch.object(builder, "CITY_APPEARANCE_SOURCE_GROUPS", reversed_groups):
            assets = apply(source, config)
        self.assertEqual(self.config, config)
        self.assertEqual([row for row in self.document["assets"] if row["path"].startswith("images/npc/")], assets)
        self.assertEqual(before_source, source)
        self.assertEqual(assets, apply(source, config), "Reapplying appearance must be idempotent")

    def testSourceFingerprintOrDuplicateEvidenceFailsBeforeChangingActorState(self):
        apply = self.requireAppearanceHelper()
        for mutation in ("changed", "added", "removed"):
            with self.subTest(mutation=mutation):
                source = deepcopy(self.source)
                if mutation == "changed":
                    source["creatures"]["CATP"]["sha256"] = "0" * 64
                elif mutation == "added":
                    source["creatures"]["UNREVIEWED"] = deepcopy(source["creatures"]["CATP"])
                else:
                    del source["creatures"]["CATP"]
                config = deepcopy(self.config)
                before = deepcopy(config)
                with self.assertRaisesRegex(ValueError, "CRE fingerprints"):
                    apply(source, config)
                self.assertEqual(before, config)
        groups = deepcopy(builder.CITY_APPEARANCE_SOURCE_GROUPS)
        groups[("UNREVIEWED", "MALE")] = ["CATP"]
        config = deepcopy(self.config)
        before = deepcopy(config)
        with patch.object(builder, "CITY_APPEARANCE_SOURCE_GROUPS", groups):
            with self.assertRaisesRegex(ValueError, "Duplicate source appearance"):
                apply(self.source, config)
        self.assertEqual(before, config)

        reviewed = {
            code: appearance for appearance, codes in builder.CITY_APPEARANCE_SOURCE_GROUPS.items() for code in codes
        }
        unreviewed = sorted(self.source["creatures"].keys() - reviewed.keys())
        self.assertEqual(146, len(unreviewed))
        with self.assertRaisesRegex(ValueError, "Unaudited City appearance for " + unreviewed[0]):
            builder.cityActorAppearance({"sourceCreature": unreviewed[0]}, self.source, reviewed)

    def testDeclaredAssetsExactlyCoverAllStaticMapLocalActorReferences(self):
        assets = self.document.get("assets")
        self.assertIsInstance(assets, list)
        assets = [row for row in assets if row["path"].startswith("images/npc/")]
        self.assertEqual(41, len(assets))
        self.assertEqual(assets, sorted(assets, key=lambda row: row["path"]))
        paths = [row["path"] for row in assets]
        self.assertEqual(len(paths), len(set(paths)))
        expected = set()
        for row in sourceActors(self.config).values():
            animation = row["properties"]["animation"]
            self.assertFalse(animation.endswith(".png"), "The animation provider appends the extension")
            if animation.startswith(PREFIX):
                expected.add(animation.removeprefix("maps/baldursGate/") + ".png")
            else:
                self.assertTrue((ROOT / "res" / (animation + ".png")).is_file(), animation)
        self.assertEqual(expected, set(paths))
        for row in assets:
            self.assertEqual({"path", "kind"}, set(row))
            self.assertEqual("file", row["kind"])
            path = PurePosixPath(row["path"])
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertEqual(("images", "npc"), path.parts[:2])
            self.assertEqual(".png", path.suffix)

    def testProductionDeclaredAssetStagingCopiesExactFixtureBytesAndOnlyDeclaredFiles(self):
        assets = self.document.get("assets")
        self.assertIsInstance(assets, list)
        self.assertEqual(41, sum(row["path"].startswith("images/npc/") for row in assets))
        self.assertEqual(65, len(assets))
        cmake_source = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^function\(stage_map_declared_assets map_name\).*?^endfunction\(\)", cmake_source)
        self.assertIsNotNone(match)
        registered = re.search(r"set\(GAME_STAGED_MAPS\s+(.*?)\)", cmake_source, flags=re.DOTALL)
        self.assertIsNotNone(registered)
        self.assertIn("baldursGate", registered.group(1).split())
        self.assertIn("install(DIRECTORY res/maps DESTINATION fall-of-nouraajd)", cmake_source)
        cmake = [shutil.which("cmake")] if shutil.which("cmake") else [sys.executable, "-m", "cmake"]
        # COPYONLY treats bytes opaquely; real generated-PNG decoding is checked separately below.
        payload = b"synthetic city appearance staging fixture\x00\xff"
        with tempfile.TemporaryDirectory(prefix="city-appearance-staging-") as temporary:
            root = Path(temporary)
            source, staged = root / "source", root / "build"
            map_root = source / "res/maps/baldursGate"
            map_root.mkdir(parents=True)
            (map_root / "map.json").write_text(json.dumps({"assets": assets}), encoding="utf-8")
            for row in assets:
                target = map_root / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            (map_root / "images/npc/notDeclared.png").write_bytes(payload)
            (source / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\nproject(cityAppearanceStaging NONE)\n"
                + match.group(0)
                + "\nstage_map_declared_assets(baldursGate)\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [*cmake, "-S", str(source), "-B", str(staged)], capture_output=True, text=True, timeout=30
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            staged_root = staged / "maps/baldursGate"
            self.assertEqual(
                set(row["path"] for row in assets),
                {p.relative_to(staged_root).as_posix() for p in staged_root.rglob("*.png")},
            )
            for row in assets:
                self.assertEqual(payload, (staged_root / row["path"]).read_bytes(), row["path"])


class BaldursGateCityAppearanceAssetTest(unittest.TestCase):
    def testDeclaredGeneratedPngsAreDistinctTransparentAndFitTheNativePixelBudget(self):
        try:
            from PIL import Image
        except ImportError as error:
            self.skipTest("Existing development Pillow dependency is unavailable: " + str(error))
        document = readJson(MAP_ROOT / "map.json")
        assets = document.get("assets")
        self.assertIsInstance(assets, list)
        assets = [row for row in assets if row["path"].startswith("images/npc/")]
        self.assertEqual(41, len(assets))
        native = (ROOT / "src/gui/CTextureCache.cpp").read_text(encoding="utf-8")
        limit = re.search(r"constexpr int MAX_ALPHA_MASK_PIXELS = ([\d']+);", native)
        self.assertIsNotNone(limit)
        pixel_budget = int(limit.group(1).replace("'", ""))
        hashes = set()
        for row in assets:
            path = MAP_ROOT / row["path"]
            with self.subTest(path=row["path"]):
                self.assertTrue(path.is_file())
                raw = path.read_bytes()
                self.assertTrue(raw)
                sha = hashlib.sha256(raw).hexdigest()
                self.assertNotIn(sha, hashes, "Different appearances require different artwork")
                hashes.add(sha)
                with Image.open(path) as image:
                    image.load()
                    self.assertEqual("PNG", image.format)
                    self.assertEqual("RGBA", image.mode)
                    self.assertGreater(image.width, 0)
                    self.assertGreater(image.height, 0)
                    self.assertLessEqual(image.width * image.height, pixel_budget)
                    alpha = image.getchannel("A")
                    low, high = alpha.getextrema()
                    self.assertEqual(0, low)
                    self.assertGreater(high, 0)
                    for point in (
                        (0, 0),
                        (image.width - 1, 0),
                        (0, image.height - 1),
                        (image.width - 1, image.height - 1),
                    ):
                        self.assertEqual(0, alpha.getpixel(point), "Keep corner transparency supplied by the generator")


if __name__ == "__main__":
    unittest.main()
