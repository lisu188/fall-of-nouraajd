# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual cave callbacks and route observers reject missing or fabricated evidence."""

import ast
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_routes_caves import (
    AMBIENT_CAVES,
    RITUAL_ANCHORS,
    afterAmbientCaveTurn,
    ambientCaveDefinition,
    beforeAmbientCaveTurn,
    captureAmbientCave,
    verifyInactiveRitualCaves,
)

Coords = namedtuple("Coords", "x y z")


def caveType(randint):
    path = Path(__file__).resolve().parents[1] / "res/plugins/object.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
    callback = next(node for node in loader.body if isinstance(node, ast.ClassDef) and node.name == "Cave")
    callback.decorator_list = []
    namespace = {"CBuilding": object, "randint": randint, "Coords": Coords}
    exec(compile(ast.Module(body=[callback], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["Cave"]


class GameplayCaveObservationTest(unittest.TestCase):
    def ritualDriver(self):
        cave_class = caveType(Mock(side_effect=AssertionError("Zero stock must not draw random spawn rolls")))
        path = Path(__file__).resolve().parents[1] / "res/maps/ritual/script.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
        callback = next(
            node for node in loader.body if isinstance(node, ast.ClassDef) and node.name == "RitualTurnTrigger"
        )
        callback.decorator_list = []
        namespace = {"CTrigger": object}
        exec(compile(ast.Module(body=[callback], type_ignores=[]), str(path), "exec"), namespace)
        state = {"turn": 0, "countdown": 14, "started": False, "active": False, "destroyed": 0}
        actors, registry, checks = {}, {}, []
        world = SimpleNamespace(getBoolProperty=lambda key: False, addObject=Mock())
        for name in RITUAL_ANCHORS:
            actor = cave_class()
            actor.getBoolProperty = lambda key: key == "enabled"
            actor.getNumericProperty = lambda key: 0
            actor.getObjectProperty = Mock()
            actor.getMap = lambda: world
            handle = {"__handle__": name}
            actors[name], registry[name] = handle, actor
        turn_anchor = SimpleNamespace(getMap=lambda: world)
        turn_trigger = namespace["RitualTurnTrigger"]()

        def call(handle, method, *args):
            if handle == driver.game_map:
                return state["turn"] if method == "getTurn" else list(actors.values())
            return getattr(registry[handle["__handle__"]], method)(*args)

        def tick():
            for actor in registry.values():
                actor.onTurn(None)
            turn_trigger.trigger(turn_anchor, None)
            state["turn"] += 1

        driver = SimpleNamespace(
            test=self,
            map_name="ritual",
            game_map={"__handle__": "ritual-map"},
            state=state,
            registry=registry,
            world=world,
            object=actors.__getitem__,
            flag=lambda key: state["started" if key == "ritual_started" else "active"],
            number=lambda key: state["countdown" if key == "ritual_countdown" else "destroyed"],
            call=call,
            tick=tick,
            checks=checks,
            check=lambda branch, condition, **evidence: checks.append((branch, condition, evidence)),
        )
        return driver

    def ambientDriver(self, *, rolls=()):
        definition = ambientCaveDefinition("vhulmarn")
        random_roll = Mock(side_effect=iter(rolls))
        cave = caveType(random_roll)()
        state = {"turn": 0, "monsters": definition["monsters"], "enabled": True}
        handles = {definition["name"]: {"__handle__": "cave"}}
        objects, events, checks = {"cave": cave}, [], []
        world = SimpleNamespace()
        template = SimpleNamespace(coords=Coords(0, 0, 0), getTypeId=lambda: "drownedHybrid")
        objects["template"] = template

        def clone():
            name = "ambient-clone-" + str(len(events))
            actor = SimpleNamespace(coords=template.coords, getTypeId=template.getTypeId, name=name)

            def move(x, y, z):
                origin = actor.coords
                actor.coords = Coords(x, y, z)
                events.append(
                    {
                        "event": "movement",
                        "committed": True,
                        "map": driver.map_name,
                        "object": {"name": name, "typeId": actor.getTypeId(), "isPlayer": False},
                        "from": dict(zip("xyz", origin)),
                        "to": dict(zip("xyz", actor.coords)),
                    }
                )

            actor.moveTo = move
            return actor

        def add(actor):
            handles[actor.name] = {"__handle__": actor.name}
            objects[actor.name] = actor

        template.clone = clone
        cave.getMap = lambda: world
        cave.getCoords = lambda: Coords(*definition["coords"])
        cave.getBoolProperty = lambda key: state["enabled"]
        cave.getNumericProperty = lambda key: state["monsters"] if key == "monsters" else definition["chance"]
        cave.getObjectProperty = lambda key: template
        cave.incProperty = lambda key, delta: state.__setitem__(key, state[key] + delta)
        world.addObject = add
        world.getObjects = lambda: list(handles.values())

        def call(handle, method, *args):
            if handle == driver.game_map:
                return state["turn"] if method == "getTurn" else world.getObjects()
            if handle == {"__handle__": "cave"} and method == "getObjectProperty":
                return {"__handle__": "template"}
            return getattr(objects[handle["__handle__"]], method)(*args)

        def coords(handle):
            actor = objects[handle["__handle__"]]
            return tuple(actor.getCoords() if actor is cave else actor.coords)

        def tick():
            beforeAmbientCaveTurn(driver)
            cave.onTurn(None)
            state["turn"] += 1
            afterAmbientCaveTurn(driver)

        driver = SimpleNamespace(
            test=self,
            map_name="vhulmarn",
            game_map={"__handle__": "map"},
            case=SimpleNamespace(branches=("vhulmarn.cave.timedSpawn", "vhulmarn.cave.exhausted")),
            state=state,
            events=events,
            handles=handles,
            objects=objects,
            cave=cave,
            random_roll=random_roll,
            coords=coords,
            object=lambda name, required=True: handles.get(name),
            call=call,
            tick=tick,
            checks=checks,
            check=lambda branch, condition, **evidence: checks.append((branch, condition, evidence)),
        )
        return driver

    def nativeTrace(self, driver):
        checkpoint = patch("tests.gameplay_routes_services.nativeCheckpoint", side_effect=lambda d: len(driver.events))
        records = patch(
            "tests.gameplay_routes_services.nativeEventsSince",
            side_effect=lambda d, offset, event: tuple(row for row in driver.events[offset:] if row["event"] == event),
        )
        return checkpoint, records

    def testAuthoredAmbientSourcesHaveFinitePositiveStockAndUnvisitedLateCoordinates(self):
        expected = {
            "nouraajd": ((57, 103, 0), 10, 10),
            "ninemarches": ((391, 214, 0), 4, 6),
            "vhulmarn": ((26, 20, 0), 6, 12),
            "kadath": ((48, 122, 0), 10, 12),
            "sunderedmarch": ((150, 100, 0), 8, 12),
        }
        self.assertEqual(set(expected), set(AMBIENT_CAVES))
        for map_name, values in expected.items():
            definition = ambientCaveDefinition(map_name)
            self.assertEqual(values, tuple(definition[key] for key in ("coords", "monsters", "chance")))

    def testActualCaveRandomMissThenSpawnThenTwoExhaustedTurns(self):
        driver = self.ambientDriver(rolls=[100, 1, 1, 1, 1, 1, 1])
        captureAmbientCave(driver)
        checkpoint, records = self.nativeTrace(driver)
        with checkpoint, records:
            driver.tick()
            self.assertEqual([], driver.checks)
            for _ in range(6):
                driver.tick()
            self.assertEqual(["vhulmarn.cave.timedSpawn"], [row[0] for row in driver.checks])
            driver.tick()
            self.assertEqual(1, len(driver.checks))
            driver.tick()
            self.assertEqual(["vhulmarn.cave.timedSpawn", "vhulmarn.cave.exhausted"], [row[0] for row in driver.checks])
            self.assertEqual([8, 9], driver.checks[-1][2]["actualTurns"])
            self.assertTrue(driver._ambient_cave["complete"])
            beforeAmbientCaveTurn(driver)
            afterAmbientCaveTurn(driver)
        self.assertEqual(7, driver.random_roll.call_count, "Zero stock must never draw another random roll")
        self.assertEqual(0, driver.state["monsters"])
        self.assertEqual(6, len(driver.events))
        self.assertNotEqual("cave", driver.checks[0][2]["spawnedIdentity"])

    def testAmbientDoesNothingWithoutBothDeclaredBranches(self):
        driver = self.ambientDriver()
        driver.case.branches = ("vhulmarn.cave.timedSpawn",)
        driver.call = Mock(side_effect=AssertionError("An undeclared observer must perform no RPCs"))
        captureAmbientCave(driver)
        beforeAmbientCaveTurn(driver)
        afterAmbientCaveTurn(driver)
        self.assertIsNone(driver._ambient_cave)

    def testAmbientCounterAloneCannotCreditMissingNativePlacementOrOldIdentity(self):
        for defect in ("missing-trace", "old-identity", "wrong-type", "double-decrement"):
            with self.subTest(defect=defect):
                driver = self.ambientDriver(rolls=[1])
                captureAmbientCave(driver)
                checkpoint, records = self.nativeTrace(driver)
                with checkpoint, records:
                    beforeAmbientCaveTurn(driver)
                    driver.cave.onTurn(None)
                    driver.state["turn"] += 1
                    if defect == "missing-trace":
                        driver.events.clear()
                    elif defect == "old-identity":
                        driver._ambient_cave["stage"]["identities"] |= {driver.events[0]["object"]["name"]}
                    elif defect == "wrong-type":
                        driver.events[0]["object"]["typeId"] = "another-monster"
                    else:
                        driver.state["monsters"] -= 1
                    with self.assertRaises(AssertionError):
                        afterAmbientCaveTurn(driver)
                self.assertEqual([], driver.checks)

    def testAmbientRemovalBeforeExhaustionCannotBecomeAnEmptySuccess(self):
        driver = self.ambientDriver(rolls=[1])
        captureAmbientCave(driver)
        checkpoint, records = self.nativeTrace(driver)
        with checkpoint, records:
            beforeAmbientCaveTurn(driver)
            driver.cave.onTurn(None)
            driver.handles.pop(ambientCaveDefinition("vhulmarn")["name"])
            driver.state["turn"] += 1
            with self.assertRaisesRegex(AssertionError, "entered before its spawn and exhausted states"):
                afterAmbientCaveTurn(driver)
        self.assertEqual([], driver.checks)

    def testAmbientExhaustionRejectsFreshCloneWithoutCounterDecrement(self):
        driver = self.ambientDriver(rolls=[1] * 6)
        captureAmbientCave(driver)
        checkpoint, records = self.nativeTrace(driver)
        with checkpoint, records:
            for _ in range(6):
                driver.tick()
            beforeAmbientCaveTurn(driver)
            template = driver.objects["template"]
            unexpected = template.clone()
            driver.handles[unexpected.name] = {"__handle__": unexpected.name}
            driver.objects[unexpected.name] = unexpected
            unexpected.moveTo(*ambientCaveDefinition("vhulmarn")["coords"])
            driver.state["turn"] += 1
            with self.assertRaisesRegex(AssertionError, "exhausted cave created a fresh"):
                afterAmbientCaveTurn(driver)
        self.assertEqual(["vhulmarn.cave.timedSpawn"], [row[0] for row in driver.checks])

    def testInactiveRitualUsesActualCaveAndTurnCallbacksForTwoRealTurns(self):
        driver = self.ritualDriver()
        verifyInactiveRitualCaves(driver)
        self.assertEqual(2, driver.state["turn"])
        self.assertEqual([("ritual.cave.inactive", True)], [(key, condition) for key, condition, _ in driver.checks])
        self.assertEqual([1, 2], driver.checks[0][2]["actualTurns"])
        driver.world.addObject.assert_not_called()
        for actor in driver.registry.values():
            actor.getObjectProperty.assert_not_called()

    def testInactiveRitualRejectsNoTurnAndWrongCounter(self):
        driver = self.ritualDriver()
        driver.tick = lambda: None
        with self.assertRaisesRegex(AssertionError, "completed real map turn"):
            verifyInactiveRitualCaves(driver)
        self.assertEqual([], driver.checks)
        driver = self.ritualDriver()
        driver.registry[RITUAL_ANCHORS[0]].getNumericProperty = lambda key: 1 if key == "monsters" else 0
        with self.assertRaises(AssertionError):
            verifyInactiveRitualCaves(driver)
        self.assertEqual(0, driver.state["turn"])
        self.assertEqual([], driver.checks)

    def testInactiveRitualRejectsUnexpectedActorCreation(self):
        driver = self.ritualDriver()
        native_tick = driver.tick

        def broken_tick():
            native_tick()
            native_call = driver.call
            driver.call = lambda handle, method, *args: (
                native_call(handle, method, *args) + [{"__handle__": "unexpected-monster"}]
                if handle == driver.game_map and method == "getObjects"
                else native_call(handle, method, *args)
            )

        driver.tick = broken_tick
        with self.assertRaisesRegex(AssertionError, "created or removed a map actor"):
            verifyInactiveRitualCaves(driver)
        self.assertEqual([], driver.checks)
