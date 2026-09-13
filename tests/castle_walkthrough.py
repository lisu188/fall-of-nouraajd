# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared source-routed Castle campaign exercise for native and stdio MCP tests."""

import json
from collections import deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_NAMES = ("castleHomecoming", "castleGuardianAngels", "castleGriffinCliff")


class TransitRoutes(dict):
    def __init__(self):
        super().__init__()
        self.passages = {}


def authoredMap(map_name):
    directory = REPO_ROOT / "res" / "maps" / map_name
    document = json.loads((directory / "map.json").read_text(encoding="utf-8"))
    configs = {}
    for path in sorted((REPO_ROOT / "res" / "config").glob("*.json")):
        configs.update(json.loads(path.read_text(encoding="utf-8")))
    configs.update(json.loads((directory / "config.json").read_text(encoding="utf-8")))

    def definition(type_id):
        value = configs[type_id]
        base = definition(value["ref"]) if "ref" in value else {}
        return {**base, **value, "properties": {**base.get("properties", {}), **value.get("properties", {})}}

    objects = {}
    for layer in document["layers"]:
        if layer["type"] != "objectgroup":
            continue
        z = int(layer["properties"]["level"])
        for item in layer["objects"]:
            value = definition(item["type"])
            objects[item["name"]] = {
                **value,
                "properties": {**value.get("properties", {}), **item.get("properties", {})},
                "coords": (int(item["x"] // 32), int(item["y"] // 32), z),
            }
    tile_types = document["tilesets"][0]["tileproperties"]
    walkable = set()
    for layer in document["layers"]:
        if layer["type"] != "tilelayer":
            continue
        z = int(layer["properties"]["level"])
        for index, tile in enumerate(layer["data"]):
            type_id = tile_types.get(str(tile - 1), {}).get("type")
            if type_id and definition(type_id)["properties"].get("canStep", False):
                walkable.add((index % document["width"], index // document["width"], z))
    portals = TransitRoutes()
    for value in objects.values():
        props = value["properties"]
        if value.get("class") == "CastlePortal":
            target = tuple(int(props["campaign_target" + axis]) for axis in "XYZ")
            if props.get("campaign_portalKind") == "diagonalPassage":
                portals.passages.setdefault(value["coords"], set()).add(target)
            else:
                portals[value["coords"]] = target
        elif props.get("canStep") is False:
            walkable.discard(value["coords"])
    mission = json.loads(objects["castleMission"]["properties"]["campaign_mission"].removeprefix("castleMission:"))
    return document, objects, walkable, portals, mission


def shortestRoute(walkable, portals, start, target):
    """Return (adjacent movement command, resulting position) pairs, including portal traversal."""
    start, target = tuple(start), tuple(target)
    previous = {start: None}
    queue = deque([start])
    while queue and target not in previous:
        current = queue.popleft()
        steps = [(current[0] + dx, current[1] + dy, current[2]) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
        steps.extend(sorted(portals.passages.get(current, ())))
        for step in steps:
            if step not in walkable:
                continue
            arrival = portals.get(step, step)
            if arrival not in walkable or arrival in previous:
                continue
            previous[arrival] = (current, step)
            queue.append(arrival)
    if target not in previous:
        raise AssertionError(f"No authored walkable route from {start} to {target}")
    route = []
    cursor = target
    while previous[cursor] is not None:
        origin, step = previous[cursor]
        route.append((step, cursor))
        cursor = origin
    return list(reversed(route))


class CastleWalkthrough:
    def __init__(self, engine_call, handle_call, game_handle, map_handle, player_handle):
        self.engineCall = engine_call
        self.handleCall = handle_call
        self.game = game_handle
        self.gameMap = map_handle
        self.player = player_handle
        self.loop = self.engineCall("event_loop.instance", [])
        self.log = {"steps": 0, "combats": [], "portals": [], "allies": [], "chapters": []}

    def call(self, handle, method, args=None):
        return self.handleCall(handle, method, args or [])

    def pump(self):
        self.call(self.loop, "run")

    def playerData(self):
        return json.loads(self.engineCall("jsonify", [self.player]))["properties"]

    def coords(self):
        data = self.playerData()
        return tuple(data["pos" + axis] for axis in "xyz")

    def refresh(self):
        self.gameMap = self.call(self.game, "getMap")
        self.player = self.call(self.gameMap, "getPlayer")

    def object(self, name):
        return self.call(self.gameMap, "getObjectByName", [name])

    def questNames(self, key):
        return [
            quest.get("properties", {}).get("typeId") or quest.get("properties", {}).get("name")
            for quest in self.playerData().get(key) or []
        ]

    def walkTo(self, target):
        route = shortestRoute(self.walkable, self.portals, self.coords(), target)
        for step, arrival in route:
            guards = [name for name in self.guardsByCell.get(step, ()) if self.object(name)]
            self.call(self.player, "moveTo", list(step))
            self.pump()
            self.log["steps"] += 1
            if guards:
                for name in guards:
                    assert self.object(name) is None, f"Player failed to defeat {name} at {step}"
                    assert self.call(self.gameMap, "getBoolProperty", ["campaign_castleDefeated_" + name]), name
                    self.log["combats"].append(name)
                # Winning a fight restores the player to the previous square; re-enter the vacated square.
                self.call(self.player, "moveTo", list(step))
                self.pump()
            if self.call(self.gameMap, "getBoolProperty", ["campaign_castleFinished_" + self.mission["scenarioId"]]):
                return
            if step != arrival:
                self.log["portals"].append({"from": list(step), "to": list(arrival)})
        assert self.coords() == tuple(target), ("Route ended at the wrong position", self.coords(), target)

    def chapter(self, map_name, *, finish=True):
        self.refresh()
        # A headless player panel cancels fights; the existing AI chooses ordinary actions and carried potions.
        template = self.call(self.game, "createObject", [self.call(self.player, "getTypeId")])
        auto_combat = self.call(template, "getFightController")
        self.call(self.player, "setFightController", [auto_combat])
        document, self.objects, self.walkable, self.portals, self.mission = authoredMap(map_name)
        self.guardsByCell = {}
        for name in self.mission["defenderIds"]:
            self.guardsByCell.setdefault(self.objects[name]["coords"], []).append(name)
        start = tuple(int(document["properties"][axis]) for axis in "xyz")
        assert self.coords() == start, (map_name, self.coords(), start)
        floor = next(
            layer
            for layer in document["layers"]
            if layer["type"] == "tilelayer" and int(layer["properties"]["level"]) == start[2]
        )
        gid = floor["data"][start[1] * document["width"] + start[0]]
        expected_tile = document["tilesets"][0]["tileproperties"][str(gid - 1)]["type"]
        coords_handle = self.call(self.player, "getCoords")
        tile_handle = self.call(self.gameMap, "getTile", list(start))
        assert self.call(tile_handle, "getTypeId") == expected_tile, (map_name, "Native tile decode mismatch")
        assert self.call(self.gameMap, "canStep", [coords_handle]), (map_name, "Native landing tile is blocked")
        # Starting a map places the player without onEnter; an ordinary turn must initialize its quest.
        self.call(self.gameMap, "move")
        self.pump()
        quest_names = self.questNames("quests")
        assert self.mission["questId"] in quest_names, (map_name, quest_names)
        self.initialGold = self.call(self.player, "getGold")
        for name in ("castleCatherine", "castleChristian"):
            officer = self.objects[name]
            self.walkTo(officer["coords"])
            dialog = self.call(self.game, "createObject", [officer["properties"]["campaign_dialog"]])
            self.call(dialog, "invokeAction", ["reportProgress"])
            self.pump()
            self.log["allies"].append({"map": map_name, "name": name})
        if map_name == "castleGuardianAngels":
            angel_name = next(
                name
                for name, value in self.objects.items()
                if value.get("class") == "CastleSupply"
                and value["properties"].get("animation") == "images/castle/angel"
            )
            self.walkTo(self.objects[angel_name]["coords"])
            assert self.call(self.gameMap, "getBoolProperty", ["campaign_castleSupply_" + angel_name])
            self.log["allies"].append({"map": map_name, "name": angel_name, "supplied": True})
        for name, value in self.objects.items():
            if value.get("class") == "CastleSupply":
                try:
                    self.walkTo(value["coords"])
                    break
                except AssertionError as error:
                    if "No authored walkable route" not in str(error):
                        raise
        objectives = list(self.mission["objectiveIds"])
        if not finish:
            objectives = objectives[:1]
        # Commanders are separate victory requirements in Guardian Angels.
        for name in self.mission.get("enemyHeroIds", []):
            if self.object(name):
                self.walkTo(self.objects[name]["coords"])
        for name in objectives:
            marker = self.object(name)
            guards = self.objects[name]["properties"].get("campaign_guards", "").split(",")
            for guard in filter(None, guards):
                if self.object(guard):
                    self.walkTo(self.objects[guard]["coords"])
            if not self.call(self.gameMap, "getBoolProperty", ["campaign_castleCaptured_" + name]):
                self.walkTo(self.objects[name]["coords"])
                if not self.call(self.gameMap, "getBoolProperty", ["campaign_castleCaptured_" + name]):
                    assert self.call(marker, "capture", [self.player]), name
                    self.pump()
            assert self.call(self.gameMap, "getBoolProperty", ["campaign_castleCaptured_" + name]), name
        scenario_id = self.mission["scenarioId"]
        assert self.call(self.gameMap, "getBoolProperty", ["campaign_castleFinished_" + scenario_id]) == finish
        if finish:
            completed = self.questNames("completedQuests")
            assert self.mission["questId"] in completed, (map_name, completed)
        self.log["chapters"].append(
            {"map": map_name, "captured": objectives, "gold": self.call(self.player, "getGold"), "finished": finish}
        )
        return self.log


def nativeDriver(game_module, game_instance):
    def engineCall(name, args):
        target = game_module
        for part in name.split("."):
            target = getattr(target, part)
        return target(*args)

    return CastleWalkthrough(
        engineCall,
        lambda handle, method, args: getattr(handle, method)(*args),
        game_instance,
        game_instance.getMap(),
        game_instance.getMap().getPlayer(),
    )
