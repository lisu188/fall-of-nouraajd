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
