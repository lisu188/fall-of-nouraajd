# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual plugin callbacks must complete one transfer before permitting another."""

from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def waypointTypes(source=None):
    registered = {}
    game = ModuleType("game")
    game.CBuilding = game.CScroll = type("PluginBase", (), {})
    game.Coords = lambda x, y, z: (x, y, z)
    game.showReader = game.requirementMessage = game.randint = game.claim_once = lambda *args: None

    def register(context):
        def decorate(cls):
            registered[cls.__name__] = cls
            return cls

        return decorate

    game.register = register
    namespace = {}
    path = ROOT / "res/plugins/object.py"
    exec(compile(source if source is not None else path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    with patch.dict("sys.modules", {"game": game}):
        namespace["load"](None, object())
    return registered


class WaypointTraversalTest(unittest.TestCase):
    def pair(self):
        types = waypointTypes()
        left, right = types["Teleporter"](), types["Teleporter"]()
        portals = {"left": left, "right": right}
        game_map = SimpleNamespace(getObjectByName=portals.get, canStep=lambda coords: True)
        for name, portal in portals.items():
            portal.getMap = lambda: game_map
            portal.getCoords = lambda name=name: name
            portal.getBoolProperty = lambda field: True
            portal.getStringProperty = lambda field, name=name: "right" if name == "left" else "left"

        class Creature:
            def __init__(self):
                self.coords = "left"
                self.arrivals = []

            def setCoords(self, coords):
                self.coords = coords
                self.arrivals.append(coords)
                if len(self.arrivals) > 4:
                    raise AssertionError("Recursive return portal did not stop")
                portals[coords].onEnter(SimpleNamespace(getCause=lambda: self))

        return left, right, Creature

    def testPairedTeleportersTransferOnceAndAllowLaterReturnVisits(self):
        left, right, Creature = self.pair()
        creature = Creature()
        event = SimpleNamespace(getCause=lambda: creature)
        left.onEnter(event)
        self.assertEqual("right", creature.coords)
        self.assertEqual(["right"], creature.arrivals)
        right.onEnter(event)
        self.assertEqual("left", creature.coords)
        self.assertEqual(["right", "left"], creature.arrivals)

    def testTransferGuardIsReleasedAfterFailedMovement(self):
        left, _right, Creature = self.pair()
        creature = Creature()
        event = SimpleNamespace(getCause=lambda: creature)
        move = creature.setCoords
        creature.setCoords = lambda coords: (_ for _ in ()).throw(RuntimeError("movement failed"))
        with self.assertRaisesRegex(RuntimeError, "movement failed"):
            left.onEnter(event)
        creature.setCoords = move
        left.onEnter(event)
        self.assertEqual("right", creature.coords)
        self.assertEqual(["right"], creature.arrivals)

    def testTransferGuardDoesNotSuppressAnotherCreature(self):
        left, _right, Creature = self.pair()
        first, second = Creature(), Creature()
        first_move = first.setCoords

        def move(coords):
            left.onEnter(SimpleNamespace(getCause=lambda: second))
            first_move(coords)

        first.setCoords = move
        left.onEnter(SimpleNamespace(getCause=lambda: first))
        for creature in (first, second):
            self.assertEqual("right", creature.coords)
            self.assertEqual(["right"], creature.arrivals)

    def testMissingEventCauseAndBlockedExitDoNotMove(self):
        left, _right, Creature = self.pair()
        creature = Creature()
        left.onEnter(None)
        left.onEnter(SimpleNamespace(getCause=lambda: None))
        left.getMap().canStep = lambda coords: False
        left.onEnter(SimpleNamespace(getCause=lambda: creature))
        self.assertEqual("left", creature.coords)
        self.assertEqual([], creature.arrivals)
