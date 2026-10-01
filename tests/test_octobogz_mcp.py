# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from hashlib import sha256
import os
from pathlib import Path
from statistics import median
import subprocess
import sys
from time import perf_counter
import unittest
import uuid

from tests import test_ui_mcp_dialogue as dialogue_mcp
from tests.castle_walkthrough import TransitRoutes, shortestRoute
from tests.narrative_walkthrough import authoredRegion


class OctobogzMcpWalkthroughTest(unittest.TestCase):
    setUp = dialogue_mcp.DialogueMcpWalkthroughTest.setUp
    pump = dialogue_mcp.DialogueMcpWalkthroughTest.pump
    object = dialogue_mcp.DialogueMcpWalkthroughTest.object
    dialog = dialogue_mcp.DialogueMcpWalkthroughTest.dialog
    action = dialogue_mcp.DialogueMcpWalkthroughTest.action
    questNames = dialogue_mcp.DialogueMcpWalkthroughTest.questNames

    def resetMcpProfile(self, player_class):
        self.mcp_profile_class = player_class
        self.mcp_profile_started = perf_counter()
        self.mcp_method_profile = {}

    def profiledMcpCall(self, key, callback, *args):
        started = perf_counter()
        failed = False
        try:
            return callback(self, *args)
        except BaseException:
            failed = True
            raise
        finally:
            elapsed = perf_counter() - started
            if not hasattr(self, "mcp_method_profile"):
                self.mcp_method_profile = {}
                self.mcp_profile_started = started
            entry = self.mcp_method_profile.setdefault(key, {"count": 0, "seconds": 0.0, "max": 0.0, "failures": 0})
            entry["count"] += 1
            entry["seconds"] += elapsed
            entry["max"] = max(entry["max"], elapsed)
            entry["failures"] += int(failed)

    def engine(self, name, *args):
        return self.profiledMcpCall("export:" + name, dialogue_mcp.DialogueMcpWalkthroughTest.engine, name, *args)

    def call(self, handle, method, *args):
        return self.profiledMcpCall(
            "handle:" + method, dialogue_mcp.DialogueMcpWalkthroughTest.call, handle, method, *args
        )

    def reportMcpProfile(self, stage):
        profile = getattr(self, "mcp_method_profile", {})
        now = perf_counter()
        methods = [
            {
                "method": name,
                **{key: round(value, 6) if isinstance(value, float) else value for key, value in values.items()},
            }
            for name, values in sorted(profile.items(), key=lambda entry: (-entry[1]["seconds"], entry[0]))[:64]
        ]
        print(
            "MCP hunt method profile",
            {
                "class": getattr(self, "mcp_profile_class", "unassigned"),
                "stage": stage,
                "steps": getattr(self, "movement_steps", 0),
                "elapsed": round(now - getattr(self, "mcp_profile_started", now), 6),
                "calls": sum(entry["count"] for entry in profile.values()),
                "rpcSeconds": round(sum(entry["seconds"] for entry in profile.values()), 6),
                "methods": methods,
                "omittedMethods": max(0, len(profile) - len(methods)),
            },
            flush=True,
        )

    def probeCoordinateReadCosts(self):
        expected = self.fullJsonCoords()
        turn_before = self.call(self.game_map, "getTurn")
        state_before = self.state()
        resources_before = (self.call(self.player, "getHp"), self.call(self.player, "getMana"))
        full_samples, scalar_samples = [], []
        for index in range(21):
            started = perf_counter()
            full_coords = self.fullJsonCoords()
            full_elapsed = perf_counter() - started
            started = perf_counter()
            scalar_coords = tuple(self.call(self.player, "getNumericProperty", "pos" + axis) for axis in "xyz")
            scalar_elapsed = perf_counter() - started
            self.assertEqual(expected, full_coords)
            self.assertEqual(full_coords, scalar_coords)
            self.assertEqual(turn_before, self.call(self.game_map, "getTurn"))
            self.assertEqual(state_before, self.state())
            if index:
                full_samples.append(full_elapsed)
                scalar_samples.append(scalar_elapsed)
        self.assertEqual(resources_before, (self.call(self.player, "getHp"), self.call(self.player, "getMana")))
        print(
            "MCP hunt paired coordinate read probe",
            {
                "class": getattr(self, "mcp_profile_class", "unassigned"),
                "samples": 20,
                "warmup": 1,
                "coords": expected,
                "turn": turn_before,
                "fullJsonRpcPerSample": 1,
                "scalarRpcPerSample": 3,
                "fullJsonMedianSeconds": round(median(full_samples), 6),
                "scalarMedianSeconds": round(median(scalar_samples), 6),
                "fullJsonTotalSeconds": round(sum(full_samples), 6),
                "scalarTotalSeconds": round(sum(scalar_samples), 6),
            },
            flush=True,
        )

    def state(self):
        return json.loads(
            self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry").removeprefix("octobogzHunt.v1:")
        )

    def refresh(self):
        self.game_map = self.call(self.game, "getMap")
        self.player = self.call(self.game_map, "getPlayer")
        registered = self.call(self.game_map, "getObjectByName", self.call(self.player, "getName"))
        self.assertEqual(self.player["__handle__"], registered["__handle__"])

    def fullJsonCoords(self, handle=None):
        data = json.loads(self.engine("jsonify", handle or self.player))["properties"]
        return tuple(data["pos" + axis] for axis in "xyz")

    def coords(self, handle=None):
        actor = handle or self.player
        return tuple(self.call(actor, "getNumericProperty", "pos" + axis) for axis in "xyz")

    def snapshot(self, stage):
        data = json.loads(self.engine("jsonify", self.player))["properties"]
        coords = self.coords()
        self.assertEqual(
            tuple(data["pos" + axis] for axis in "xyz"), coords, "Scalar coordinates must match the native snapshot"
        )
        result = {
            "stage": stage,
            "coords": coords,
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
        self.reportMcpProfile(stage)
        return result

    def step(self, destination):
        origin = self.coords()
        defeat_before = self.call(self.player, "getStringProperty", "uiDefeatReceipt")
        self.assertEqual(1, sum(abs(a - b) for a, b in zip(origin, destination)))
        tile = self.call(self.game_map, "getTile", *destination)
        self.assertIsNotNone(tile, destination)
        self.assertTrue(self.call(tile, "getBoolProperty", "canStep"), destination)
        capture = getattr(self, "capture_before_move", None)
        if capture:
            capture(origin, destination)
        # Native adjacent moveTo checks CMap.canStep before committing, including object footprints.
        self.call(self.player, "moveTo", *destination)
        self.pump()
        if capture:
            capture(origin, destination)
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
        if self.movement_steps % 128 == 0:
            self.reportMcpProfile("adjacent movement checkpoint")
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

    def collectAuthoredRetreatScroll(self):
        before = self.call(self.player, "countItems", "TownPortalScroll")
        self.walkTo("townPortalScroll", allow_removed=True)
        self.assertIsNone(self.call(self.game_map, "getObjectByName", "townPortalScroll"))
        self.assertEqual(before + 1, self.call(self.player, "countItems", "TownPortalScroll"))
        self.snapshot("collected authored retreat scroll")

    def retreatWithOwnedAuthoredScroll(self):
        scrolls = [
            item for item in self.call(self.player, "getItems") if self.call(item, "getTypeId") == "TownPortalScroll"
        ]
        self.assertEqual(1, len(scrolls), "Retreat must use the actual collected, owned source scroll")
        before = self.snapshot("before owned town portal retreat")
        hunt_before = self.state()
        count_before = self.call(self.player, "countItems", "TownPortalScroll")
        self.call(self.player, "useItem", scrolls[0])
        self.pump()
        self.assertEqual(self.game_map, self.call(self.game, "getMap"))
        self.assertEqual(self.player, self.call(self.game_map, "getPlayer"))
        entry = tuple(self.call(self.game_map, method) for method in ("getEntryX", "getEntryY", "getEntryZ"))
        self.assertEqual((110, 111, 0), entry)
        self.assertEqual(entry, self.coords())
        self.assertEqual(before["defeat"], self.call(self.player, "getStringProperty", "uiDefeatReceipt"))
        self.assertEqual(hunt_before, self.state())
        self.assertEqual(count_before - 1, self.call(self.player, "countItems", "TownPortalScroll"))
        self.assertGreater(self.call(self.player, "getHp"), 0)
        self.snapshot("owned town portal retreat complete")
        self.recoverOnRoadPair((110, 111, 0), (109, 111, 0), "town portal road recovery")

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

    def nearbyAuthoredPritz(self, anchor):
        current = self.coords()
        candidates = []
        for actor in self.call(self.game_map, "getObjects"):
            if self.call(actor, "getTypeId") != "Pritz" or not self.call(actor, "isAlive"):
                continue
            if self.call(actor, "getStringProperty", "affiliation") != "gooby":
                continue
            coords = self.coords(actor)
            if coords[2] == anchor[2] and abs(coords[0] - anchor[0]) + abs(coords[1] - anchor[1]) <= 55:
                candidates.append((sum(abs(a - b) for a, b in zip(current, coords)), self.call(actor, "getName")))
        return sorted(candidates)

    def nearbyRolfEnemies(self):
        return self.nearbyAuthoredPritz((19, 10, 0))

    def marketTransactionState(self):
        player = json.loads(self.engine("jsonify", self.player))["properties"]
        return {
            "player": {key: value for key, value in player.items() if key not in ("items", "gold")},
            "turn": self.call(self.game_map, "getTurn"),
            "registry": self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry"),
            "quests": self.questNames(),
            "completed": self.questNames("getCompletedQuests"),
        }

    def prepareHealingStockAtAuthoredMarket(self):
        self.walkTo("market1")
        market_actor = self.object("market1")
        self.assertEqual((106, 111, 0), self.coords(market_actor))
        self.assertEqual(self.coords(market_actor), self.coords())
        market = self.call(market_actor, "getObjectProperty", "market")
        self.assertIsNotNone(market)
        inventory = self.call(self.player, "getItems")
        strong = [
            item
            for item in inventory
            if self.call(item, "hasTag", "heal") and self.call(item, "getNumericProperty", "power") > 1
        ]
        self.assertTrue(strong, "Ordinary preparation must retain genuinely earned stronger healing stock")
        weak = [
            item
            for item in inventory
            if self.call(item, "hasTag", "heal")
            and not self.call(item, "hasTag", "mana")
            and self.call(item, "getNumericProperty", "power") == 1
            and self.call(item, "getBoolProperty", "singleUse")
        ]
        weak.sort(key=lambda item: (self.call(item, "getTypeId"), self.call(item, "getName")))
        self.assertLessEqual(len(weak), 128)
        before = self.marketTransactionState()
        sold = []
        for item in weak:
            identity = item["__handle__"]
            self.assertIn(identity, [owned["__handle__"] for owned in self.call(self.player, "getItems")])
            gold_before = self.call(self.player, "getGold")
            price = self.call(market, "getBuyCost", item)
            self.assertGreater(price, 0)
            self.call(market, "buyItem", self.player, item)
            self.assertEqual(gold_before + price, self.call(self.player, "getGold"))
            self.assertNotIn(identity, [owned["__handle__"] for owned in self.call(self.player, "getItems")])
            self.assertIn(identity, [stocked["__handle__"] for stocked in self.call(market, "getItems")])
            self.assertEqual(before, self.marketTransactionState())
            sold.append({"name": self.call(item, "getName"), "typeId": self.call(item, "getTypeId"), "price": price})
        for item in strong:
            self.assertIn(item["__handle__"], [owned["__handle__"] for owned in self.call(self.player, "getItems")])
        print("MCP hunt ordinary authored market preparation", {"sold": sold, "strongStock": len(strong)}, flush=True)

    def prepareThroughRolf(self):
        self.recoverOnRoadPair((44, 106, 0), (44, 107, 0), "opened gate road recovery")
        self.snapshot("before original Rolf cave")
        self.walkTo("cave1", allow_removed=True)
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "completed_rolf"))
        self.assertGreater(self.call(self.player, "countItems", "skullOfRolf"), 0)
        self.snapshot("after original Rolf cave")
        for _ in range(32):
            if self.call(self.player, "getLevel") >= 4:
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
        self.assertGreaterEqual(self.call(self.player, "getLevel"), 3, self.snapshot("Rolf preparation complete"))
        self.recoverOnRoadPair((9, 36, 0), (9, 37, 0), "before hunt Rolf road recovery")

    def prepareThroughCatacombs(self):
        if self.call(self.player, "getLevel") < 4:
            # Follow authored roads; the grass shortcut crosses the occupied cave before recovery.
            for waypoint in ((9, 39, 0), (8, 39, 0), (8, 49, 0), (9, 49, 0), (9, 81, 0), (30, 81, 0), (30, 115, 0)):
                self.walkCoords(waypoint)
            self.recoverOnRoadPair((57, 115, 0), (58, 115, 0), "before original catacombs road recovery")
            self.assertIsNotNone(self.call(self.game_map, "getObjectByName", "catacombs"))
            relics_before = self.call(self.player, "countItems", "holyRelic")
            self.snapshot("before original catacombs")
            self.walkTo("catacombs", allow_removed=True)
            self.assertIsNone(self.call(self.game_map, "getObjectByName", "catacombs"))
            self.assertEqual(relics_before + 1, self.call(self.player, "countItems", "holyRelic"))
            self.snapshot("after original catacombs arrival")
            for _ in range(18):
                if self.call(self.player, "getLevel") >= 4:
                    break
                candidates = self.nearbyAuthoredPritz((57, 103, 0))
                if not candidates:
                    break
                if self.call(self.player, "getHpRatio") < 75:
                    self.recoverOnRoadPair((57, 115, 0), (58, 115, 0), "catacombs road recovery")
                    candidates = self.nearbyAuthoredPritz((57, 103, 0))
                    if not candidates:
                        break
                name = candidates[0][1]
                before = self.snapshot("before authored catacombs Pritz " + name)
                self.walkTo(name, allow_removed=True)
                after = self.snapshot("after authored catacombs Pritz " + name)
                self.assertIsNone(self.call(self.game_map, "getObjectByName", name))
                self.assertGreater(
                    after["exp"], before["exp"], "Catacombs preparation must earn real combat experience"
                )
            self.recoverOnRoadPair((57, 115, 0), (58, 115, 0), "after catacombs road recovery")
        self.assertGreaterEqual(self.call(self.player, "getLevel"), 4, self.snapshot("earned hunt preparation"))
        self.assertGreaterEqual(self.call(self.player, "getNumericProperty", "exp"), 6000)

    def finishOriginalMainQuest(self):
        self.snapshot("before original Gooby approach after hunt")
        self.recoverOnRoadPair((109, 100, 0), (109, 101, 0), "Gooby road recovery")
        self.walkTo("gooby1", allow_removed=True)
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "completed_gooby"))
        self.assertIn("mainQuest", self.questNames("getCompletedQuests"))
        self.snapshot("original MainQuest complete after hunt")

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

    def trackLivingHuntActors(self):
        for slot, actor in self.livingActors().items():
            self.assertIsNotNone(actor, slot)
            self.assertTrue(self.call(actor, "isAlive"), slot)
            if self.hunt_actors.get(slot) != actor:
                self.hunt_actors[slot] = actor
                resources = {
                    "slot": slot,
                    "name": self.call(actor, "getName"),
                    "hp": self.call(actor, "getHp"),
                    "mana": self.call(actor, "getMana"),
                }
                self.assertGreater(resources["hp"], 0, resources)
                print("MCP hunt tracked living actor", resources, flush=True)

    def captureHuntActors(self, origin, destination):
        distance = min(
            sum(abs(a - b) for a, b in zip(coords, self.hunt_lair_coords)) for coords in (origin, destination)
        )
        if distance <= 12:
            self.trackLivingHuntActors()

    def assertSlotDefeated(self, slot):
        record = self.state()["slots"][slot]
        actor = self.hunt_actors.get(slot)
        self.assertIsNotNone(actor, "The actual living actor must be captured before its fight: " + slot)
        self.assertEqual(record["name"], self.call(actor, "getName"))
        self.assertFalse(self.call(actor, "isAlive"), slot)
        self.assertIsNone(self.call(self.game_map, "getObjectByName", record["name"]), slot)
        self.assertEqual("dead", record["status"])
        if slot not in self.confirmed_dead:
            self.observeActors("confirmed actual " + slot + " defeat", {slot: actor})
            self.confirmed_dead.add(slot)

    def enterHunt(self):
        lair = self.object("cave2")
        self.hunt_lair_coords = self.coords(lair)
        self.capture_before_move = self.captureHuntActors
        before = self.snapshot("before entering the hunt lair")
        healing_stock = [
            {"type": self.call(item, "getTypeId"), "power": self.call(item, "getNumericProperty", "power")}
            for item in self.call(self.player, "getItems")
            if self.call(item, "hasTag", "heal")
        ]
        print("MCP hunt actual earned healing stock", healing_stock, flush=True)
        self.walkTo("cave2")
        self.assertIn(self.state()["stage"], ("scout", "brood"))
        if self.state()["slots"]["scout"]["status"] == "dead":
            self.assertSlotDefeated("scout")
            self.assertGreater(self.call(self.player, "getNumericProperty", "exp"), before["exp"])
        else:
            self.defeat("scout")
        self.assertEqual("brood", self.state()["stage"])
        self.assertFalse(self.call(self.game_map, "getBoolProperty", "octobogzHuntCleared"))
        self.trackLivingHuntActors()

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
                "hp": self.call(actor, "getHp"),
                "mana": self.call(actor, "getMana"),
            }
            print("MCP hunt actor combat", observation, flush=True)
            self.phase_observations.append(observation)

    def defeat(self, slot):
        record = self.state()["slots"][slot]
        if record["status"] == "dead":
            self.assertSlotDefeated(slot)
            return
        self.assertEqual("living", record["status"])
        self.trackLivingHuntActors()
        actors = self.livingActors()
        self.snapshot("before " + slot)
        self.walkTo(record["name"], allow_removed=True)
        self.snapshot("after " + slot)
        self.observeActors("after " + slot, actors)
        self.assertGreater(
            self.call(self.player, "getNumericProperty", "hp"), 0, "Ordinary player loadout failed against " + slot
        )
        self.assertSlotDefeated(slot)

    @staticmethod
    def itemIdentity(item):
        if item is None:
            return None
        properties = item["properties"]
        return {key: properties.get(key, 0 if key == "power" else "") for key in ("name", "typeId", "power")}

    def captureDecisionReplayState(self, slot):
        data = json.loads(self.engine("jsonify", self.player))["properties"]
        player = {
            "name": self.call(self.player, "getName"),
            "classId": self.mcp_profile_class,
            "typeId": self.call(self.player, "getTypeId"),
            "level": self.call(self.player, "getLevel"),
            "exp": data["exp"],
            "hp": data["hp"],
            "mana": data["mana"],
            "gold": self.call(self.player, "getGold"),
            "hpMax": self.call(self.player, "getHpMax"),
            "manaMax": self.call(self.player, "getManaMax"),
            "effects": data["effects"],
            "coords": {axis: data["pos" + axis] for axis in "xyz"},
            "raceId": data.get("raceId", ""),
            "archetypeRaceId": self.call(self.player, "getArchetypeRaceId"),
            "archetypeClassId": self.call(self.player, "getArchetypeClassId"),
            "baseStats": data["baseStats"],
            "levelStats": data["levelStats"],
            "equipment": {slot: self.itemIdentity(item) for slot, item in (data.get("equipped") or {}).items()},
            "inventory": sorted(
                (self.itemIdentity(item) for item in data.get("items") or []),
                key=lambda item: (item["name"], item["typeId"], item["power"]),
            ),
        }
        actors = []
        for actor_slot, actor in sorted(self.livingActors().items()):
            actors.append(
                {
                    "slot": actor_slot,
                    "name": self.call(actor, "getName"),
                    "typeId": self.call(actor, "getTypeId"),
                    "level": self.call(actor, "getLevel"),
                    "hp": self.call(actor, "getHp"),
                    "mana": self.call(actor, "getMana"),
                    "phase": self.call(actor, "getStringProperty", "octobogzCombatPhase"),
                    "role": self.call(actor, "getStringProperty", "octobogzCombatRole"),
                }
            )
        return {
            "saveSlot": slot,
            "playerBefore": player,
            "actorsBefore": actors,
            "registryBefore": self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry"),
        }

    def validateDecisionReplay(self, result, expected):
        self.assertTrue(result["success"])
        self.assertEqual("deterministic-manual-earned-save", result["mode"])
        self.assertEqual(expected["saveSlot"], result["saveSlot"])
        self.assertIsInstance(result["playerComposedStatsBefore"], dict)
        self.assertIsInstance(result["playerComposedStatsBefore"]["properties"], dict)
        self.assertEqual(100, result["seed"])
        for field in ("playerBefore", "actorsBefore", "registryBefore"):
            self.assertEqual(expected[field], result[field], field)
        self.assertTrue(result["cardinalVerified"])
        self.assertGreater(result["movements"], 0)
        self.assertLessEqual(result["movements"], 512)
        self.assertTrue(result["playerAlive"])
        self.assertTrue(result["defeatReceiptUnchanged"])
        self.assertTrue(result["sourceUnchanged"])
        barriers = [decision for decision in result["decisions"] if decision["action"] == "Barrier"]
        self.assertEqual(len(barriers), result["paidBarriers"])
        self.assertGreater(result["paidBarriers"], 0)
        for decision in barriers:
            self.assertEqual(17, decision["cost"], "The learned Barrier must retain its authored cost")
            self.assertGreaterEqual(decision["refund"], 0)
            self.assertLessEqual(decision["refund"], decision["cost"])
            self.assertEqual(decision["cost"] - decision["refund"], decision["manaBefore"] - decision["manaAfter"])
        self.assertTrue(any(decision["refund"] < decision["cost"] for decision in barriers))
        consumed_names = set()
        for decision in (entry for entry in result["decisions"] if entry["action"] == "UseItem"):
            self.assertTrue(decision["consumedOnce"])
            self.assertTrue(decision["healOnlyDisposable"])
            self.assertIn(decision["item"], expected["playerBefore"]["inventory"])
            self.assertNotIn(decision["item"]["name"], consumed_names)
            consumed_names.add(decision["item"]["name"])
            self.assertEqual(0, decision["cost"])
            self.assertEqual(0, decision["refund"])
            self.assertEqual(decision["manaBefore"], decision["manaAfter"])
            self.assertEqual(decision["enemyHpBefore"], decision["enemyHpAfter"])
            self.assertEqual(decision["enemyManaBefore"], decision["enemyManaAfter"])
            self.assertEqual(decision["inventoryCountBefore"] - 1, decision["inventoryCountAfter"])
            self.assertGreater(decision["hpAfter"], decision["hpBefore"])
            self.assertEqual(
                min(decision["hpMax"], decision["hpBefore"] + decision["item"]["power"] * decision["hpMax"] // 5),
                decision["hpAfter"],
            )
        self.assertTrue(result["positivePackets"], "A real paid defensive turn must expose a positive pulse")
        for packet in result["positivePackets"]:
            self.assertIn(packet["slot"], ("brood", "alpha"))
            self.assertTrue(packet["pulse"])
            self.assertTrue(packet["effect"])
            self.assertGreater(packet["damage_roll"], 0)
            self.assertEqual(1, packet["shadow"])
            self.assertEqual(packet["damage_roll"] - 1, packet["normal"])
            self.assertEqual(5, packet["enemyManaBefore"] - packet["enemyManaAfter"])
            effect = packet["linkedEffect"]
            self.assertEqual("octobogzShadowPulseEffect", effect["typeId"])
            actor = next(actor for actor in expected["actorsBefore"] if actor["slot"] == packet["slot"])
            self.assertEqual(actor["name"], effect["caster"])
            self.assertEqual(expected["playerBefore"]["name"], effect["victim"])
            self.assertEqual(1, effect["duration"])
            self.assertEqual(1, effect["timeTotal"])
            self.assertIn(effect["time"], (0, 1))
            bonus = effect["bonus"]["properties"]
            self.assertEqual(-1, bonus["shadowResist"])
            self.assertTrue(
                all(value == 0 for key, value in bonus.items() if key != "shadowResist" and isinstance(value, int))
            )
        return result["positivePackets"]

    def requireDecisionReplayExecutable(self):
        import test as harness

        executable_name = "monster_balance_unit_tests" + (".exe" if os.name == "nt" else "")
        candidates = [Path(directory) / executable_name for directory in (*harness.extension_dirs, self.build_dir)]
        executable = next((path for path in candidates if path.is_file()), None)
        if executable is None:
            if os.environ.get("CI"):
                self.fail("The required native saved-hero decision fixture is missing: " + str(candidates))
            self.skipTest("The current monster_balance_unit_tests binary is required for the saved-hero replay")
        return executable

    def replaySavedOrdinaryDefensiveDecisions(self, slot, save_path, expected):
        executable = getattr(self, "decision_executable", None) or self.requireDecisionReplayExecutable()
        environment = os.environ.copy()
        if os.name == "nt":
            cache = self.build_dir / "CMakeCache.txt"
            values = {}
            if cache.is_file():
                for line in cache.read_text(encoding="utf-8").splitlines():
                    if "=" in line and ":" in line.split("=", 1)[0]:
                        key, value = line.split("=", 1)
                        values[key.split(":", 1)[0]] = value
            python_path = Path(values.get("Python3_EXECUTABLE", sys.executable)).parent
            installed = values.get("_VCPKG_INSTALLED_DIR") or values.get("VCPKG_INSTALLED_DIR")
            triplet = values.get("VCPKG_TARGET_TRIPLET")
            runtime_paths = [executable.parent, self.build_dir, python_path]
            if installed and triplet:
                runtime_paths.append(Path(installed) / triplet / "bin")
            environment["PYTHONHOME"] = str(python_path)
            environment["PATH"] = os.pathsep.join(map(str, runtime_paths)) + os.pathsep + environment.get("PATH", "")
        before_hash = sha256(save_path.read_bytes()).hexdigest()
        live_before = (self.game, self.game_map, self.player, self.call(self.game_map, "getTurn"), self.state())
        resources_before = (self.call(self.player, "getHp"), self.call(self.player, "getMana"), self.coords())
        try:
            completed = subprocess.run(
                [str(executable), "--hunt-decision", slot],
                cwd=self.build_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, completed.returncode, (completed.stdout[-8192:], completed.stderr[-8192:]))
            marker = "NATIVE_HUNT_DECISION_RESULT "
            results = [
                json.loads(line[len(marker) :]) for line in completed.stdout.splitlines() if line.startswith(marker)
            ]
            self.assertEqual(1, len(results), completed.stdout[-8192:])
            packets = self.validateDecisionReplay(results[0], expected)
            print("MCP hunt deterministic ordinary defensive replay", results[0], flush=True)
            return packets
        except subprocess.TimeoutExpired as error:
            for name in ("stdout", "stderr"):
                output = getattr(error, name) or ""
                if isinstance(output, bytes):
                    output = output.decode("utf-8", errors="replace")
                print("Saved hunt decision replay timeout " + name, output[-8192:], file=sys.stderr, flush=True)
            raise
        finally:
            self.assertEqual(
                before_hash, sha256(save_path.read_bytes()).hexdigest(), "Replay must not rewrite the save"
            )
            self.assertEqual(
                live_before, (self.game, self.game_map, self.player, self.call(self.game_map, "getTurn"), self.state())
            )
            self.assertEqual(
                resources_before, (self.call(self.player, "getHp"), self.call(self.player, "getMana"), self.coords())
            )

    def assertMeaningfulPulseWitness(self):
        self.assertTrue(self.manual_phase_observations, "The ordinary saved-hero defensive replay remains mandatory")
        positive_packets = [
            observed
            for observed in self.phase_observations + self.manual_phase_observations
            if observed["pulse"] and observed["damage_roll"] > 0 and observed["shadow"] == 1
        ]
        self.assertTrue(positive_packets, "Real combat must exercise a positive shadow packet, not only a phase flag")
        for observed in positive_packets:
            self.assertEqual(
                observed["damage_roll"] - 1, observed["normal"], "The original damage budget must be preserved"
            )

    def testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce(self):
        self.decision_executable = self.requireDecisionReplayExecutable()
        self.phase_observations = []
        self.manual_phase_observations = []
        for player_class in ("Warrior", "Sorcerer"):
            with self.subTest(player_class=player_class):
                self.resetMcpProfile(player_class)
                self.hunt_actors, self.confirmed_dead = {}, set()
                self.capture_before_move = None
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
                self.collectAuthoredRetreatScroll()
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
                self.probeCoordinateReadCosts()
                self.prepareThroughCatacombs()
                if player_class == "Sorcerer":
                    self.prepareHealingStockAtAuthoredMarket()
                self.walkTo("questGiver")
                if player_class == "Warrior":
                    self.action(self.dialog("dialog"), "accept_quest")
                    self.assertIn("octoBogzQuest", self.questNames())
                self.walkTo("ambientOctobogzNet")
                self.recoverOnRoadPair((118, 21, 0), (118, 20, 0), "before hunt road recovery")
                self.enterHunt()

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
                    self.trackLivingHuntActors()
                    self.snapshot("partial reload")
                    decision_state = self.captureDecisionReplayState(slot) if player_class == "Warrior" else None
                    gold_before_final = self.call(self.player, "getGold")
                    self.retreatWithOwnedAuthoredScroll()
                    self.recoverOnAuthoredRoad()
                    self.defeat("alpha")
                    if self.state()["slots"]["brood"]["status"] != "dead":
                        self.assertIsNotNone(self.call(self.game_map, "getObjectByName", "cave2"))
                        self.assertFalse(self.call(self.game_map, "getBoolProperty", "OCTOBOGZ_SLAIN"))
                        self.recoverOnAuthoredRoad()
                    self.defeat("brood")
                    self.assertEqual({"scout", "brood", "alpha"}, self.confirmed_dead)
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
                    self.finishOriginalMainQuest()
                    self.assertGreater(self.movement_steps, 100)
                    self.snapshot("completed")
                    print(
                        "MCP OctoBogz real combat completed for",
                        player_class,
                        "adjacent steps",
                        self.movement_steps,
                        flush=True,
                    )
                    if decision_state is not None:
                        self.manual_phase_observations += self.replaySavedOrdinaryDefensiveDecisions(
                            slot, save_path, decision_state
                        )
                finally:
                    save_path.unlink(missing_ok=True)
                    save_path.with_suffix(".json.bak").unlink(missing_ok=True)
        self.assertMeaningfulPulseWitness()


if __name__ == "__main__":
    unittest.main()
