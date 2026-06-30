#!/usr/bin/env python3

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
import base64
import binascii
import json
import struct
import zlib
from pathlib import Path

# Per-action iteration limits.
#
# These bound every attacker-controlled iteration count that feeds a loop in a
# simulation step, so a single step with an extreme value (e.g. turns=10**9)
# cannot spin the engine before any step cap applies. They are deliberately
# generous enough for legitimate walkthroughs while staying well below anything
# that would burn CPU. Each entry maps an action field name to (minimum,
# maximum) inclusive bounds; a minimum of 0 permits a no-op count.
MAX_STEP_TURNS = 1000
MAX_STEP_PUMP_TIMES = 1000
MAX_STEP_PUMP_ITERATIONS = 5000
MAX_STEP_MOVE_TURNS = 1000

# Cumulative iteration budget across an entire ``runSteps`` invocation. Even if
# every individual field is within its per-field limit, the sum of the declared
# worst-case iteration counts across all steps may not exceed this budget. This
# prevents a long sequence of in-bounds steps (or nested/repeated actions) from
# multiplying into an unbounded amount of work.
MAX_SIMULATION_ITERATION_BUDGET = 20000

# Map each simulation action to the iteration fields it consumes, the default
# used when the field is absent, and the per-field ceiling. ``min_value`` is the
# smallest accepted value (0 means a no-op count is allowed).
_ACTION_ITERATION_FIELDS = {
    "advance_turns": [("turns", 1, 0, MAX_STEP_TURNS)],
    "pump_events": [
        ("times", 1, 0, MAX_STEP_PUMP_TIMES),
        ("max_iterations", 100, 0, MAX_STEP_PUMP_ITERATIONS),
    ],
    "move_to_coords": [("max_turns", 24, 0, MAX_STEP_MOVE_TURNS)],
    "move_to_object": [("max_turns", 24, 0, MAX_STEP_MOVE_TURNS)],
    "interact_object": [("max_turns", 24, 0, MAX_STEP_MOVE_TURNS)],
}


class SimulationError(RuntimeError):
    def __init__(self, step, message, state=None):
        self.step = step
        self.message = message
        self.state = state or {}
        rendered_state = json.dumps(self.state, sort_keys=True, default=str)
        super().__init__(f"{step}: {message}; current_state={rendered_state}")

    def asDict(self):
        return {
            "step": self.step,
            "error": self.message,
            "state": self.state,
        }


def _validateIterationField(index, action, field, value, default, min_value, max_value):
    """Validate one attacker-controlled iteration count.

    Returns the bounded integer value (the value, or ``default`` when absent).
    Raises :class:`SimulationError` for non-integer, out-of-range, or negative
    inputs, identifying the offending step index and field. Booleans are
    rejected explicitly because ``bool`` is an ``int`` subclass and would
    otherwise silently pass as 0/1.
    """
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise SimulationError(
            f"{index}:{action}",
            f"`{field}` must be an integer, got {type(value).__name__}.",
        )
    if value < min_value:
        raise SimulationError(
            f"{index}:{action}",
            f"`{field}` must be >= {min_value}, got {value}.",
        )
    if value > max_value:
        raise SimulationError(
            f"{index}:{action}",
            f"`{field}` exceeds the per-action limit of {max_value}, got {value}.",
        )
    return value


def validateSteps(steps):
    """Validate every per-action iteration count before any loop executes.

    Bounds each attacker-controlled count against its per-field limit and
    enforces a cumulative iteration budget across the whole sequence so that a
    long run of in-bounds steps cannot multiply into unbounded work. Raises
    :class:`SimulationError` identifying the offending step index and field.
    Steps are validated in declaration order; because every step is validated
    exactly once here, nested or repeated actions cannot bypass or multiply the
    budget.
    """
    total_budget = 0
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            # Defer non-dict handling to runStep, which raises a precise error.
            continue
        action = step.get("action")
        fields = _ACTION_ITERATION_FIELDS.get(action)
        if not fields:
            continue
        for field, default, min_value, max_value in fields:
            bounded = _validateIterationField(index, action, field, step.get(field), default, min_value, max_value)
            total_budget += bounded
            if total_budget > MAX_SIMULATION_ITERATION_BUDGET:
                raise SimulationError(
                    f"{index}:{action}",
                    (
                        "cumulative iteration budget of "
                        f"{MAX_SIMULATION_ITERATION_BUDGET} exhausted at field `{field}`."
                    ),
                )
    return True


def runSimulation(game_module, map_name, player_class="Warrior", load_gui=False, steps=None):
    steps = steps or []
    validateSteps(steps)
    simulation = GameSimulation.startGame(
        game_module,
        map_name,
        player_class=player_class,
        load_gui=load_gui,
    )
    return simulation.runSteps(steps)


class GameSimulation:
    def __init__(self, game_module, game_instance, map_name, player_class):
        self.gameModule = game_module
        self.gameInstance = game_instance
        self.mapName = map_name
        self.playerClass = player_class
        self.gameMap = None
        self.player = None
        self.refreshHandles()

    @classmethod
    def startGame(cls, game_module, map_name, player_class="Warrior", load_gui=False):
        game_instance = game_module.CGameLoader.loadGame()
        if load_gui:
            game_module.CGameLoader.loadGui(game_instance)
        game_module.CGameLoader.startGameWithPlayer(game_instance, map_name, player_class)
        simulation = cls(game_module, game_instance, map_name, player_class)
        simulation.pumpEvents(5 if load_gui else 1)
        return simulation

    def refreshHandles(self):
        self.gameMap = self.gameInstance.getMap()
        self.player = self.gameMap.getPlayer()
        return self

    def fail(self, step, message):
        raise SimulationError(step, message, self.safeState())

    def safeState(self):
        try:
            return self.readMapState(include_objects=True, max_objects=20)
        except Exception as exc:
            return {"state_error": str(exc), "map": self.mapName, "playerClass": self.playerClass}

    def pumpEvents(self, times=1, drain=False, max_iterations=100):
        loop = self.gameModule.event_loop.instance()
        # Clamp defensively: validateSteps rejects out-of-range counts before the
        # step loop runs, but direct callers may still pass raw values here.
        minimum_iterations = min(max(int(times), 0), MAX_STEP_PUMP_TIMES)
        max_iterations = min(max(int(max_iterations), minimum_iterations), MAX_STEP_PUMP_ITERATIONS)
        iterations = 0
        for _ in range(minimum_iterations):
            loop.run()
            iterations += 1
        while drain and iterations < max_iterations and loop.run():
            iterations += 1
        self.refreshHandles()
        return {"pumped": iterations, "drain": bool(drain), "turn": self.gameMap.getTurn()}

    def advanceTurns(self, turns):
        turns = min(max(int(turns), 0), MAX_STEP_TURNS)
        for _ in range(turns):
            self.gameMap.move()
            self.pumpEvents(1)
        return {"turns": turns, "turn": self.gameMap.getTurn(), "player": self.playerSummary()}

    def objectByName(self, object_name):
        obj = self.gameMap.getObjectByName(object_name)
        if obj is None:
            self.fail("objectByName", f"Could not find object `{object_name}`.")
        return obj

    def objectsByType(self, type_name):
        return [
            obj
            for obj in self.gameMap.getObjects()
            if self._safeCall(obj, "getTypeId") == type_name or self._safeCall(obj, "getType") == type_name
        ]

    def moveToCoords(self, x, y, z=0, max_turns=24, mode="path"):
        # Clamp defensively: validateSteps bounds max_turns before the step loop
        # runs, but direct callers may still pass raw values here.
        max_turns = min(max(int(max_turns), 0), MAX_STEP_MOVE_TURNS)
        coords = self.gameModule.Coords(int(x), int(y), int(z))
        start = self.coordsDict(self.player.getCoords())
        if mode == "direct":
            self.player.setCoords(coords)
            self.pumpEvents(1)
            return {
                "mode": mode,
                "from": start,
                "to": self.coordsDict(self.player.getCoords()),
                "turn": self.gameMap.getTurn(),
            }
        if mode != "path":
            self.fail("moveToCoords", f"Unknown movement mode `{mode}`.")

        controller = self.player.getController()
        if not hasattr(controller, "setTarget"):
            self.fail("moveToCoords", f"Player controller cannot set a deterministic target: {type(controller)!r}.")
        controller.setTarget(self.player, coords)

        target = self.coordsDict(coords)
        for turn_index in range(max(int(max_turns), 0) + 1):
            if self.coordsDict(self.player.getCoords()) == target:
                return {
                    "mode": mode,
                    "from": start,
                    "to": target,
                    "turns": turn_index,
                    "turn": self.gameMap.getTurn(),
                }
            if turn_index == max(int(max_turns), 0):
                break
            self.gameMap.move()
            self.pumpEvents(1)

        self.fail(
            "moveToCoords",
            f"Player did not reach {target} from {start} within {max_turns} bounded turns.",
        )

    def moveToObject(self, object_name, max_turns=24, mode="path"):
        obj = self.objectByName(object_name)
        coords = obj.getCoords()
        result = self.moveToCoords(coords.x, coords.y, coords.z, max_turns=max_turns, mode=mode)
        result["object"] = self.objectSummary(obj)
        return result

    def interactWithObject(self, object_name, mode="remove", approach=True, move_mode="direct", max_turns=24):
        obj = self.objectByName(object_name)
        before = self.objectSummary(obj)
        approach_result = None
        if mode in {"remove", "destroy"}:
            if approach:
                coords = obj.getCoords()
                approach_coords = self._interactionCoords(coords)
                if move_mode == "direct":
                    start = self.coordsDict(self.player.getCoords())
                    self.player.setCoords(approach_coords)
                    approach_result = {
                        "mode": move_mode,
                        "from": start,
                        "to": self.coordsDict(self.player.getCoords()),
                        "target": self.coordsDict(coords),
                        "distance": self._distance(self.player.getCoords(), coords),
                    }
                else:
                    approach_result = self.moveToCoords(
                        approach_coords.x,
                        approach_coords.y,
                        approach_coords.z,
                        max_turns=max_turns,
                        mode=move_mode,
                    )
                    approach_result["target"] = self.coordsDict(coords)
                    approach_result["distance"] = self._distance(self.player.getCoords(), coords)
            runtime_name = self._safeCall(obj, "getName") or object_name
            self.gameMap.removeObjectByName(runtime_name)
        elif mode == "enter":
            coords = obj.getCoords()
            approach_result = self.moveToCoords(coords.x, coords.y, coords.z, max_turns=max_turns, mode=move_mode)
        else:
            self.fail("interactWithObject", f"Unknown interaction mode `{mode}`.")
        self.pumpEvents(3)
        return {
            "mode": mode,
            "approach": approach_result,
            "object": before,
            "state": self.readMapState(include_objects=False),
        }

    def openPanel(self, panel_name):
        panel = self.gameInstance.getGuiHandler().openPanel(panel_name)
        self.pumpEvents(3)
        return {
            "panel": self.objectSummary(panel),
            "guiClasses": sorted(self.guiClasses()),
        }

    def readQuestLog(self):
        return {
            "active": [self.questSummary(quest) for quest in self._safeCollection(self.player.getQuests)],
            "completed": [self.questSummary(quest) for quest in self._safeCollection(self.player.getCompletedQuests)],
        }

    def readInventory(self):
        items = [self.itemSummary(item) for item in self._safeCollection(self.player.getItems)]
        items.sort(key=lambda item: (item.get("typeId") or "", item.get("name") or ""))
        return items

    def hasInventoryItem(self, item_name):
        for item in self.readInventory():
            if item.get("name") == item_name or item.get("typeId") == item_name:
                return True
        return False

    def readMapState(
        self,
        include_objects=True,
        max_objects=80,
        bool_flags=None,
        string_properties=None,
        numeric_properties=None,
    ):
        self.refreshHandles()
        state = {
            "map": self._mapName(),
            "playerClass": self.playerClass,
            "turn": self.gameMap.getTurn(),
            "player": self.playerSummary(),
        }
        if include_objects:
            objects = [self.objectSummary(obj) for obj in self.gameMap.getObjects()]
            objects.sort(key=lambda item: (item.get("name") or "", item.get("typeId") or "", str(item.get("coords"))))
            state["objects"] = objects[: max(int(max_objects), 0)]
            state["objectCount"] = len(objects)
        if bool_flags:
            state["boolFlags"] = {name: self.gameMap.getBoolProperty(name) for name in bool_flags}
        if string_properties:
            state["stringProperties"] = {name: self.gameMap.getStringProperty(name) for name in string_properties}
        if numeric_properties:
            state["numericProperties"] = {name: self.gameMap.getNumericProperty(name) for name in numeric_properties}
        return state

    def readGuiTree(self):
        gui = self.gameInstance.getGui()
        if gui is None:
            self.fail("readGuiTree", "Game has no GUI. Start with load_gui=True before reading GUI state.")
        return json.loads(self.gameModule.jsonify(gui))

    def guiClasses(self):
        tree = self.readGuiTree()
        classes = set()

        def visit(node):
            if not isinstance(node, dict):
                return
            class_name = node.get("class")
            if class_name:
                classes.add(class_name)
            for child in node.get("properties", {}).get("children") or []:
                visit(child)

        visit(tree)
        return classes

    def guiContainsClass(self, class_name):
        return class_name in self.guiClasses()

    def captureGuiScreenshot(self, path=None, capture_func=None, include_base64=False):
        gui = self.gameInstance.getGui()
        if gui is None:
            self.fail("captureGuiScreenshot", "Game has no GUI. Start with load_gui=True before capturing screenshots.")

        path = Path(path) if path else None
        png_data = None
        width = None
        height = None
        if capture_func is None:
            read_pixels = getattr(gui, "read_pixels", None) or getattr(gui, "readPixels", None)
            if read_pixels is None:
                self.fail("captureGuiScreenshot", "GUI does not expose pixel readback and no callback was provided.")
            pixels, width, height = read_pixels()
            png_data = self._encodePng(bytes(pixels), int(width), int(height))
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png_data)
        else:
            if path is None:
                self.fail("captureGuiScreenshot", "A screenshot path is required when using a capture callback.")
            path.parent.mkdir(parents=True, exist_ok=True)
            result = capture_func(path, gui)
            if isinstance(result, (list, tuple)) and len(result) >= 3 and isinstance(result[1], int):
                width = int(result[1])
                height = int(result[2])

        if path is not None:
            if not path.exists() or path.stat().st_size <= 0:
                self.fail("captureGuiScreenshot", f"Screenshot capture did not write a non-empty file: {path}.")
            info = {
                "path": str(path),
                "suffix": path.suffix,
                "bytes": path.stat().st_size,
            }
            if path.suffix.lower() == ".png":
                width, height = self._pngDimensions(path.read_bytes())
        else:
            info = {"suffix": ".png", "bytes": len(png_data)}

        if width is not None and height is not None:
            info["width"] = width
            info["height"] = height
        if include_base64 or path is None:
            if png_data is None:
                png_data = path.read_bytes()
            info["pngBase64"] = base64.b64encode(png_data).decode("ascii")
        return info

    def runSteps(self, steps):
        validateSteps(steps)
        records = []
        for index, step in enumerate(steps, start=1):
            records.append(self.runStep(step, index))
        return {
            "map": self._mapName(),
            "playerClass": self.playerClass,
            "steps": records,
            "state": self.readMapState(include_objects=True, max_objects=40),
            "questLog": self.readQuestLog(),
            "inventory": self.readInventory(),
        }

    def runStep(self, step, index):
        if not isinstance(step, dict):
            raise SimulationError(f"{index}:invalid", "Simulation steps must be objects.", self.safeState())
        action = step.get("action")
        label = step.get("name") or f"{index}:{action}"
        try:
            result = self._runStepAction(step, action)
            return {"step": label, "action": action, "result": result}
        except SimulationError as exc:
            raise SimulationError(label, exc.message, exc.state) from exc
        except Exception as exc:
            raise SimulationError(label, str(exc), self.safeState()) from exc

    def _runStepAction(self, step, action):
        if action == "move_to_coords":
            coords = step.get("coords")
            if isinstance(coords, dict):
                x, y, z = coords.get("x"), coords.get("y"), coords.get("z", 0)
            elif isinstance(coords, (list, tuple)) and len(coords) in {2, 3}:
                x, y = coords[0], coords[1]
                z = coords[2] if len(coords) == 3 else 0
            else:
                x, y, z = step.get("x"), step.get("y"), step.get("z", 0)
            return self.moveToCoords(
                x,
                y,
                z,
                max_turns=step.get("max_turns", 24),
                mode=step.get("mode", "path"),
            )
        if action == "move_to_object":
            return self.moveToObject(
                step.get("object"),
                max_turns=step.get("max_turns", 24),
                mode=step.get("mode", "path"),
            )
        if action == "interact_object":
            return self.interactWithObject(
                step.get("object"),
                mode=step.get("mode", "remove"),
                approach=step.get("approach", True),
                move_mode=step.get("move_mode", "direct"),
                max_turns=step.get("max_turns", 24),
            )
        if action == "advance_turns":
            return self.advanceTurns(step.get("turns", 1))
        if action == "pump_events":
            return self.pumpEvents(
                step.get("times", 1),
                drain=step.get("drain", False),
                max_iterations=step.get("max_iterations", 100),
            )
        if action == "open_panel":
            return self.openPanel(step.get("panel"))
        if action == "read_quest_log":
            return self.readQuestLog()
        if action == "read_inventory":
            return self.readInventory()
        if action == "read_map_state":
            return self.readMapState(
                include_objects=step.get("include_objects", True),
                max_objects=step.get("max_objects", 80),
                bool_flags=step.get("bool_flags"),
                string_properties=step.get("string_properties"),
                numeric_properties=step.get("numeric_properties"),
            )
        if action == "read_gui_tree":
            return self.readGuiTree()
        if action == "capture_gui_screenshot":
            return self.captureGuiScreenshot(
                step.get("path"),
                include_base64=step.get("include_base64", False),
            )
        if action == "assert_map_bool":
            name = step.get("property") or step.get("name")
            expected = step.get("value", True)
            actual = self.gameMap.getBoolProperty(name)
            if actual != expected:
                self.fail("assert_map_bool", f"Expected map bool `{name}` to be {expected}, got {actual}.")
            return {"property": name, "value": actual}
        if action == "assert_inventory_contains":
            item = step.get("item")
            if not self.hasInventoryItem(item):
                self.fail("assert_inventory_contains", f"Inventory does not contain `{item}`.")
            return {"item": item, "present": True}
        if action == "assert_gui_contains_class":
            class_name = step.get("class")
            if not self.guiContainsClass(class_name):
                self.fail("assert_gui_contains_class", f"GUI tree does not contain `{class_name}`.")
            return {"class": class_name, "present": True}
        self.fail("runStep", f"Unknown simulation action `{action}`.")

    def playerSummary(self):
        summary = self.objectSummary(self.player)
        summary["gold"] = self._safeCall(self.player, "getGold")
        summary["level"] = self._safeCall(self.player, "getLevel")
        summary["hpRatio"] = self._safeCall(self.player, "getHpRatio")
        return summary

    def objectSummary(self, obj):
        if obj is None:
            return None
        coords = self._safeCall(obj, "getCoords")
        return {
            "class": obj.__class__.__name__,
            "name": self._safeCall(obj, "getName"),
            "type": self._safeCall(obj, "getType"),
            "typeId": self._safeCall(obj, "getTypeId"),
            "label": self._safeCall(obj, "getLabel"),
            "coords": self.coordsDict(coords) if coords is not None else None,
        }

    def itemSummary(self, item):
        return {
            "name": self._safeCall(item, "getName"),
            "typeId": self._safeCall(item, "getTypeId"),
            "label": self._safeCall(item, "getLabel"),
            "description": self._safeCall(item, "getDescription"),
        }

    def questSummary(self, quest):
        return {
            "name": self._safeCall(quest, "getName"),
            "typeId": self._safeCall(quest, "getTypeId"),
            "objective": self._safeCall(quest, "getObjective"),
            "reward": self._safeCall(quest, "getReward"),
            "hint": self._safeCall(quest, "getHint"),
        }

    @staticmethod
    def coordsDict(coords):
        return {"x": coords.x, "y": coords.y, "z": coords.z}

    def _interactionCoords(self, coords):
        candidates = (
            (0, 1, 0),
            (1, 0, 0),
            (-1, 0, 0),
            (0, -1, 0),
            (0, 0, 0),
        )
        for dx, dy, dz in candidates:
            candidate = self.gameModule.Coords(coords.x + dx, coords.y + dy, coords.z + dz)
            if self._safeCall(self.gameMap, "canStep", candidate):
                return candidate
        return coords

    @staticmethod
    def _distance(left, right):
        return abs(left.x - right.x) + abs(left.y - right.y) + abs(left.z - right.z)

    @staticmethod
    def _encodePng(rgba_data, width, height):
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid screenshot dimensions: {width}x{height}.")
        pitch = width * 4
        if len(rgba_data) != pitch * height:
            raise ValueError(
                f"Screenshot pixel buffer has {len(rgba_data)} bytes, expected {pitch * height} for {width}x{height}."
            )

        def chunk(name, data):
            name = name.encode("ascii")
            crc = binascii.crc32(name + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)

        rows = b"".join(b"\x00" + rgba_data[row * pitch : (row + 1) * pitch] for row in range(height))
        header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk("IHDR", header) + chunk("IDAT", zlib.compress(rows)) + chunk("IEND", b"")

    @staticmethod
    def _pngDimensions(data):
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Screenshot file is not a PNG.")
        if len(data) < 33 or data[12:16] != b"IHDR":
            raise ValueError("Screenshot PNG is missing an IHDR chunk.")
        if struct.unpack(">I", data[8:12])[0] != 13:
            raise ValueError("Screenshot PNG has an invalid IHDR chunk.")
        width, height = struct.unpack(">II", data[16:24])
        if width <= 0 or height <= 0:
            raise ValueError(f"Screenshot PNG has invalid dimensions: {width}x{height}.")
        return width, height

    def _mapName(self):
        name = getattr(self.gameMap, "mapName", None)
        return name or self._safeCall(self.gameMap, "getName") or self.mapName

    @staticmethod
    def _safeCollection(fn):
        try:
            return list(fn())
        except Exception:
            return []

    @staticmethod
    def _safeCall(obj, method_name, *args):
        if obj is None:
            return None
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        try:
            return method(*args)
        except Exception:
            return None
