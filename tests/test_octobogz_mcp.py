# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import unittest
import uuid

from tests import test_ui_mcp_dialogue as dialogue_mcp
from tests.castle_walkthrough import TransitRoutes, shortestRoute
from tests.narrative_walkthrough import authoredRegion


class OctobogzMcpWalkthroughTest(unittest.TestCase):
    setUp = dialogue_mcp.DialogueMcpWalkthroughTest.setUp
    engine = dialogue_mcp.DialogueMcpWalkthroughTest.engine
    call = dialogue_mcp.DialogueMcpWalkthroughTest.call
    pump = dialogue_mcp.DialogueMcpWalkthroughTest.pump
    object = dialogue_mcp.DialogueMcpWalkthroughTest.object
    dialog = dialogue_mcp.DialogueMcpWalkthroughTest.dialog
    action = dialogue_mcp.DialogueMcpWalkthroughTest.action
    questNames = dialogue_mcp.DialogueMcpWalkthroughTest.questNames

    def state(self):
        return json.loads(
            self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry").removeprefix("octobogzHunt.v1:")
        )

    def refresh(self):
        self.game_map = self.call(self.game, "getMap")
        self.player = self.call(self.game_map, "getPlayer")
        registered = self.call(self.game_map, "getObjectByName", self.call(self.player, "getName"))
        self.assertEqual(self.player["__handle__"], registered["__handle__"])

    def coords(self, handle=None):
        data = json.loads(self.engine("jsonify", handle or self.player))["properties"]
        return tuple(data["pos" + axis] for axis in "xyz")

    def snapshot(self, stage):
        data = json.loads(self.engine("jsonify", self.player))["properties"]
        result = {
            "stage": stage,
            "coords": self.coords(),
            "level": self.call(self.player, "getLevel"),
            "exp": self.call(self.player, "getNumericProperty", "exp"),
            "hp": data.get("hp"),
            "mana": self.call(self.player, "getMana"),
            "gold": self.call(self.player, "getGold"),
            "items": [item["properties"].get("typeId") for item in data.get("items") or []],
            "turn": self.call(self.game_map, "getTurn"),
            "defeat": self.call(self.player, "getStringProperty", "uiDefeatReceipt"),
        }
        print("MCP hunt journey", result, flush=True)
        return result

    def step(self, destination):
        origin = self.coords()
        defeat_before = self.call(self.player, "getStringProperty", "uiDefeatReceipt")
        self.assertEqual(1, sum(abs(a - b) for a, b in zip(origin, destination)))
        tile = self.call(self.game_map, "getTile", *destination)
        self.assertIsNotNone(tile, destination)
        self.assertTrue(self.call(tile, "getBoolProperty", "canStep"), destination)
        # Native adjacent moveTo checks CMap.canStep before committing, including object footprints.
        self.call(self.player, "moveTo", *destination)
        self.pump()
        turn = self.call(self.game_map, "getTurn")
        self.call(self.game_map, "move")
        self.pump()
        self.assertEqual(turn + 1, self.call(self.game_map, "getTurn"))
        if not self.call(self.player, "isAlive"):
            self.fail(self.snapshot("defeated during movement"))
        if self.call(self.player, "getStringProperty", "uiDefeatReceipt") != defeat_before:
            self.fail(self.snapshot("lost authored combat and respawned"))
        arrival = self.coords()
        if sum(abs(a - b) for a, b in zip(origin, arrival)) > 1:
            self.fail(
                ("Unexpected movement without an authored transit", origin, destination, self.snapshot("arrival"))
            )
        self.movement_steps += 1
        return arrival

    def walkTo(self, name, *, allow_removed=False):
        return self.walkRoute(name, allow_removed=allow_removed)

    def walkCoords(self, coords):
        return self.walkRoute(tuple(coords))

    def walkRoute(self, target, *, allow_removed=False):
        route = []
        planned_target = None
        blockers = None
        for _ in range(512):
            actor = self.call(self.game_map, "getObjectByName", target) if isinstance(target, str) else None
            if isinstance(target, str):
                if actor is None and allow_removed:
                    return
                self.assertIsNotNone(actor, target)
                destination = self.coords(actor)
            else:
                destination = target
            current = self.coords()
            if current == destination:
                return actor
            if planned_target != destination or not route:
                route = shortestRoute(self.walkable, TransitRoutes(), current, destination)
                planned_target = destination
            step, expected = route.pop(0)
            tile = self.call(self.game_map, "getTile", *step)
            self.assertIsNotNone(tile, step)
            if not self.call(tile, "getBoolProperty", "canStep"):
                self.walkable.discard(step)
                route = []
                continue
            if self.step(step) != expected:
                # Player victories restore the origin, including repeated fights in a cave cell.
                if blockers is None:
                    blockers = [
                        candidate
                        for candidate in self.call(self.game_map, "getObjects")
                        if not self.call(candidate, "getBoolProperty", "canStep")
                    ]
                for blocker in blockers:
                    if self.coords(blocker) == step and not self.call(
                        self.game_map, "canStep", self.call(blocker, "getCoords")
                    ):
                        self.walkable.discard(step)
                route = []
        self.fail(("Bounded adjacent hunt route did not reach its target", target, self.snapshot("route blocked")))

    def recoverOnAuthoredRoad(self):
        actors = self.livingActors()
        self.recoverOnRoadPair((118, 21, 0), (118, 20, 0), "hunt road recovery", actors)

    def recoverOnRoadPair(self, first, second, stage, actors=None):
        self.assertEqual(1, sum(abs(a - b) for a, b in zip(first, second)))
        for destination in (first, second):
            tile = self.call(self.game_map, "getTile", *destination)
            self.assertEqual("RoadTile", self.call(tile, "getTypeId"))
        self.walkCoords(first)
        self.snapshot(stage + " arrival")
        if actors:
            self.observeActors(stage + " arrival", actors)
        for index in range(128):
            destination = second if index % 2 == 0 else first
            tile = self.call(self.game_map, "getTile", *destination)
            self.assertEqual("RoadTile", self.call(tile, "getTypeId"))
            self.step(destination)
            if self.call(self.player, "getHp") == self.call(self.player, "getHpMax") and self.call(
                self.player, "getMana"
            ) == self.call(self.player, "getManaMax"):
                self.snapshot(stage + " complete")
                return
        self.fail(
            ("Authored road steps did not restore the ordinary player", self.snapshot("road recovery incomplete"))
        )

    def nearbyRolfEnemies(self):
        current = self.coords()
        candidates = []
        for actor in self.call(self.game_map, "getObjects"):
            if self.call(actor, "getTypeId") != "Pritz" or not self.call(actor, "isAlive"):
                continue
            if self.call(actor, "getStringProperty", "affiliation") != "gooby":
                continue
            coords = self.coords(actor)
            if coords[2] == 0 and abs(coords[0] - 19) + abs(coords[1] - 10) <= 55:
                candidates.append((sum(abs(a - b) for a, b in zip(current, coords)), self.call(actor, "getName")))
        return sorted(candidates)

    def prepareThroughRolf(self):
        self.recoverOnRoadPair((44, 106, 0), (44, 107, 0), "opened gate road recovery")
        self.snapshot("before original Rolf cave")
        self.walkTo("cave1", allow_removed=True)
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "completed_rolf"))
        self.assertGreater(self.call(self.player, "countItems", "skullOfRolf"), 0)
        self.snapshot("after original Rolf cave")
        for _ in range(32):
            if self.call(self.player, "getLevel") >= 3:
                break
            candidates = self.nearbyRolfEnemies()
            if not candidates:
                break
            if self.call(self.player, "getHpRatio") < 75:
                self.recoverOnRoadPair((9, 36, 0), (9, 37, 0), "Rolf road recovery")
                candidates = self.nearbyRolfEnemies()
                if not candidates:
                    break
            name = candidates[0][1]
            before = self.snapshot("before authored Pritz " + name)
            self.walkTo(name, allow_removed=True)
            after = self.snapshot("after authored Pritz " + name)
            self.assertIsNone(self.call(self.game_map, "getObjectByName", name))
            self.assertGreater(after["exp"], before["exp"], "Preparation must earn experience through real combat")
        self.snapshot("before original Gooby approach")
        self.recoverOnRoadPair((109, 100, 0), (109, 101, 0), "Gooby road recovery")
        self.walkTo("gooby1", allow_removed=True)
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "completed_gooby"))
        self.assertIn("mainQuest", self.questNames("getCompletedQuests"))
        self.assertGreaterEqual(self.call(self.player, "getLevel"), 3, self.snapshot("Rolf preparation complete"))

    def useOrdinaryCombatController(self, player_class):
        # Attachment and save restoration install the interactive controller.
        template = self.call(self.game, "createObject", player_class)
        self.call(self.player, "setFightController", self.call(template, "getFightController"))

    def livingActors(self):
        return {
            slot: self.call(self.game_map, "getObjectByName", record["name"])
            for slot, record in self.state()["slots"].items()
            if record["status"] == "living"
        }

    def observeActors(self, stage, actors):
        for slot, actor in actors.items():
            self.assertIsNotNone(actor, slot)
            properties = json.loads(self.engine("jsonify", actor))["properties"]
            packet = (
                self.call(actor, "getObjectProperty", "enemyRoleDamagePacket")
                if properties.get("enemyRoleDamagePacket") is not None
                else None
            )
            observation = {
                "stage": stage,
                "slot": slot,
                "phase": self.call(actor, "getStringProperty", "octobogzCombatPhase"),
                "pulse": self.call(actor, "getBoolProperty", "octobogzPulseUsed"),
                "effect": self.call(actor, "getBoolProperty", "octobogzPulseEffectApplied"),
                "damage_roll": self.call(actor, "getNumericProperty", "enemyRoleAttackBudget"),
                "normal": self.call(packet, "getNumericProperty", "normal") if packet else 0,
                "shadow": self.call(packet, "getNumericProperty", "shadow") if packet else 0,
                "alive": self.call(actor, "isAlive"),
                "mana": self.call(actor, "getMana"),
            }
            print("MCP hunt actor combat", observation, flush=True)
            self.phase_observations.append(observation)

    def defeat(self, slot):
        record = self.state()["slots"][slot]
        if record["status"] == "dead":
            return
        self.assertEqual("living", record["status"])
        actors = self.livingActors()
        self.snapshot("before " + slot)
        self.walkTo(record["name"], allow_removed=True)
        self.snapshot("after " + slot)
        self.observeActors("after " + slot, actors)
        self.assertGreater(
            self.call(self.player, "getNumericProperty", "hp"), 0, "Ordinary player loadout failed against " + slot
        )
        self.assertIsNone(
            self.call(self.game_map, "getObjectByName", record["name"]), "Real movement and combat must defeat " + slot
        )
        self.assertEqual("dead", self.state()["slots"][slot]["status"])

    def testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce(self):
        self.phase_observations = []
        for player_class in ("Warrior", "Sorcerer"):
            with self.subTest(player_class=player_class):
                self.game = self.engine("CGameLoader.loadGame")
                self.engine("CGameLoader.startGameWithPlayer", self.game, "nouraajd", player_class)
                self.refresh()
                self.pump()
                _, self.walkable = authoredRegion("nouraajd")
                self.movement_steps = 0
                self.assertIsNone(self.call(self.game, "getGui"), "The hunt must not create a desktop window")
                self.snapshot("entry")
                starting_blades = self.call(self.player, "countItems", "ShadowBlade")
                # The template's existing AI uses ordinary spells, equipment and carried potions.
                self.useOrdinaryCombatController(player_class)
                # Earn the authored class discovery reward through its NPC action.
                if player_class == "Warrior":
                    self.walkTo("nouraajdDoor")
                    self.action(self.dialog("doorDialog"), "brace_gate")
                else:
                    self.walkTo("nouraajdDoor")
                    self.action(self.dialog("doorDialog"), "open_door")
                    _, self.walkable = authoredRegion("nouraajd")
                    self.walkTo("nouraajdChapel")
                    self.action(self.dialog("berenDialog"), "decode_stained_glass_ward")
                self.prepareThroughRolf()
                self.walkTo("questGiver")
                if player_class == "Warrior":
                    self.action(self.dialog("dialog"), "accept_quest")
                    self.assertIn("octoBogzQuest", self.questNames())
                self.walkTo("ambientOctobogzNet")
                self.recoverOnRoadPair((118, 21, 0), (118, 20, 0), "before hunt road recovery")
                self.walkTo("cave2")
                self.assertEqual("scout", self.state()["stage"])
                self.defeat("scout")
                self.assertEqual("brood", self.state()["stage"])
                self.assertFalse(self.call(self.game_map, "getBoolProperty", "octobogzHuntCleared"))

                slot = "mcp-octobogz-" + uuid.uuid4().hex
                save_path = self.build_dir / "save" / (slot + ".json")
                self.assertFalse(save_path.exists())
                try:
                    self.assertTrue(self.engine("CMapLoader.saveWithResult", self.game_map, slot))
                    self.assertTrue(save_path.is_file())
                    old_state = self.state()
                    self.game = self.engine("CGameLoader.loadGame")
                    self.engine("CGameLoader.loadSavedGame", self.game, slot)
                    self.refresh()
                    self.pump()
                    self.assertEqual(old_state, self.state())
                    self.useOrdinaryCombatController(player_class)
                    self.snapshot("partial reload")
                    gold_before_final = self.call(self.player, "getGold")
                    self.recoverOnAuthoredRoad()
                    self.defeat("alpha")
                    if self.state()["slots"]["brood"]["status"] != "dead":
                        self.assertIsNotNone(self.call(self.game_map, "getObjectByName", "cave2"))
                        self.assertFalse(self.call(self.game_map, "getBoolProperty", "OCTOBOGZ_SLAIN"))
                        self.recoverOnAuthoredRoad()
                    self.defeat("brood")
                    self.assertEqual("cleared", self.state()["stage"])
                    self.assertTrue(self.call(self.game_map, "getBoolProperty", "OCTOBOGZ_SLAIN"))
                    self.assertIsNone(self.call(self.game_map, "getObjectByName", "cave2"))
                    self.walkTo("questGiver")
                    gold_before_claim = self.call(self.player, "getGold")
                    self.action(self.dialog("dialog"), "accept_quest")
                    gold_after_claim = self.call(self.player, "getGold")
                    if player_class == "Sorcerer":
                        self.assertEqual(gold_before_claim + 1000, gold_after_claim)
                    else:
                        self.assertGreaterEqual(gold_before_claim, gold_before_final + 1000)
                        self.assertEqual(gold_before_claim, gold_after_claim)
                    self.assertEqual(starting_blades + 1, self.call(self.player, "countItems", "ShadowBlade"))
                    self.assertIn("octoBogzQuest", self.questNames("getCompletedQuests"))
                    self.action(self.dialog("dialog"), "accept_quest")
                    self.assertEqual(gold_after_claim, self.call(self.player, "getGold"))
                    self.assertEqual(starting_blades + 1, self.call(self.player, "countItems", "ShadowBlade"))
                    self.assertGreater(self.movement_steps, 100)
                    self.snapshot("completed")
                    print(
                        "MCP OctoBogz real combat completed for",
                        player_class,
                        "adjacent steps",
                        self.movement_steps,
                        flush=True,
                    )
                finally:
                    save_path.unlink(missing_ok=True)
                    save_path.with_suffix(".json.bak").unlink(missing_ok=True)
        positive_packets = [
            observed
            for observed in self.phase_observations
            if observed["pulse"] and observed["damage_roll"] > 0 and observed["shadow"] == 1
        ]
        self.assertTrue(
            positive_packets,
            "The real melee/caster routes must exercise a positive shadow packet, not only a phase flag",
        )
        for observed in positive_packets:
            self.assertEqual(
                observed["damage_roll"] - 1, observed["normal"], "The original damage budget must be preserved"
            )


if __name__ == "__main__":
    unittest.main()
