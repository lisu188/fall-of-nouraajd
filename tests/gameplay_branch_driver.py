# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Restricted natural-play client; fixture mutations never pass through its action surface."""

from collections import deque
from functools import lru_cache

from tests.gameplay_branch_journals import verifyJournals
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_METHODS = frozenset(
    {
        "addGold",
        "addItem",
        "addItems",
        "addQuest",
        "addObjectByName",
        "removeObjectByName",
        "replaceTile",
        "setCoords",
        "setNumericProperty",
        "setBoolProperty",
        "setStringProperty",
        "incProperty",
        "heal",
        "healProc",
        "hurt",
        "onAction",
        "changeMap",
        "requestMapChange",
    }
)
NATIVE_SET_PROPERTIES = frozenset(
    {
        "items",
        "quests",
        "completedQuests",
        "actions",
        "effects",
        "classTracks",
        "templates",
        "coveredSlots",
        "subtypes",
        "tags",
    }
)


def canonicalNativeState(value, property_name=None):
    """Compare reflected native sets by content without changing ordered arrays or identities."""
    if isinstance(value, dict):
        return {key: canonicalNativeState(item, key) for key, item in value.items()}
    if isinstance(value, list):
        result = [canonicalNativeState(item) for item in value]
        if property_name in NATIVE_SET_PROPERTIES:
            result.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return result
    return value


def caseSeed(case_id, class_id):
    return int.from_bytes(hashlib.sha256(f"nouraajd:{case_id}:{class_id}".encode()).digest()[:4], "big")


@lru_cache(maxsize=16)
def mapDefinitions(map_id):
    result = {}
    for directory in (ROOT / "res/config", ROOT / "res/maps" / map_id):
        for path in sorted(directory.glob("*.json")):
            if path.name != "map.json":
                document = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(document, dict):
                    result.update(document)
    return result


@lru_cache(maxsize=16)
def authoredRoadCells(map_id):
    document = json.loads((ROOT / "res/maps" / map_id / "map.json").read_text(encoding="utf-8"))
    road_ids = {
        tileset["firstgid"] + int(local_id)
        for tileset in document["tilesets"]
        for local_id, properties in tileset.get("tileproperties", {}).items()
        if properties.get("type") == "RoadTile"
    }
    return frozenset(
        (index % document["width"], index // document["width"], int(layer["properties"]["level"]))
        for layer in document["layers"]
        if layer["type"] == "tilelayer"
        for index, tile in enumerate(layer["data"])
        if tile in road_ids
    )


def readNewNativeTrace(path, positions, after_seq=0):
    """Read new bounded native trace records with caller-owned cursors across ordinary file rotation."""
    path = Path(path)
    records = {}
    staged_positions = {}
    files_present = False
    for candidate in (Path(str(path) + ".1"), path):
        if not candidate.is_file():
            continue
        files_present = True
        with candidate.open(encoding="utf-8") as source:
            first_line = source.readline()
            if not first_line:
                continue
            old_first, old_offset = positions.get(str(candidate), (None, 0))
            source.seek(old_offset if first_line == old_first else 0)
            for line in source:
                record = json.loads(line)
                seq = record.get("seq")
                if type(seq) is not int or seq <= 0:
                    raise AssertionError(("Invalid native trace sequence", record))
                if seq > after_seq:
                    if seq in records and records[seq] != record:
                        raise AssertionError(("Conflicting native trace records", seq))
                    records[seq] = record
            staged_positions[str(candidate)] = (first_line, source.tell())
    if after_seq > 0 and not files_present:
        raise AssertionError(("Native trace files disappeared", {"path": str(path), "afterSeq": after_seq}))
    ordered = tuple(records[seq] for seq in sorted(records))
    for expected, record in enumerate(ordered, after_seq + 1):
        if record["seq"] != expected:
            raise AssertionError(
                ("Native trace evidence was lost", {"expectedSeq": expected, "observedSeq": record["seq"]})
            )
    positions.update(staged_positions)
    return ordered


def resolveDefinition(definitions, identity, seen=()):
    if identity in seen:
        raise AssertionError(f"Cyclic resource reference: {seen + (identity,)}")
    value = definitions.get(identity, {})
    parent = resolveDefinition(definitions, value["ref"], seen + (identity,)) if "ref" in value else {}
    return {**parent, **value, "properties": {**parent.get("properties", {}), **value.get("properties", {})}}


class GameplayBranchDriver:
    def __init__(self, test, harness, session, case, class_id, build_dir):
        self.test, self.harness, self.session = test, harness, session
        self.case, self.class_id, self.race_id = case, class_id, case.race
        self.build_dir = Path(build_dir)
        self.seed = caseSeed(case.id, class_id)
        self.game = self.game_map = self.player = None
        self.map_name = None
        self.recoveryEnabled = True
        self.branches = {}
        self.actions = deque(maxlen=128)
        self.steps = self.turns = self.combats = 0
        self._save_paths = []
        self._defeat_receipt = ""
        self._hunt_adapter = None
        self._refreshing = False
        self._dialog_positions = {}
        self.action_path = None
        self.trace_path = None
        self._combat_trace_positions = {}
        self._combat_trace_seq = 0
        self._combat_failure = None
        self._recorded_actions = 0
        self._coordinate_point = None
        self._ephemeral_handles = set()
        self._coordinate_values = {}

    def record(self, action, *, replay=False):
        self.actions.append(action)
        if replay and self.action_path is not None:
            self._recorded_actions += 1
            if self._recorded_actions > 50000:
                self.test.fail("Gameplay action budget exhausted (50000); retain the recorded failing route")
            with Path(self.action_path).open("a", encoding="utf-8") as output:
                output.write(json.dumps(action, ensure_ascii=False) + "\n")

    def engine(self, name, *args):
        self.test.assertNotIn(
            name, {"randint", "CGameLoader.loadGui"}, "Routes cannot manipulate randomness or open GUI"
        )
        self.record({"engine": name, "args": args}, replay=name not in {"jsonify", "event_loop.instance"})
        return self.harness._mcp_engine_call(self.session, name, list(args), timeout=90)

    def _rawCall(self, handle, method, *args):
        return self.harness._mcp_handle_call(self.session, handle, method, list(args), timeout=90)

    def call(self, handle, method, *args):
        self.test.assertNotIn(method, FORBIDDEN_METHODS, f"Forbidden gameplay fixture mutation: {method}")
        if method == "moveTo":
            self.test.assertEqual(self.player["__handle__"], handle["__handle__"])
            self.test.assertEqual(1, sum(abs(a - b) for a, b in zip(self.coords(), args)))
        if method in {"useItem", "equipItem"}:
            item = args[-1]
            if item is not None:
                self.test.assertIn(
                    item["__handle__"], {entry["__handle__"] for entry in self.call(self.player, "getItems")}
                )
        if method == "capture":
            self.test.assertEqual(1, len(args))
            self.test.assertEqual(self.player["__handle__"], args[0]["__handle__"])
            self.test.assertEqual(self.game_map["__handle__"], self.call(handle, "getMap")["__handle__"])
            name = self.call(handle, "getName")
            self.test.assertEqual(handle["__handle__"], self.object(name)["__handle__"])
            self.test.assertTrue(self.call(handle, "getStringProperty", "campaign_objectiveId"))
            here, there = self.coords(handle), self.coords()
            self.test.assertEqual(here[2], there[2])
            self.test.assertLessEqual(max(abs(here[0] - there[0]), abs(here[1] - there[1])), 1)
        action = {"method": method, "handle": handle.get("__handle__"), "args": args}
        if method == "setTarget" and args and isinstance(args[-1], dict):
            coordinates = self._coordinate_values.get(args[-1].get("__handle__"))
            if coordinates is not None:
                action["targetCoordinates"] = coordinates
        self.record(
            action,
            replay=method
            in {
                "move",
                "moveTo",
                "setTarget",
                "useItem",
                "useAction",
                "sealBreach",
                "checkQuests",
                "equipItem",
                "setFightController",
                "invokeAction",
                "sellItem",
                "buyItem",
                "configureTown",
                "capture",
                "run",
            },
        )
        result = self._rawCall(handle, method, *args)
        if method == "getCoords" and isinstance(result, dict) and "__handle__" in result:
            self._ephemeral_handles.add(result["__handle__"])
        consumed = {
            argument["__handle__"]
            for argument in args
            if isinstance(argument, dict) and argument.get("__handle__") in self._ephemeral_handles
        }
        if consumed:
            self.harness._mcp_tool(self.session, "engine_release_handles", {"handles": sorted(consumed)})
            self._ephemeral_handles.difference_update(consumed)
            for identity in consumed:
                self._coordinate_values.pop(identity, None)
        return result

    def properties(self, handle):
        return json.loads(self.engine("jsonify", handle))["properties"]

    def coords(self, handle=None):
        handle = handle or self.player
        return tuple(self.call(handle, "getNumericProperty", "pos" + axis) for axis in "xyz")

    def canStep(self, coords):
        point = self._coordinateHandle(tuple(coords))
        try:
            return self.call(self.game_map, "canStep", point)
        finally:
            identity = point.get("__handle__")
            if identity in self._ephemeral_handles:
                self.harness._mcp_tool(self.session, "engine_release_handles", {"handles": [identity]})
                self._ephemeral_handles.discard(identity)
                self._coordinate_values.pop(identity, None)

    def object(self, name, required=True):
        result = self.call(self.game_map, "getObjectByName", name)
        if required and result is None:
            self.test.fail(f"Missing authored object {self.map_name}/{name}: {self.snapshot()}")
        return result

    def flag(self, name):
        return self.call(self.game_map, "getBoolProperty", name)

    def number(self, name):
        return self.call(self.game_map, "getNumericProperty", name)

    def string(self, name):
        return self.call(self.game_map, "getStringProperty", name)

    def count(self, type_id):
        return self.call(self.player, "countItems", type_id)

    def gold(self):
        return self.call(self.player, "getGold")

    def questNames(self, completed=False):
        key = "completedQuests" if completed else "quests"
        return [
            entry["properties"].get("typeId") or entry["properties"].get("name")
            for entry in self.properties(self.player).get(key) or []
        ]

    def refresh(self):
        if self.game is None or self._refreshing:
            return
        self._refreshing = True
        try:
            world = self.call(self.game, "getMap")
            self.test.assertIsNotNone(world)
            player = self.call(world, "getPlayer")
            self.test.assertIsNotNone(player)
            changed = self.game_map is None or world["__handle__"] != self.game_map["__handle__"]
            if self.player is not None:
                self.test.assertEqual(self.player["__handle__"], player["__handle__"], "Transition replaced the hero")
            self.game_map, self.player = world, player
            self.map_name = self.string("mapName")
            if changed:
                self.automaticCombat()
        finally:
            self._refreshing = False

    def automaticCombat(self):
        template = self.call(self.game, "createObject", self.class_id)
        controller = self.call(template, "getFightController")
        self.call(self.player, "setFightController", controller)

    def assertSurvival(self):
        self.assertNativeCombatOutcomes()
        if self.player is not None:
            if self.call(self.player, "getHp") <= 0:
                self.test.fail(self.snapshot())
            self.test.assertEqual(
                self._defeat_receipt,
                self.call(self.player, "getStringProperty", "uiDefeatReceipt"),
                "A defeated/respawned hero cannot continue a successful route",
            )

    def assertNativeCombatOutcomes(self):
        if self._combat_failure is not None:
            self.test.fail(self._combat_failure)
        if self.trace_path is None:
            return
        try:
            records = readNewNativeTrace(self.trace_path, self._combat_trace_positions, self._combat_trace_seq)
        except (AssertionError, OSError, ValueError) as error:
            self._combat_failure = ("Native combat evidence unavailable", str(error))
            self.test.fail(self._combat_failure)
        for record in records:
            if record.get("event") != "combat_finished":
                continue
            participants = [record.get("attacker"), *record.get("opponents", ())]
            if not any(isinstance(actor, dict) and actor.get("isPlayer") is True for actor in participants):
                continue
            outcome = record.get("outcome")
            # CFightOutcome resolves only AttackerVictory (1) and AttackerDefeat (2).
            if type(outcome) is not int or outcome not in (1, 2):
                self._combat_failure = ("Unresolved native player combat", record)
                self.test.fail(self._combat_failure)
        if records:
            self._combat_trace_seq = records[-1]["seq"]

    def pump(self):
        loop = self.engine("event_loop.instance")
        for _ in range(3):
            self.call(loop, "run")
            self.refresh()
            self.assertSurvival()

    def startMap(self, map_id):
        self._dialog_positions.clear()
        if self.case.initial_reputation is not None:
            self.loadStartingSave(map_id=map_id)
            self.test.assertEqual(map_id, self.map_name)
            return
        self.game_map = self.player = None
        self.game = self.engine("CGameLoader.loadGame")
        self.engine("CGameLoader.startGameWithPlayer", self.game, map_id, self.class_id, self.race_id)
        self.refresh()
        self.test.assertIsNone(self.call(self.game, "getGui"), "Branch routes must remain offscreen")
        self.test.assertEqual(map_id, self.map_name)
        self.assertSurvival()
        self.pump()

    def startCampaign(self, campaign_id):
        self.loadStartingSave(campaign_id=campaign_id)

    def _slot(self, label):
        slot = "mcp-branch-" + uuid.uuid4().hex
        self._save_paths.extend(self.build_dir / "save" / (slot + suffix) for suffix in (".json", ".json.bak"))
        self.record({"checkpoint": label, "slot": slot}, replay=True)
        return slot

    def loadStartingSave(self, *, map_id=None, campaign_id=None):
        slot = self._slot("initial")
        arguments = [
            sys.executable,
            str(ROOT / "tests/gameplay_starting_save.py"),
            "--build-dir",
            str(self.build_dir),
            "--class-id",
            self.class_id,
            "--race-id",
            self.race_id,
            "--slot",
            slot,
            "--seed",
            str(self.seed),
        ]
        if campaign_id:
            arguments += ["--campaign", campaign_id]
        else:
            arguments += ["--map", map_id]
        if self.case.initial_reputation is not None:
            arguments += ["--reputation", str(self.case.initial_reputation)]
        environment = os.environ.copy()
        environment["GAME_PLAYTEST_TRACE"] = "0"
        process = subprocess.run(arguments, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=90)
        self.test.assertEqual(0, process.returncode, process.stdout[-4096:] + process.stderr[-4096:])
        self.test.assertTrue((self.build_dir / "save" / (slot + ".json")).is_file())
        self.record({"startingSave": json.loads(process.stdout.splitlines()[-1])}, replay=True)
        self.game_map = self.player = None
        self.game = self.engine("CGameLoader.loadGame")
        self.engine("CGameLoader.loadSavedGame", self.game, slot)
        self.refresh()
        self.pump()
        if self.case.initial_reputation is not None:
            self.test.assertEqual(
                self.case.initial_reputation, self.call(self.player, "getNumericProperty", "reputation")
            )

    def snapshot(self):
        if self.player is None:
            return {"case": self.case.id, "class": self.class_id, "seed": self.seed}
        return {
            "case": self.case.id,
            "class": self.class_id,
            "seed": self.seed,
            "map": self.map_name,
            "coords": self.coords(),
            "hp": self.call(self.player, "getHp"),
            "mana": self.call(self.player, "getMana"),
            "gold": self.gold(),
            "turn": self.call(self.game_map, "getTurn"),
        }

    def recover(self):
        if not self.recoveryEnabled or self.call(self.player, "getHpRatio") >= 75:
            return
        items = self.call(self.player, "getItems")
        candidates = []
        for item in items:
            if (
                self.call(item, "hasTag", "heal")
                and not self.call(item, "hasTag", "mana")
                and self.call(item, "getBoolProperty", "singleUse")
            ):
                power = self.call(item, "getNumericProperty", "power")
                if power > 0:
                    candidates.append((power, self.call(item, "getTypeId"), self.call(item, "getName"), item))
        for _, _, _, item in sorted(candidates, key=lambda value: value[:3]):
            if self.call(self.player, "getHpRatio") >= 75:
                break
            hp = self.call(self.player, "getHp")
            owned = {entry["__handle__"] for entry in self.call(self.player, "getItems")}
            self.test.assertIn(item["__handle__"], owned)
            self.call(self.player, "useItem", item)
            self.pump()
            self.test.assertGreater(self.call(self.player, "getHp"), hp, "Owned recovery failed")
            self.test.assertEqual(
                owned - {item["__handle__"]}, {entry["__handle__"] for entry in self.call(self.player, "getItems")}
            )

    def roadRecoveryTarget(self, *, road_cells=None, visited=()):
        """Choose an adjacent native road step that does not approach the nearest live hostile."""
        self.assertSurvival()
        if road_cells is None:
            road_cells = authoredRoadCells(self.map_name)
        origin = self.coords()
        affiliation = self.call(self.player, "getStringProperty", "affiliation")
        hostiles = []
        for actor in self.call(self.game_map, "getObjects"):
            if actor["__handle__"] == self.player["__handle__"]:
                continue
            methods = {entry["name"] for entry in actor.get("pythonMethods", ())}
            if actor.get("__type__") not in {"CCreature", "CPlayer"} and "isAlive" not in methods:
                continue
            if not self.call(actor, "isAlive") or self.call(actor, "isNpc"):
                continue
            if affiliation and self.call(actor, "getStringProperty", "affiliation") == affiliation:
                continue
            coords = self.coords(actor)
            if coords[2] == origin[2]:
                hostiles.append(coords)

        def clearance(coords):
            return min((sum(abs(a - b) for a, b in zip(coords, hostile)) for hostile in hostiles), default=float("inf"))

        origin_clearance = clearance(origin)
        candidates = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            coords = (origin[0] + dx, origin[1] + dy, origin[2])
            if coords not in road_cells:
                continue
            distance = clearance(coords)
            if distance <= 1 or distance < origin_clearance:
                continue
            tile = self.call(self.game_map, "getTile", *coords)
            if tile is None or self.call(tile, "getTypeId") != "RoadTile" or not self.canStep(coords):
                continue
            candidates.append((-distance, visited.count(coords), coords))
        return min(candidates)[2] if candidates else None

    def recoverOnAuthoredRoad(self, *, limit=128, road_cells=None):
        """Recover through bounded native road movement and ordinary map turns, or fail the route."""
        self.test.assertTrue(type(limit) is int and 0 < limit <= 128, "Road recovery permits at most 128 real turns")
        world, map_name, initial_turns = self.game_map["__handle__"], self.map_name, self.turns
        visited = [self.coords()]
        unchanged = 0
        for index in range(limit + 1):
            self.assertSurvival()
            hp, hp_max = self.call(self.player, "getHp"), self.call(self.player, "getHpMax")
            mana, mana_max = self.call(self.player, "getMana"), self.call(self.player, "getManaMax")
            if hp >= hp_max and mana >= mana_max:
                return self.turns - initial_turns
            if index == limit:
                break
            target = self.roadRecoveryTarget(road_cells=road_cells, visited=visited)
            if target is None:
                self.test.fail(("No safe adjacent authored road for recovery", self.snapshot()))
            origin = self.coords()
            controller = self.call(self.player, "getController")
            self.call(controller, "setTarget", self.player, self._coordinateHandle(target))
            self.tick()
            self.steps += 1
            self.test.assertEqual(
                (world, map_name), (self.game_map["__handle__"], self.map_name), "Road recovery left its map"
            )
            arrival = self.coords()
            self.test.assertIn(arrival, (origin, target), "Road recovery left its adjacent native target")
            unchanged = unchanged + 1 if arrival == origin else 0
            if unchanged >= 24:
                self.test.fail(("Native road recovery stalled", target, self.snapshot()))
            visited.append(arrival)
        self.test.fail(("Natural road recovery budget exhausted", limit, self.snapshot()))

    def _validateMovement(self, origin, arrival):
        if origin[2] == arrival[2] and sum(abs(a - b) for a, b in zip(origin, arrival)) <= 1:
            return
        sources = [
            origin,
            *(
                tuple(origin[i] + offset[i] for i in range(3))
                for offset in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))
            ),
        ]
        self.test.assertTrue(
            any(self._hasNavigationEdge(source, arrival) for source in sources),
            ("Unexpected unauthored relocation", origin, arrival),
        )

    def tick(self):
        if self.turns >= 20000:
            self.test.fail(("Route turn budget exhausted", self.snapshot()))
        self.assertSurvival()
        self.recover()
        origin, map_name = self.coords(), self.map_name
        turn = self.call(self.game_map, "getTurn")
        self._captureHuntMovement(origin, origin)
        adapter = self._hunt_adapter
        recovery = getattr(adapter, "recover_before_map_turn", None)
        if recovery:
            recovery()
        self.call(self.game_map, "move")
        self.pump()
        self._captureHuntMovement(origin, self.coords())
        self.turns += 1
        if self.map_name == map_name:
            self.test.assertEqual(turn + 1, self.call(self.game_map, "getTurn"))
            self._validateMovement(origin, self.coords())
        self.assertSurvival()

    def waitTurns(self, limit, predicate):
        for _ in range(limit):
            if predicate():
                return
            self.tick()
        if not predicate():
            self.test.fail(("Turn budget exhausted", limit, self.snapshot()))

    def _captureHuntMovement(self, origin, destination):
        if self.map_name != "nouraajd":
            return
        if self._hunt_adapter is not None:
            self._hunt_adapter.game_map, self._hunt_adapter.player = self.game_map, self.player
        capture = getattr(self._hunt_adapter, "capture_before_move", None)
        if capture:
            capture(origin, destination)

    def _traversedTarget(self, target, arrival):
        distance = sum(abs(a - b) for a, b in zip(target, arrival))
        relocated = distance > 1 or target[2] != arrival[2]
        return relocated and self._hasNavigationEdge(target, arrival)

    def _hasNavigationEdge(self, source, target):
        if source[2] == target[2] and sum(abs(a - b) for a, b in zip(source, target)) <= 1:
            return False
        neighbors = self.call(self.game_map, "getNavigationNeighbors", self._coordinateHandle(source))
        return tuple(target) in {tuple(coords) for coords in neighbors}

    def _coordinateHandle(self, coords):
        # This detached point is only an argument carrier; it is never inserted into the world.
        if self._coordinate_point is None:
            self._coordinate_point = self.call(self.game, "createObject", "CMapObject")
        point = self._coordinate_point
        for axis, value in zip("xyz", coords):
            self._rawCall(point, "setNumericProperty", "pos" + axis, value)
        result = self.call(point, "getCoords")
        self._coordinate_values[result["__handle__"]] = tuple(coords)
        return result

    def navigateCoords(self, coords, *, limit=None):
        target = tuple(coords)
        initial_distance = sum(abs(a - b) for a, b in zip(self.coords(), target))
        budget = limit or max(128, 4 * initial_distance + 128)
        controller = self.call(self.player, "getController")
        self.call(controller, "setTarget", self.player, self._coordinateHandle(target))
        unchanged = 0
        for _ in range(budget):
            if self.coords() == target:
                return
            before, world = self.coords(), self.map_name
            self.tick()
            if self.map_name != world:
                return
            if self._traversedTarget(target, self.coords()):
                return
            unchanged = unchanged + 1 if self.coords() == before else 0
            if unchanged >= 24:
                self.test.fail(("Native navigation stalled", target, self.snapshot()))
            if unchanged:
                # Native combat restores the origin and interrupts the controller's path.
                controller = self.call(self.player, "getController")
                self.call(controller, "setTarget", self.player, self._coordinateHandle(target))
            self.steps += 1
        self.test.fail(("Native route budget exhausted", target, budget, self.snapshot()))

    def navigateTo(self, name, adjacent=False, *, after_tick=None):
        target = self.object(name)
        initial = self.coords(target)
        budget = max(128, 4 * sum(abs(a - b) for a, b in zip(self.coords(), initial)) + 128)
        unchanged = 0
        for _ in range(budget):
            target = self.object(name, required=False)
            if target is None:
                return
            destination = self.coords(target)
            distance = sum(abs(a - b) for a, b in zip(self.coords(), destination))
            if distance <= int(adjacent):
                return
            controller = self.call(self.player, "getController")
            target_coordinates = self.call(target, "getCoords")
            self._coordinate_values[target_coordinates["__handle__"]] = destination
            self.call(controller, "setTarget", self.player, target_coordinates)
            before, world = self.coords(), self.map_name
            self.tick()
            if self.map_name != world:
                return
            if self._traversedTarget(destination, self.coords()):
                return
            unchanged = unchanged + 1 if before == self.coords() else 0
            if unchanged >= 24:
                self.test.fail(("Could not approach authored object", name, self.snapshot()))
            self.steps += 1
            if after_tick is not None:
                after_tick()
        self.test.fail(("Authored route budget exhausted", name, budget, self.snapshot()))

    def step(self, coords):
        destination = tuple(coords)
        origin = self.coords()
        self.test.assertEqual(1, sum(abs(a - b) for a, b in zip(origin, destination)))
        self.recover()
        self._captureHuntMovement(origin, destination)
        self.call(self.player, "moveTo", *destination)
        self.pump()
        self._captureHuntMovement(origin, destination)
        self._validateMovement(origin, self.coords())
        controller = self.call(self.player, "getController")
        self.call(controller, "setTarget", self.player, self._coordinateHandle(self.coords()))
        self.steps += 1
        self.tick()

    def revisit(self, name):
        target = self.object(name)
        destination = self.coords(target)
        if self.coords() == destination:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (destination[0] + dx, destination[1] + dy, destination[2])
                if self.call(self.game_map, "canStep", self._coordinateHandle(neighbor)):
                    self.navigateCoords(neighbor)
                    break
            else:
                self.test.fail(("No authored re-entry route", name, destination))
        self.navigateTo(name)

    def fight(self, name):
        actor = self.object(name)
        self.test.assertTrue(self.call(actor, "isAlive"), name)
        exp = self.call(self.player, "getNumericProperty", "exp")
        self.navigateTo(name)
        if self.object(name, required=False) is not None:
            self.test.fail(("Enemy survived", name, self.snapshot()))
        self.test.assertFalse(self.call(actor, "isAlive"), "Despawn is not a combat victory")
        self.test.assertGreater(self.call(self.player, "getNumericProperty", "exp"), exp)
        self.combats += 1

    def condition(self, dialog_id, condition):
        dialog = self.call(self.game, "createObject", dialog_id)
        return self.call(dialog, "invokeCondition", condition)

    def _dialogStates(self, dialog_id):
        definitions = mapDefinitions(self.map_name)

        def expand(value):
            if isinstance(value, list):
                return [expand(item) for item in value]
            if not isinstance(value, dict):
                return value
            if "ref" in value:
                identity = value["ref"]
                parent = resolveDefinition(definitions, identity)
                value = {
                    **parent,
                    **value,
                    "properties": {**parent.get("properties", {}), **value.get("properties", {})},
                }
                value.pop("ref", None)
            return {key: expand(item) for key, item in value.items()}

        definition = expand(resolveDefinition(definitions, dialog_id))
        return {
            state["properties"]["stateId"]: state["properties"] for state in definition["properties"].get("states", [])
        }

    def choose(self, dialog_id, action, condition=None, *, option_number=None, state_id=None):
        dialog = self.call(self.game, "createObject", dialog_id)
        states = self._dialogStates(dialog_id)
        start = self._dialog_positions.get((self.map_name, dialog_id), "ENTRY")
        queue, visited = deque(["ENTRY" if start == "EXIT" else start]), set()
        while queue:
            current = queue.popleft()
            if current in visited or current == "EXIT":
                continue
            visited.add(current)
            state = states.get(current)
            self.test.assertIsNotNone(state, (dialog_id, current))
            for option in sorted(state.get("options", []), key=lambda value: value["properties"].get("number", 0)):
                value = option["properties"]
                gate = value.get("condition", "")
                visible = not gate or self.call(dialog, "invokeCondition", gate)
                matches = (
                    value.get("action", "") == action
                    and (condition is None or gate == condition)
                    and (option_number is None or value.get("number") == option_number)
                    and (state_id is None or current == state_id)
                )
                if matches:
                    self.test.assertTrue(visible, ("Authored option is unavailable", dialog_id, current, value))
                    if action:
                        self.call(dialog, "invokeAction", action)
                    destination = value.get("nextStateId", "EXIT")
                    if value.get("afterCondition") and self.call(dialog, "invokeCondition", value["afterCondition"]):
                        destination = value.get("afterStateId", destination)
                    self._dialog_positions[(self.map_name, dialog_id)] = destination
                    self.record(
                        {
                            "choice": dialog_id,
                            "state": current,
                            "option": value.get("number"),
                            "action": action,
                            "next": value.get("nextStateId"),
                        },
                        replay=True,
                    )
                    self.pump()
                    return value
                if visible and not value.get("action"):
                    destination = value.get("nextStateId", "EXIT")
                    after_condition = value.get("afterCondition", "")
                    if after_condition:
                        if self.call(dialog, "invokeCondition", after_condition):
                            destination = value.get("afterStateId", destination)
                    queue.append(destination)
        self.test.fail(("No reachable authored dialog option", self.map_name, dialog_id, action, condition, state_id))

    def select(self, dialog_id, state_id, option_number):
        states = self._dialogStates(dialog_id)
        options = [
            value["properties"]
            for value in states[state_id].get("options", [])
            if value["properties"].get("number") == option_number
        ]
        self.test.assertEqual(1, len(options))
        return self.choose(dialog_id, options[0].get("action", ""), option_number=option_number, state_id=state_id)

    def check(self, branch_id, condition, **evidence):
        self.test.assertIn(branch_id, self.case.branches, "Route credited an undeclared branch")
        if not condition:
            self.test.fail((branch_id, evidence, self.snapshot()))
        self.branches[branch_id] = {"state": self.snapshot(), "evidence": evidence}

    def saveAndReload(self, label):
        self.assertSurvival()
        journals = verifyJournals(self)
        initial = self.properties(self.player)
        turn, map_id = self.call(self.game_map, "getTurn"), self.map_name
        slot = self._slot(label)
        self.test.assertTrue(self.engine("CMapLoader.saveWithResult", self.game_map, slot))
        # Saving captures journals. Compare the resulting persisted state, while also
        # checking that this capture did not change the hero's resources or equipment.
        self.test.assertEqual(journals, verifyJournals(self), "Saving changed the observed journal text")
        before = self.properties(self.player)
        for key in ("hp", "mana", "gold", "exp", "level", "reputation", "items", "equipped"):
            self.test.assertEqual(
                canonicalNativeState(initial.get(key), key), canonicalNativeState(before.get(key), key), key
            )
        self.game_map = self.player = None
        self.game = self.engine("CGameLoader.loadGame")
        self.engine("CGameLoader.loadSavedGame", self.game, slot)
        self.refresh()
        self.test.assertEqual(map_id, self.map_name)
        self.test.assertEqual(turn, self.call(self.game_map, "getTurn"))
        after = self.properties(self.player)
        for key in ("hp", "mana", "gold", "exp", "level", "reputation", "posx", "posy", "posz", "raceId"):
            self.test.assertEqual(before.get(key), after.get(key), key)
        for key in set(before) | set(after):
            if key.startswith(("campaign_", "questJournal")) or key in {
                "items",
                "equipped",
                "quests",
                "completedQuests",
            }:
                self.test.assertEqual(
                    canonicalNativeState(before.get(key), key), canonicalNativeState(after.get(key), key), key
                )
        self.pump()
        self.test.assertEqual(journals, verifyJournals(self), "Reload changed the observed journal text")

    def buyAt(self, market_object, item_type, count=1):
        self.navigateTo(market_object)
        market = self.call(self.object(market_object), "getObjectProperty", "market")
        self.test.assertIsNotNone(market)
        for _ in range(count):
            candidates = [item for item in self.call(market, "getItems") if self.call(item, "getTypeId") == item_type]
            self.test.assertTrue(candidates, ("Finite authored stock exhausted", item_type))
            item = min(candidates, key=lambda entry: self.call(entry, "getName"))
            price, gold = self.call(market, "getSellCost", item), self.gold()
            self.test.assertGreaterEqual(gold, price, "Earned funds are insufficient")
            self.test.assertTrue(self.call(market, "sellItem", self.player, item))
            self.test.assertEqual(gold - price, self.gold())
            self.test.assertIn(
                item["__handle__"], {entry["__handle__"] for entry in self.call(self.player, "getItems")}
            )

    def sellAt(self, market_object, item):
        self.navigateTo(market_object)
        self.test.assertIn(item["__handle__"], {entry["__handle__"] for entry in self.call(self.player, "getItems")})
        market = self.call(self.object(market_object), "getObjectProperty", "market")
        price, gold = self.call(market, "getBuyCost", item), self.gold()
        self.call(market, "buyItem", self.player, item)
        self.test.assertEqual(gold + price, self.gold())
        self.test.assertNotIn(item["__handle__"], {entry["__handle__"] for entry in self.call(self.player, "getItems")})

    def craft(self, station, recipe):
        self.navigateTo(station)
        result = self.engine("craftRecipe", self.game, self.object(station), recipe)
        self.pump()
        return result

    def restAtTown(self, name):
        self.navigateTo(name)
        dialog = self.call(self.game, "createObject", "CastleTownRestDialog")
        self.test.assertTrue(self.call(dialog, "configureTown", self.object(name)))
        available = self.call(dialog, "invokeCondition", "canRest")
        gold, hp = self.gold(), self.call(self.player, "getHp")
        self.call(dialog, "invokeAction", "rest")
        self.pump()
        self.test.assertEqual(gold - (10 if available else 0), self.gold())
        self.test.assertEqual(self.call(self.player, "getHpMax") if available else hp, self.call(self.player, "getHp"))
        return available

    def tradeRequests(self):
        self.test.assertIsNotNone(self.trace_path, "The actual callback trade trace is required")
        path = Path(self.trace_path)
        if not path.is_file():
            return []
        return [
            record
            for line in path.read_text(encoding="utf-8").splitlines()
            if (record := json.loads(line)).get("event") == "trade_requested"
        ]

    def hunt(self, method, *args):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        if self._hunt_adapter is None:
            driver = self

            class Adapter(OctobogzMcpWalkthroughTest):
                def call(self, handle, method, *values):
                    return driver.call(handle, method, *values)

                def engine(self, name, *values):
                    return driver.engine(name, *values)

                def pump(self):
                    driver.pump()

                def coords(self, handle=None):
                    return driver.coords(handle)

                def refresh(self):
                    driver.refresh()
                    self.game_map, self.player = driver.game_map, driver.player

                def action(self, dialog, action):
                    return driver.choose(driver.call(dialog, "getTypeId"), action)

                def step(self, coords):
                    driver.step(coords)
                    self.movement_steps += 1
                    return driver.coords()

                def walkCoords(self, coords):
                    driver.navigateCoords(coords)

                def walkTo(self, name, *, allow_removed=False):
                    if getattr(self, "recover_before_map_turn", None):
                        # Alpha recovery must occur after adjacent native combat and
                        # before the next map turn lets the Brood take its action.
                        from tests.narrative_walkthrough import authoredRegion

                        self.walkable = authoredRegion("nouraajd")[1]
                        return self.walkRoute(name, allow_removed=allow_removed)
                    if allow_removed and driver.object(name, required=False) is None:
                        return
                    driver.navigateTo(name)

            self._hunt_adapter = Adapter(methodName="runTest")
            self._hunt_adapter.movement_steps = 0
            self._hunt_adapter.hunt_actors, self._hunt_adapter.confirmed_dead = {}, set()
            self._hunt_adapter.capture_before_move = None
            self._hunt_adapter.phase_observations = []
            self._hunt_adapter.manual_phase_observations = []
            self._hunt_adapter.native_log_path = self.build_dir / "branch-native-disabled.log"
            self._hunt_adapter.harness, self._hunt_adapter.session = self.harness, self.session
            self._hunt_adapter.process = self.session["proc"]
            self._hunt_adapter.resetMcpProfile(self.class_id)
        adapter = self._hunt_adapter
        adapter.game, adapter.game_map, adapter.player = self.game, self.game_map, self.player
        adapter.build_dir = self.build_dir
        allowed = {
            "collectAuthoredRetreatScroll",
            "prepareThroughRolf",
            "prepareThroughCatacombs",
            "prepareHealingStockAtAuthoredMarket",
            "recoverOnAuthoredRoad",
            "recoverOnRoadPair",
            "enterHunt",
            "defeat",
            "retreatWithOwnedAuthoredScroll",
            "recoverBeforeRemainingBrood",
            "finishOriginalMainQuest",
            "trackLivingHuntActors",
        }
        self.test.assertIn(method, allowed)
        return getattr(adapter, method)(*args)

    def prepareNouraajd(self):
        self.hunt("prepareThroughRolf")
        self.hunt("prepareThroughCatacombs")
        self.hunt("prepareHealingStockAtAuthoredMarket")

    def finish(self):
        self.assertSurvival()
        if self.trace_path is not None and self._combat_trace_seq == 0:
            self._combat_failure = ("No observed native trace records", str(self.trace_path))
            self.test.fail(self._combat_failure)
        verifyJournals(self)
        self.test.assertEqual(set(self.case.branches), set(self.branches), "Unvisited authored branches")

    def receipt(self):
        return {
            "case": self.case.id,
            "class": self.class_id,
            "race": self.race_id,
            "seed": self.seed,
            "branches": self.branches,
            "steps": self.steps,
            "turns": self.turns,
            "combats": self.combats,
            "actions": list(self.actions),
            "initialReputation": self.case.initial_reputation,
            "journals": getattr(self, "_journal_observations", []),
        }

    def cleanup(self):
        for path in self._save_paths:
            path.unlink(missing_ok=True)
