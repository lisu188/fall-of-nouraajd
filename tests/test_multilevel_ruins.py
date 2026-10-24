# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored fifteen-floor routes, real controller traversal and summit persistence."""

from collections import deque
import json
from pathlib import Path
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
LEVEL_COUNT = 15


def goalName(level):
    return ("multilevelLowerGoal", "multilevelUpperGoal")[level] if level < 2 else f"multilevelGoalLevel{level}"


def upName(level):
    return "stairsUp" if level == 0 else f"stairsUpLevel{level}"


def downName(level):
    return "stairsDown" if level == 1 else f"stairsDownLevel{level}"


def authoredRuins():
    directory = ROOT / "res" / "maps" / "multilevel"
    document = json.loads((directory / "map.json").read_text(encoding="utf-8"))
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    objects = {}
    floors = {}
    object_layers = {}
    for layer in document["layers"]:
        level = int(layer.get("properties", {}).get("level", 0))
        if layer["type"] == "tilelayer":
            floors[level] = layer
        elif layer["type"] == "objectgroup":
            object_layers[level] = layer
            for obj in layer["objects"]:
                coords = (int(obj["x"] / document["tilewidth"]), int(obj["y"] / document["tileheight"]), level)
                if obj["name"] in objects:
                    raise AssertionError(f"Duplicate authored object: {obj['name']}")
                objects[obj["name"]] = (obj, coords)
    return document, config, floors, object_layers, objects


def authoredWalkableCells(document, config, floors, objects):
    tile_types = json.loads((ROOT / "res" / "config" / "tiles.json").read_text(encoding="utf-8"))
    misc_types = json.loads((ROOT / "res" / "config" / "misc.json").read_text(encoding="utf-8"))
    tile_set = document["tilesets"][0]
    walkable = {}
    for level, floor in floors.items():
        cells = set()
        for index, gid in enumerate(floor["data"]):
            tile_type = floor["properties"]["default"]
            if gid:
                tile_type = tile_set["tileproperties"][str(gid - tile_set["firstgid"])]["type"]
            if tile_types[tile_type]["properties"]["canStep"]:
                cells.add((index % floor["width"], index // floor["width"], level))
        walkable[level] = cells
    for obj, coords in objects.values():
        definition = config[obj["type"]]
        if "ref" in definition:
            definition = misc_types[definition["ref"]]
        if not definition.get("properties", {}).get("canStep", True):
            walkable[coords[2]].discard(coords)
    return walkable


class MultilevelRuinsContentTest(unittest.TestCase):
    def testAllFifteenFloorsHaveGoalsAndReciprocalWalkableStairs(self):
        document, config, floors, object_layers, objects = authoredRuins()
        self.assertEqual(set(range(LEVEL_COUNT)), set(floors))
        self.assertEqual(set(range(LEVEL_COUNT)), set(object_layers))
        stairs = {}
        walkable = authoredWalkableCells(document, config, floors, objects)
        for level, floor in floors.items():
            self.assertEqual(document["width"] * document["height"], len(floor["data"]))
        for name, (obj, coords) in objects.items():
            definition = config[obj["type"]]
            if definition.get("class") == "LevelStairs":
                properties = definition["properties"]
                stairs[name] = (coords, tuple(properties[f"target{axis}"] for axis in "XYZ"))
        self.assertEqual(2 * (LEVEL_COUNT - 1), len(stairs))
        for level in range(LEVEL_COUNT):
            with self.subTest(level=level):
                goal, coords = objects[goalName(level)]
                self.assertEqual("MultilevelGoal", config[goal["type"]]["class"])
                self.assertEqual(level, coords[2])
                self.assertIn(coords, walkable[level])
                if level < LEVEL_COUNT - 1:
                    source, target = stairs[upName(level)]
                    reverse_source, reverse_target = stairs[downName(level + 1)]
                    self.assertEqual(level, source[2])
                    self.assertEqual(level + 1, target[2])
                    self.assertEqual(source, reverse_target)
                    self.assertEqual(target, reverse_source)
                    self.assertIn(source, walkable[level])
                    self.assertIn(target, walkable[level + 1])
        self.assertEqual((4, 1, 0), objects["stairsUp"][1])
        self.assertEqual((4, 1, 1), objects["stairsDown"][1])
        self.assertEqual((6, 5, 0), objects[goalName(0)][1])
        self.assertEqual((6, 4, 1), objects[goalName(1)][1])

    def testEveryLandingGoalAndStairHasARouteWithoutAccidentalTransitions(self):
        document, config, floors, _object_layers, objects = authoredRuins()
        walkable = authoredWalkableCells(document, config, floors, objects)
        stair_coords = {coords for obj, coords in objects.values() if config[obj["type"]].get("class") == "LevelStairs"}

        def reachable(start, target):
            floor = floors[start[2]]
            blocked = stair_coords - {start, target}
            queue = deque([start])
            seen = {start}
            while queue:
                point = queue.popleft()
                if point == target:
                    return True
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y, level = point[0] + dx, point[1] + dy, point[2]
                    neighbor = (x, y, level)
                    if not (0 <= x < floor["width"] and 0 <= y < floor["height"]):
                        continue
                    if neighbor in seen or neighbor in blocked:
                        continue
                    if neighbor not in walkable[level]:
                        continue
                    seen.add(neighbor)
                    queue.append(neighbor)
            return False

        for level in range(LEVEL_COUNT):
            with self.subTest(level=level):
                landing = objects[downName(level) if level else upName(0)][1]
                goal = objects[goalName(level)][1]
                self.assertTrue(reachable(landing, goal), (landing, goal))
                if level < LEVEL_COUNT - 1:
                    self.assertTrue(reachable(goal, objects[upName(level)][1]), level)
                if level:
                    self.assertTrue(reachable(goal, objects[downName(level)][1]), level)
        entry = tuple(int(document["properties"][axis]) for axis in "xyz")
        self.assertTrue(reachable(entry, objects[upName(0)][1]))


def exerciseNativeRuins(game, loop):
    """Keep the long route in an isolated native process, with one tiny disposable save."""
    sessions = []
    save_paths = []

    def loadSession():
        current = game.CGameLoader.loadGame()
        sessions.append(current)
        return current

    def coords(obj):
        point = obj.getCoords()
        return point.x, point.y, point.z

    try:
        current = loadSession()
        game.CGameLoader.startGameWithPlayer(current, "multilevel", "Warrior")
        world = current.getMap()
        player = world.getPlayer()
        assert current.getGui() is None
        start_turn = world.getTurn()

        def walk(name, destination_level=None):
            target = world.getObjectByName(name)
            assert target is not None, name
            destination = coords(target)
            player.getController().setTarget(player, target.getCoords())
            trail = []
            for _ in range(32):
                position = coords(player)
                trail.append(position)
                reached = position[2] == destination_level if destination_level is not None else position == destination
                if reached:
                    return position
                world.move()
                loop.run()
                loop.run()
            raise AssertionError(
                (name, destination, coords(player), trail, world.getNumericProperty("levelTransitionCount"))
            )

        for level in range(1, LEVEL_COUNT):
            walk(upName(level - 1), level)
            assert world.getNumericProperty("levelTransitionCount") == level
            walk(goalName(level))
            assert world.getBoolProperty(f"visited_level_{level}_goal"), level
            assert not world.getBoolProperty("visited_lower_goal"), "Deep goals must not mark the floor-zero goal"
        assert world.getBoolProperty("visited_upper_goal")
        saved_coords = coords(player)
        saved_turn = world.getTurn()
        slot = "unit-multilevel-summit-" + uuid.uuid4().hex
        game.CMapLoader.save(world, slot)
        save_path = Path(current.getResourcesProvider().getPath("save/" + slot + ".json"))
        save_paths.extend((save_path, Path(str(save_path) + ".bak")))
        assert save_path.is_file()
        loaded = loadSession()
        game.CGameLoader.loadSavedGame(loaded, slot)
        world = loaded.getMap()
        player = world.getPlayer()
        assert coords(player) == saved_coords and saved_coords[2] == LEVEL_COUNT - 1
        assert world.getTurn() == saved_turn
        assert world.getNumericProperty("levelTransitionCount") == LEVEL_COUNT - 1
        for level in range(1, LEVEL_COUNT):
            assert world.getBoolProperty(f"visited_level_{level}_goal"), level
        for level in range(LEVEL_COUNT - 1, 0, -1):
            walk(goalName(level))
            walk(downName(level), level - 1)
            assert world.getNumericProperty("levelTransitionCount") == 2 * (LEVEL_COUNT - 1) - level + 1
        walk(goalName(0))
        assert coords(player)[2] == 0
        assert world.getBoolProperty("visited_lower_goal")
        assert world.getBoolProperty("used_stairs_down") and world.getBoolProperty("used_stairs_up")
        for level in range(LEVEL_COUNT):
            assert world.getBoolProperty(f"visited_level_{level}_goal"), level
        assert world.getTurn() > start_turn
        print(json.dumps({"levels": LEVEL_COUNT, "transitions": 28, "summit": saved_coords, "final": coords(player)}))
    finally:
        for current in reversed(sessions):
            current.getContext().shutdown()
        for path in save_paths:
            path.unlink(missing_ok=True)


class MultilevelRuinsRuntimeTest(unittest.TestCase):
    def testRealControllerClimbsAllFloorsAndReloadsSummitBeforeFullDescent(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild(
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "from tests.test_multilevel_ruins import exerciseNativeRuins\n"
            "exerciseNativeRuins(game, loop)\n",
            timeout_seconds=90,
        )
        self.assertIn('"levels": 15, "transitions": 28', output)


class MultilevelRuinsMcpTest(unittest.TestCase):
    def setUp(self):
        from tests.test_navigation_mcp import NavigationMcpWalkthroughTest

        self.driver = NavigationMcpWalkthroughTest(methodName="runTest")
        self.addCleanup(self.driver.doCleanups)
        self.driver.setUp()

    def testStdioControllerVisitsEveryGoalAndCompletesTwentyEightTransitions(self):
        driver = self.driver

        def walk(name, destination_level):
            driver.target(name)
            return driver.reach(lambda point: point[2] == destination_level, max_turns=32)

        def walkGoal(level):
            goal = driver.call(driver.world, "getObjectByName", goalName(level))
            properties = json.loads(driver.engine("jsonify", goal))["properties"]
            destination = [properties.get(key) for key in ("posx", "posy", "posz")]
            driver.target(goalName(level))
            return driver.reach(lambda point: point == destination, max_turns=32)

        initial_turn = driver.call(driver.world, "getTurn")
        for level in range(1, LEVEL_COUNT):
            walk(upName(level - 1), level)
            self.assertEqual(level, driver.call(driver.world, "getNumericProperty", "levelTransitionCount"))
            walkGoal(level)
            self.assertTrue(driver.call(driver.world, "getBoolProperty", f"visited_level_{level}_goal"))
        summit = driver.playerState()
        self.assertEqual(14, summit["coords"][2])
        for level in range(LEVEL_COUNT - 1, 0, -1):
            with self.subTest(descending_from=level):
                walkGoal(level)
                walk(downName(level), level - 1)
        walkGoal(0)
        final = driver.playerState()
        self.assertEqual(0, final["coords"][2])
        self.assertEqual(28, driver.call(driver.world, "getNumericProperty", "levelTransitionCount"))
        self.assertGreater(final["turn"], initial_turn)
        for level in range(LEVEL_COUNT):
            self.assertTrue(driver.call(driver.world, "getBoolProperty", f"visited_level_{level}_goal"))
        for flag in ("visited_lower_goal", "visited_upper_goal", "used_stairs_up", "used_stairs_down"):
            self.assertTrue(driver.call(driver.world, "getBoolProperty", flag), flag)


if __name__ == "__main__":
    unittest.main()
