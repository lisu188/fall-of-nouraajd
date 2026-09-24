# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Castle campaign gates and authored geography, runnable without _game or Heroes III."""

import copy
import importlib.util
import json
import re
import shlex
import sys
import struct
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_NAMES = ("castleHomecoming", "castleGuardianAngels", "castleGriffinCliff")


def loadCastleModule():
    spec = importlib.util.spec_from_file_location(
        "castle_campaign_under_test", REPO_ROOT / "res" / "plugins" / "castle_campaign.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeObject:
    def __init__(self, name="", game_map=None, coords=(3, 3, 0), **properties):
        self.name = name
        self.game_map = game_map
        self.coords = types.SimpleNamespace(x=coords[0], y=coords[1], z=coords[2])
        self.properties = dict(properties)
        self.alive = True

    def getName(self):
        return self.name

    def getMap(self):
        return self.game_map

    def getGame(self):
        return self.game_map.game

    def getCoords(self):
        return self.coords

    def getStringProperty(self, key):
        return self.properties.get(key, "")

    def setStringProperty(self, key, value):
        self.properties[key] = str(value)

    def getBoolProperty(self, key):
        return bool(self.properties.get(key, False))

    def setBoolProperty(self, key, value):
        self.properties[key] = bool(value)

    def getNumericProperty(self, key):
        return self.properties.get(key, 0)

    def setNumericProperty(self, key, value):
        self.properties[key] = value

    def isAlive(self):
        return self.alive

    def isPlayer(self):
        return False


class FakePlayer(FakeObject):
    def __init__(self, game_map):
        super().__init__("player", game_map)
        self.gold = 37
        self.quest_checks = 0
        self.quests = []

    def isPlayer(self):
        return True

    def getGold(self):
        return self.gold

    def addGold(self, amount):
        self.gold += amount

    def checkQuests(self):
        self.quest_checks += 1
        self.getGame().events.append("quests")

    def getQuests(self):
        return self.quests

    def getCompletedQuests(self):
        return []

    def addQuest(self, name):
        self.quests.append(FakeObject(name))


class FakeMap(FakeObject):
    def __init__(self):
        super().__init__("castleGriffinCliff")
        self.objects = {}
        self.player = FakePlayer(self)
        self.game = types.SimpleNamespace(
            getMap=lambda: self,
            getGuiHandler=lambda: types.SimpleNamespace(showMessage=lambda text: self.messages.append(text)),
            events=[],
        )
        self.messages = []

    def getGame(self):
        return self.game

    def getPlayer(self):
        return self.player

    def getObjectByName(self, name):
        return self.objects.get(name)

    def getObjects(self):
        return list(self.objects.values())


class CastleCampaignGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.castle = loadCastleModule()

    def setUp(self):
        self.game_map = FakeMap()
        self.player = self.game_map.player
        self.routes = []
        self.mission = {
            "scenarioId": "griffinCliff",
            "questId": "castleGriffinCliffQuest",
            "objectiveIds": [f"tower{index}" for index in range(1, 8)],
            "enemyHeroIds": [],
            "defenderIds": [f"tower{index}Guard" for index in range(1, 8)] + ["enemyCommander"],
            "victoryGold": 300,
            "nextMap": "",
            "intro": "Free the seven Griffin Towers.",
        }
        self.game_map.objects["castleMission"] = FakeObject(
            "castleMission", self.game_map, campaign_mission=json.dumps(self.mission)
        )
        for objective_id in self.mission["objectiveIds"]:
            self.game_map.objects[objective_id] = FakeObject(
                objective_id,
                self.game_map,
                campaign_objectiveId=objective_id,
                campaign_guards=objective_id + "Guard",
                campaign_rewardGold=25,
                label=objective_id,
            )
            self.game_map.objects[objective_id + "Guard"] = FakeObject(objective_id + "Guard", self.game_map)

        def completeScenario(game, outcome, **kwargs):
            game.events.append("route")
            self.routes.append((game, outcome, kwargs))

        def claimOnce(owner, key):
            if owner.getBoolProperty(key):
                return False
            owner.setBoolProperty(key, True)
            return True

        self.game_stub = types.SimpleNamespace(
            campaign=types.SimpleNamespace(complete_scenario=completeScenario, state=lambda game: None),
            claim_once=claimOnce,
        )
        self.patch = mock.patch.dict(sys.modules, {"game": self.game_stub})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def defeatGuard(self, objective_id):
        guard_name = objective_id + "Guard"
        guard = self.game_map.objects[guard_name]
        guard.alive = False
        self.castle.markDefeated(guard)
        del self.game_map.objects[guard_name]

    def capture(self, objective_id):
        return self.castle.captureObjective(self.game_map.objects[objective_id], self.player)

    def test_living_or_merely_removed_guard_cannot_unlock_capture(self):
        self.assertFalse(self.capture("tower1"))
        self.castle.markDefeated(self.game_map.objects["tower1Guard"])
        self.assertFalse(self.game_map.getBoolProperty(self.castle.defeatedFlag("tower1Guard")))
        del self.game_map.objects["tower1Guard"]
        self.assertFalse(self.capture("tower1"))
        self.assertEqual(37, self.player.gold)

    def test_remote_wrong_floor_and_non_player_capture_are_rejected(self):
        self.defeatGuard("tower1")
        marker = self.game_map.objects["tower1"]
        self.player.coords.x = 10
        self.assertFalse(self.capture("tower1"))
        self.player.coords.x = 3
        self.player.coords.z = 1
        self.assertFalse(self.capture("tower1"))
        self.player.coords.z = 0
        impostor = FakePlayer(self.game_map)
        self.assertFalse(self.castle.captureObjective(marker, impostor))
        self.assertFalse(self.castle.captureObjective(marker, FakeObject("npc", self.game_map)))
        self.assertEqual(37, self.player.gold)

    def test_repeated_capture_pays_once_and_does_not_complete_seven_towers(self):
        self.defeatGuard("tower1")
        self.assertTrue(self.capture("tower1"))
        for _ in range(8):
            self.capture("tower1")
        self.assertEqual(62, self.player.gold)
        self.assertTrue(any("tower1" in message for message in self.game_map.messages))
        self.assertEqual([], self.routes)
        self.assertTrue(self.game_map.getBoolProperty(self.castle.objectiveFlag("tower1")))
        self.assertFalse(self.game_map.getBoolProperty("campaign_castleFinished_griffinCliff"))

    def test_all_seven_distinct_captures_finish_once_without_unrelated_enemies(self):
        self.game_map.objects["unrelatedDevil"] = FakeObject("unrelatedDevil", self.game_map)
        for objective_id in self.mission["objectiveIds"]:
            self.defeatGuard(objective_id)
            self.assertTrue(self.capture(objective_id))
        self.assertEqual(37 + 7 * 25 + 300, self.player.gold)
        self.assertEqual(1, len(self.routes))
        self.assertTrue(self.game_map.objects["unrelatedDevil"].isAlive())
        self.assertTrue(self.player.getBoolProperty("campaign_castleCompleted_griffinCliff"))
        self.assertLess(self.game_map.game.events.index("quests"), self.game_map.game.events.index("route"))
        self.castle.finishMission(self.game_map)
        self.capture("tower7")
        self.assertEqual(1, len(self.routes))
        self.assertEqual(37 + 7 * 25 + 300, self.player.gold)

    def test_guardian_angels_requires_each_enemy_commander_after_town_captures(self):
        self.mission.update(scenarioId="guardianAngels", objectiveIds=["tower1"], enemyHeroIds=["enemyCommander"])
        self.game_map.objects["castleMission"].setStringProperty("campaign_mission", json.dumps(self.mission))
        self.game_map.objects["enemyCommander"] = FakeObject("enemyCommander", self.game_map)
        self.defeatGuard("tower1")
        self.assertTrue(self.capture("tower1"))
        self.assertEqual([], self.routes)
        commander = self.game_map.objects["enemyCommander"]
        commander.alive = False
        self.castle.markDefeated(commander)
        del self.game_map.objects["enemyCommander"]
        self.castle.finishMission(self.game_map)
        self.assertEqual(1, len(self.routes))

    def test_partial_persisted_state_keeps_capture_and_reward_identity(self):
        self.defeatGuard("tower1")
        self.capture("tower1")
        persisted_map = json.loads(json.dumps(self.game_map.properties))
        persisted_player = json.loads(json.dumps(self.player.properties))
        gold = self.player.gold
        self.game_map.properties = copy.deepcopy(persisted_map)
        self.player.properties = copy.deepcopy(persisted_player)
        self.assertFalse(self.capture("tower1"))
        self.assertEqual(gold, self.player.gold)
        self.assertFalse(self.castle.finishMission(self.game_map))
        self.assertEqual([], self.routes)

    def test_retained_chapter_cannot_advance_a_different_active_scenario(self):
        self.game_stub.campaign.state = lambda game: types.SimpleNamespace(
            active=lambda: True, campaign_id=lambda: "longLiveTheQueen", scenario=lambda: "homecoming"
        )
        for objective_id in self.mission["objectiveIds"]:
            self.defeatGuard(objective_id)
            self.capture(objective_id)
        self.assertEqual([], self.routes)
        self.assertFalse(self.player.getBoolProperty("campaign_castleCompleted_griffinCliff"))

    def test_standalone_victory_uses_existing_campaign_fallback(self):
        self.mission.update(scenarioId="homecoming", objectiveIds=["tower1"], nextMap="castleGuardianAngels")
        self.game_map.objects["castleMission"].setStringProperty("campaign_mission", json.dumps(self.mission))
        self.defeatGuard("tower1")
        self.assertTrue(self.capture("tower1"))
        self.assertEqual(1, len(self.routes))
        self.assertEqual("completed", self.routes[0][1])
        self.assertEqual({"fallback_map": "castleGuardianAngels"}, self.routes[0][2])


class CastleCampaignAuthoringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts import author_castle_campaign

        cls.author = author_castle_campaign
        cls.fixtures = []
        for map_name in MAP_NAMES:
            source = json.loads(
                (REPO_ROOT / "res/campaigns/longLiveTheQueen/sources" / (map_name + ".json")).read_text()
            )
            native = json.loads((REPO_ROOT / "res/maps" / map_name / "map.json").read_text())
            authored = cls.author.authorMap(native, source)
            cls.fixtures.append((map_name, source, native, authored))

    def objectsByName(self, document):
        return {
            obj["name"]: (obj, int(layer["properties"]["level"]))
            for layer in document["layers"]
            for obj in layer.get("objects", [])
        }

    def test_all_reviewed_landmark_families_retain_exact_source_visits(self):
        intended_types = {
            2,
            4,
            5,
            9,
            10,
            12,
            13,
            14,
            16,
            17,
            23,
            25,
            27,
            28,
            30,
            31,
            32,
            33,
            35,
            37,
            38,
            39,
            41,
            42,
            47,
            49,
            51,
            53,
            55,
            58,
            60,
            61,
            62,
            64,
            66,
            67,
            68,
            76,
            79,
            80,
            81,
            83,
            88,
            89,
            90,
            91,
            93,
            94,
            96,
            97,
            99,
            100,
            101,
            102,
            104,
            106,
            107,
            109,
            112,
            113,
        }
        self.assertEqual(intended_types, set(self.author.LANDMARKS))
        for (map_name, source, _, authored), expected_count in zip(self.fixtures, (211, 174, 423)):
            with self.subTest(map=map_name):
                expected = {}
                for record in source["objects"]:
                    x, y, z = record["visit"]
                    if record["type"] not in intended_types or not record["visitable"]:
                        continue
                    if source["terrain"][z][y * source["width"] + x][0] >= 8:
                        continue
                    if map_name == "castleGriffinCliff" and record["type"] == 17 and record["subtype"] == 25:
                        continue
                    expected[record["index"]] = record
                objects = self.objectsByName(authored)
                actual = {
                    obj["properties"]["campaign_sourceIndex"]: (obj, z)
                    for obj, z in objects.values()
                    if obj["type"] == "castleLandmark"
                }
                self.assertEqual(expected_count, len(actual))
                self.assertEqual(set(expected), set(actual))
                self.assertEqual(expected_count, len(source["landmarkMappings"]))
                for index, record in expected.items():
                    obj, z = actual[index]
                    self.assertEqual(tuple(record["visit"]), (obj["x"] // 32, obj["y"] // 32, z))
                    self.assertEqual((32, 32), (obj["width"], obj["height"]))
                    properties = obj["properties"]
                    self.assertEqual(record["type"], properties["campaign_sourceType"])
                    self.assertTrue(properties["canStep"])
                    self.assertTrue(properties["label"])
                    self.assertTrue(properties["description"])
                    self.assertNotIn("campaign_rewardGold", properties)
                    self.assertTrue((REPO_ROOT / "res" / (properties["animation"] + ".png")).is_file())
                for mapping in source["landmarkMappings"]:
                    obj, _ = objects[mapping["nativeObjectId"]]
                    self.assertEqual("visualOnly", mapping["adaptation"])
                    self.assertEqual(expected[mapping["sourceIndex"]]["visit"], mapping["visit"])
                    self.assertEqual(obj["properties"]["animation"], mapping["animation"])

    def test_key_landmark_icons_and_town_service_flags_are_type_specific(self):
        icon_cases = {
            (53, 0): "ambient/supply_pile",
            (53, 2): "buildings/cave",
            (53, 5): "ambient/stone_well",
            (83, 0): "buildings/tavern",
            (17, 25): "castle/griffinTower",
            (17, 35): "buildings/chapel",
            (93, 0): "items/scroll",
            (101, 0): "misc/chest",
            (94, 0): "ambient/hay_bales",
        }
        for (kind, subtype), icon in icon_cases.items():
            properties = self.author.landmarkProperties({"index": 1, "type": kind, "subtype": subtype})
            self.assertEqual("images/" + icon, properties["animation"])
        for map_name, source, _, authored in self.fixtures:
            objects = self.objectsByName(authored)
            for record in source["objects"]:
                if record["type"] not in (77, 98):
                    continue
                prefix = "Supply" if record.get("owner") == 0 else "Objective"
                obj, _ = objects[map_name + prefix + str(record["index"])]
                self.assertTrue(obj["properties"]["campaign_isTown"])
                self.assertEqual(record.get("owner") == 0, obj["properties"].get("campaign_loyalTown", False))
            for obj, _ in objects.values():
                if "Support" in obj["name"] or "Ally" in obj["name"]:
                    self.assertFalse(obj["properties"].get("campaign_isTown", False))

    def test_optional_garrisons_and_event_armies_do_not_expand_griffin_victory(self):
        map_name, source, _, authored = self.fixtures[2]
        objects = self.objectsByName(authored)
        mission = json.loads(
            objects["castleMission"][0]["properties"]["campaign_mission"].removeprefix("castleMission:")
        )
        expected_indices = {397, 1063, 1328, 1510, 1052, 1053}
        actual_indices = {mapping["sourceIndex"] for mapping in source["optionalEncounterMappings"]}
        self.assertEqual(expected_indices, actual_indices)
        self.assertEqual(7, len(mission["objectiveIds"]))
        self.assertEqual([], mission["enemyHeroIds"])
        self.assertEqual(
            set(mission["objectiveIds"]),
            {
                name
                for name, (obj, _) in objects.items()
                if obj["properties"].get("animation") == "images/castle/griffinTower"
            },
            "Only the seven required Griffin Towers may use the roost silhouette",
        )
        for record in source["objects"]:
            if record["index"] not in expected_indices:
                continue
            actor_id = map_name + "Encounter" + str(record["index"])
            actor, z = objects[actor_id]
            self.assertEqual(tuple(record["visit"]), (actor["x"] // 32, actor["y"] // 32, z))
            self.assertEqual("castleGarrison", actor["type"])
            self.assertIn(actor_id, mission["defenderIds"])
            self.assertNotIn(actor_id, mission["objectiveIds"])
            self.assertLessEqual(actor["properties"]["hp"], 63)
            self.assertEqual(
                record["army"], json.loads(actor["properties"]["campaign_sourceArmy"].removeprefix("castleArmy:"))
            )
        self.assertEqual([], self.fixtures[0][1]["optionalEncounterMappings"])
        self.assertEqual([], self.fixtures[1][1]["optionalEncounterMappings"])

    def test_landmark_append_is_deterministic_and_preserves_terrain_and_existing_ids(self):
        for map_name, source, native, authored in self.fixtures:
            with self.subTest(map=map_name):
                self.assertEqual(authored, self.author.authorMap(native, copy.deepcopy(source)))
                self.assertEqual(
                    [layer for layer in native["layers"] if layer["type"] == "tilelayer"],
                    [layer for layer in authored["layers"] if layer["type"] == "tilelayer"],
                )
                before, after = self.objectsByName(native), self.objectsByName(authored)
                for name, (old, old_z) in before.items():
                    new, new_z = after[name]
                    self.assertEqual(old["id"], new["id"])
                    self.assertEqual(old["type"], new["type"])
                    if name not in ("castleCatherine", "castleChristian") and "Support" not in name:
                        self.assertEqual((old["x"], old["y"], old_z), (new["x"], new["y"], new_z))
                landmark_cells = {
                    (obj["x"], obj["y"], z) for obj, z in after.values() if obj["type"] == "castleLandmark"
                }
                for name, (obj, z) in after.items():
                    if name in ("castleCatherine", "castleChristian") or "Support" in name:
                        self.assertNotIn((obj["x"], obj["y"], z), landmark_cells)


class CastleCampaignPackagingTest(unittest.TestCase):
    def test_castle_resources_are_staged_and_installed(self):
        cmake = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        staged = {}
        for arguments in re.findall(r"(?m)^\s*configure_file\s*\(([^)]*)\)", cmake):
            source, destination, *options = shlex.split(arguments)
            staged[source] = (destination, options)

        sources = {
            "res/plugins/castle_campaign.py",
            "res/campaigns/longLiveTheQueen/campaign.json",
        }
        for map_name in MAP_NAMES:
            sources.add(f"res/campaigns/longLiveTheQueen/sources/{map_name}.json")
            sources.update(
                f"res/maps/{map_name}/{name}" for name in ("config.json", "dialog.json", "map.json", "script.py")
            )
        images = {path.relative_to(REPO_ROOT).as_posix() for path in (REPO_ROOT / "res/images/castle").glob("*.png")}
        self.assertTrue(images, "the campaign requires its authored Castle artwork")
        sources.update(images)
        self.assertEqual([], sorted(sources - staged.keys()), "Castle resources missing from build staging")
        for source in sorted(sources):
            with self.subTest(resource=source):
                self.assertTrue((REPO_ROOT / source).is_file(), "a staged campaign resource must exist")
                destination, options = staged[source]
                self.assertEqual(source.removeprefix("res/"), destination)
                if source in images:
                    self.assertIn("COPYONLY", options, "binary artwork must be copied without text substitution")

        for directory in ("campaigns", "maps", "plugins", "images"):
            self.assertRegex(cmake, rf"install\s*\(DIRECTORY\s+res/{directory}\s+DESTINATION\s+fall-of-nouraajd\s*\)")


class CastleCampaignContentTest(unittest.TestCase):
    def test_random_level_six_army_keeps_source_identity_and_minotaur_art(self):
        from tests.castle_walkthrough import authoredMap

        source = json.loads((REPO_ROOT / "res/campaigns/longLiveTheQueen/sources/castleHomecoming.json").read_text())
        record = next(record for record in source["objects"] if record["index"] == 1449)
        self.assertEqual(163, record["type"])
        _, objects, _, _, mission = authoredMap("castleHomecoming")
        actor_name = "castleHomecomingEncounter1449"
        self.assertIn(actor_name, mission["defenderIds"])
        actor = objects[actor_name]
        self.assertEqual(tuple(record["visit"]), actor["coords"])
        self.assertEqual(1449, actor["properties"]["campaign_sourceIndex"])
        self.assertEqual(80, actor["properties"]["campaign_representativeCreature"])
        self.assertEqual("images/castle/minotaur", actor["properties"]["animation"])

    def test_original_dimensions_terrain_and_masks_are_preserved(self):
        terrain_gids = (10, 8, 11, 5, 3, 7, 10, 9, 2, 12)
        for map_name, expected_size in zip(MAP_NAMES, (72, 36, 72)):
            with self.subTest(map=map_name):
                source = json.loads(
                    (REPO_ROOT / "res/campaigns/longLiveTheQueen/sources" / (map_name + ".json")).read_text()
                )
                native = json.loads((REPO_ROOT / "res/maps" / map_name / "map.json").read_text())
                self.assertEqual(
                    (expected_size, expected_size, 2), (source["width"], source["height"], source["layers"])
                )
                self.assertEqual((expected_size, expected_size), (native["width"], native["height"]))
                self.assertRegex(source["sourceSha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(source["mapSha256"], r"^[0-9a-f]{64}$")
                blocked = {tuple(cell) for cell in source["blockedCells"]}
                floors = [layer for layer in native["layers"] if layer["type"] == "tilelayer"]
                self.assertEqual(2, len(floors))
                self.assertEqual("castleRoadTile", native["tilesets"][0]["tileproperties"]["5"]["type"])
                for z, floor in enumerate(floors):
                    expected = []
                    for index, tile in enumerate(source["terrain"][z]):
                        cell = (index % expected_size, index // expected_size, z)
                        if cell in blocked:
                            expected.append(12)
                        elif tile[4] and tile[0] not in (8, 9):
                            expected.append(15 if tile[2] else 6)
                        elif tile[2] and tile[0] not in (8, 9):
                            expected.append(14)
                        else:
                            expected.append(terrain_gids[tile[0]])
                    self.assertEqual(len(expected), len(floor["data"]))
                    mismatches = [
                        index for index, values in enumerate(zip(expected, floor["data"])) if values[0] != values[1]
                    ]
                    self.assertEqual([], mismatches[:10], f"{map_name}: source terrain or obstacle footprints drifted")

    def test_objectives_and_transit_destinations_are_reachable(self):
        from tests.castle_walkthrough import authoredMap, shortestRoute

        for map_name in MAP_NAMES:
            with self.subTest(map=map_name):
                document, objects, walkable, portals, mission = authoredMap(map_name)
                start = tuple(int(document["properties"][axis]) for axis in "xyz")
                self.assertIn(start, walkable)
                self.assertEqual(len(mission["objectiveIds"]), len(set(mission["objectiveIds"])))
                required_guards = [
                    guard
                    for name in mission["objectiveIds"]
                    for guard in objects[name]["properties"].get("campaign_guards", "").split(",")
                    if guard
                ]
                support_ids = [
                    name
                    for name, value in objects.items()
                    if name in ("castleCatherine", "castleChristian") or value.get("class") == "CastleSupply"
                ]
                for name in mission["objectiveIds"] + mission["enemyHeroIds"] + required_guards + support_ids:
                    target = objects[name]["coords"]
                    self.assertIn(target, walkable, name)
                    shortestRoute(walkable, portals, start, target)
                for origin, target in portals.items():
                    self.assertIn(origin, walkable)
                    self.assertIn(target, walkable)
                    self.assertEqual(origin, portals.get(target), "Authored transit must have a return route")
                for origin, targets in portals.passages.items():
                    for target in targets:
                        self.assertEqual(origin[2], target[2])
                        self.assertEqual(1, abs(origin[0] - target[0]))
                        self.assertEqual(1, abs(origin[1] - target[1]))
                        self.assertIn(origin, walkable)
                        self.assertIn(target, walkable)
                        self.assertIn(origin, portals.passages.get(target, ()))

    def test_exactly_seven_original_griffin_towers_and_underground_terraneus(self):
        from tests.castle_walkthrough import authoredMap

        source_root = REPO_ROOT / "res/campaigns/longLiveTheQueen/sources"
        source = json.loads((source_root / "castleGriffinCliff.json").read_text())
        towers = [record for record in source["objects"] if record["type"] == 17 and record["subtype"] == 25]
        self.assertEqual(7, len(towers))
        _, objects, _, _, mission = authoredMap("castleGriffinCliff")
        self.assertEqual(7, len(mission["objectiveIds"]))
        self.assertEqual(
            {tuple(tower["visit"]) for tower in towers},
            {objects[name]["coords"] for name in mission["objectiveIds"]},
        )
        homecoming = json.loads((source_root / "castleHomecoming.json").read_text())
        self.assertEqual([33, 35, 1], homecoming["victory"]["target"])
        town = next(
            record
            for record in homecoming["objects"]
            if record["type"] == 98 and record["visit"] == homecoming["victory"]["target"]
        )
        _, objects, _, _, mission = authoredMap("castleHomecoming")
        self.assertEqual([tuple(town["visit"])], [objects[name]["coords"] for name in mission["objectiveIds"]])

    def test_campaign_routes_without_carryover_restrictions_or_player_npcs(self):
        from tests.castle_walkthrough import authoredMap

        manifest = json.loads((REPO_ROOT / "res/campaigns/longLiveTheQueen/campaign.json").read_text())
        self.assertEqual("longLiveTheQueen", manifest["campaignId"])
        scenario_id = manifest["start"]
        maps = []
        while scenario_id:
            scenario = manifest["scenarios"][scenario_id]
            self.assertFalse(scenario.get("carryover"))
            maps.append(scenario["map"])
            scenario_id = scenario["next"].get("completed")
        self.assertEqual(list(MAP_NAMES), maps)
        for map_name in MAP_NAMES:
            _, objects, _, _, _ = authoredMap(map_name)
            for name, value in objects.items():
                self.assertNotEqual("CPlayer", value.get("class"), (map_name, name))

    def test_guardian_objectives_cover_original_enemy_towns_and_commanders(self):
        from tests.castle_walkthrough import authoredMap

        source = json.loads(
            (REPO_ROOT / "res/campaigns/longLiveTheQueen/sources/castleGuardianAngels.json").read_text()
        )
        _, objects, _, _, mission = authoredMap("castleGuardianAngels")
        source_towns = {
            record["index"] for record in source["objects"] if record["type"] == 98 and record.get("owner") in (1, 2)
        }
        source_heroes = {
            record["index"]
            for record in source["objects"]
            if record["type"] in (34, 62, 70, 214) and record.get("owner") in (1, 2)
        }
        self.assertEqual(4, len(source_towns))
        self.assertEqual(4, len(source_heroes))
        self.assertEqual(
            source_towns, {objects[name]["properties"]["campaign_sourceIndex"] for name in mission["objectiveIds"]}
        )
        self.assertEqual(
            source_heroes, {objects[name]["properties"]["campaign_sourceIndex"] for name in mission["enemyHeroIds"]}
        )

    def test_campaign_art_is_present_square_rgba_png(self):
        art_names = (
            "catherine",
            "christian",
            "pikeman",
            "marksman",
            "griffin",
            "swordsman",
            "monk",
            "cavalier",
            "angel",
            "castleTown",
            "griffinTower",
            "occupiedBanner",
            "liberatedBanner",
            "troglodyte",
            "minotaur",
            "demon",
            "devil",
        )
        for name in art_names:
            with self.subTest(image=name):
                path = REPO_ROOT / "res/images/castle" / (name + ".png")
                data = path.read_bytes()
                self.assertGreater(len(data), 32)
                self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
                self.assertEqual(b"IHDR", data[12:16])
                width, height, _, color_type = struct.unpack(">IIBB", data[16:26])
                self.assertGreater(width, 0)
                self.assertEqual(width, height)
                self.assertEqual(6, color_type, "Campaign artwork must retain its transparency channel")


if __name__ == "__main__":
    unittest.main()
