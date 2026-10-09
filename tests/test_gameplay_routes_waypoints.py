# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual shared callbacks supply source-ordered connector publication to route oracles."""

from collections import namedtuple
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from tests.gameplay_routes_waypoints import captureWaypointCreation, verifyWaypointPublication, waypointDefinitions

Coords = namedtuple("Coords", "x y z")


def waypointTypes():
    types = {}
    game = ModuleType("game")
    game.CBuilding = game.CScroll = type("PluginBase", (), {})
    game.Coords = Coords
    game.showReader = game.requirementMessage = game.randint = game.claim_once = lambda *args: None

    def register(context):
        def decorate(cls):
            types[cls.__name__] = cls
            return cls

        return decorate

    game.register = register
    path = Path(__file__).resolve().parents[1] / "res/plugins/object.py"
    namespace = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    with patch.dict("sys.modules", {"game": game}):
        namespace["load"](None, object())
    return types


class GameplayWaypointPublicationTest(unittest.TestCase):
    def driver(self, map_name):
        types = waypointTypes()
        actors, edges, credited = {}, [], []
        world = SimpleNamespace()
        world.getObjectByName = actors.get
        world.canStep = lambda coords: True
        world.hasNavigationEdge = lambda source, target, name: (tuple(source), tuple(target), name) in edges
        world.unregisterNavigationEdgesForObject = lambda name: edges.__setitem__(
            slice(None), [edge for edge in edges if edge[2] != name]
        )
        world.registerNavigationEdge = lambda source, target, enabled, bidirectional, cost, name: edges.append(
            (tuple(source), tuple(target), name)
        )
        for definition in waypointDefinitions(map_name):
            actor = types[definition["class"]]()
            properties = {"enabled": definition["enabled"], "exit": definition["exit"]}
            actor.getMap = lambda: world
            actor.getName = lambda name=definition["name"]: name
            actor.getCoords = lambda coords=definition["coords"]: Coords(*coords)
            actor.getBoolProperty = lambda key, properties=properties: bool(properties.get(key, False))
            actor.getStringProperty = lambda key, properties=properties: properties.get(key, "")
            actor.getNumericProperty = lambda key, properties=properties: properties.get(key, 0)
            actor.setBoolProperty = actor.setNumericProperty = (
                lambda key, value, properties=properties: properties.__setitem__(key, value)
            )
            actor.properties = properties
            actors[definition["name"]] = actor
            actor.onCreate(None)

        def call(handle, method, *args):
            if isinstance(handle, dict):
                if method == "getTurn":
                    return driver.turn
                if method == "getNavigationNeighbors":
                    source = tuple(args[0])
                    x, y, z = source
                    neighbors = [(x - 1, y, z), (x + 1, y, z), (x, y - 1, z), (x, y + 1, z)]
                    for origin, target, name in edges:
                        if origin == source and target not in neighbors:
                            neighbors.append(target)
                    return neighbors
                raise AssertionError(method)
            return getattr(handle, method)(*args)

        def tick():
            driver.turn += 1
            for actor in actors.values():
                actor.onTurn(None)

        driver = SimpleNamespace(
            test=self,
            map_name=map_name,
            game_map={"__handle__": map_name},
            turn=0,
            object=actors.__getitem__,
            coords=lambda actor: tuple(actor.getCoords()),
            canStep=world.canStep,
            _coordinateHandle=lambda coords: Coords(*coords),
            call=call,
            check=lambda branch, condition, **evidence: credited.append((branch, condition, evidence)),
            tick=tick,
            actors=actors,
            edges=edges,
            credited=credited,
        )
        return driver

    def testSourceOrderPermitsForwardReferencesOnlyAfterActualTurn(self):
        initial = {
            "ninemarches": {"monolithCoast", "monolithCold"},
            "sunderedmarch": {"monolithPyre"},
            "test": {"teleporter3", "groundHole"},
        }
        for map_name, expected in initial.items():
            with self.subTest(map=map_name):
                driver = self.driver(map_name)
                captureWaypointCreation(driver)
                actual = {row["name"] for row in driver._waypoint_creation["records"] if row["published"]}
                self.assertEqual(expected, actual)
                driver.tick()
                verifyWaypointPublication(driver)
                self.assertEqual([(map_name + ".waypoint.published", True)], [row[:2] for row in driver.credited])
                edge_count = len(driver.edges)
                driver.tick()
                verifyWaypointPublication(driver)
                self.assertEqual(edge_count, len(driver.edges), "Actual onTurn publication should reuse its owned edge")

    def testPublicationCannotBeCreditedBeforeAnActualTurn(self):
        driver = self.driver("test")
        captureWaypointCreation(driver)
        with self.assertRaisesRegex(AssertionError, "actual authored map turn"):
            verifyWaypointPublication(driver)
        self.assertFalse(driver.credited)
        driver.tick()
        with self.assertRaisesRegex(AssertionError, "before the first real map turn"):
            captureWaypointCreation(driver)

    def testTurnSnapshotRejectsMissingEnabledEdgesAndPublishedDisabledConnector(self):
        for defect in ("missingEnabledEdge", "publishedDisabled", "disabledEdge"):
            with self.subTest(defect=defect):
                driver = self.driver("test")
                captureWaypointCreation(driver)
                driver.tick()
                if defect == "missingEnabledEdge":
                    driver.edges[:] = [edge for edge in driver.edges if edge[2] != "teleporter1"]
                elif defect == "publishedDisabled":
                    driver.actors["teleporter2"].properties["waypoint"] = True
                else:
                    driver.edges.append(((16, 3, 0), (16, 9, 0), "teleporter2"))
                with self.assertRaises(AssertionError):
                    verifyWaypointPublication(driver)
                self.assertFalse(driver.credited)

    def testPublicationCannotReuseCreationSnapshotFromAnotherMapInstance(self):
        driver = self.driver("test")
        captureWaypointCreation(driver)
        driver.tick()
        driver.game_map = {"__handle__": "different-live-map"}
        with self.assertRaises(AssertionError):
            verifyWaypointPublication(driver)
        self.assertFalse(driver.credited)
