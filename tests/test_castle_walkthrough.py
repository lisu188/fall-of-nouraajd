# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fast protocol regression for the shared campaign route driver."""

import unittest

from tests.castle_walkthrough import CastleWalkthrough, TransitRoutes


class CastleWalkthroughProtocolTest(unittest.TestCase):
    def testPortalCostQueryUsesCoordinatesRatherThanTileMethods(self):
        position = (0, 0, 0)
        calls = []

        def handleCall(handle, method, args):
            nonlocal position
            calls.append((handle, method, args))
            if handle == "map" and method == "getTile":
                self.assertEqual(args, [10, 0, 1])
                return "destinationTile"
            if handle == "map" and method == "lookupNavigationStepCost":
                self.assertEqual(args, [1, 0, 0, 10, 0, 1])
                return 5
            if handle == "destinationTile" and method == "getNumericProperty":
                self.assertEqual(args, ["movementCost"])
                return 5
            if handle == "player" and method == "moveTo":
                self.assertEqual(args, [1, 0, 0])
                position = (10, 0, 1)
                return None
            if handle == "loop" and method == "run":
                return None
            if handle == "map" and method == "getBoolProperty":
                return False
            self.fail(f"Unexpected protocol call: {handle}.{method}({args})")

        driver = CastleWalkthrough(lambda method, args: "loop", handleCall, "game", "map", "player")
        driver.coords = lambda: position
        driver.walkable = {(0, 0, 0), (1, 0, 0), (10, 0, 1)}
        driver.portals = TransitRoutes()
        driver.portals[(1, 0, 0)] = (10, 0, 1)
        driver.guardsByCell = {}
        driver.mission = {"scenarioId": "homecoming"}

        driver.walkTo((10, 0, 1))

        self.assertEqual(driver.log["steps"], 1)
        self.assertEqual(driver.log["portals"], [{"from": [1, 0, 0], "to": [10, 0, 1], "cost": 5}])
        self.assertFalse(any(method == "getCoords" for _, method, _ in calls))


if __name__ == "__main__":
    unittest.main()
