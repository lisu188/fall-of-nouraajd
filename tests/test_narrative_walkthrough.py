# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-only survival regressions for the narrative MCP route driver."""

import json
import unittest

from tests.narrative_walkthrough import NarrativeWalkthrough


class RouteSession:
    def __init__(self, *, defeat_on=None, receipt="", victory_rollback=False, blocked=False):
        self.position = (0, 0, 0)
        self.hp = 10
        self.receipt = receipt
        self.defeatOn = defeat_on
        self.victoryRollback = victory_rollback
        self.blocked = blocked
        self.pending = None
        self.defeated = False
        self.moves = self.turns = 0
        self.nativeTurn = 41
        self.calls = []

    def engineCall(self, name, args):
        if name == "event_loop.instance":
            return "loop"
        if name == "jsonify":
            if args == ["player"]:
                properties = {
                    "posx": self.position[0],
                    "posy": self.position[1],
                    "posz": self.position[2],
                    "hp": self.hp,
                    "mana": 4,
                    "uiDefeatReceipt": self.receipt,
                }
            elif args == ["leader"]:
                properties = {"posx": 1, "posy": 0, "posz": 0, "hp": 9, "mana": 3}
            elif args == ["spawn"]:
                properties = {"posx": 1, "posy": 0, "posz": 0}
            else:
                raise AssertionError((name, args))
            return json.dumps({"properties": properties})
        raise AssertionError((name, args))

    def handleCall(self, handle, method, args):
        self.calls.append((handle, method, args))
        if handle == "player":
            if method == "isAlive":
                return self.hp > 0
            if method == "getStringProperty" and args == ["uiDefeatReceipt"]:
                return self.receipt
            if method == "moveTo":
                self.moves += 1
                self.position = tuple(args)
                self.pending = "movement"
                return None
            if method in ("getHp", "getHpMax", "getMana", "getManaMax"):
                return {"getHp": self.hp, "getHpMax": 10, "getMana": 4, "getManaMax": 8}[method]
            if method == "countItems" and args[0] in ("LifePotion", "ManaPotion"):
                return 6
        if handle == "map":
            if method == "move":
                self.turns += 1
                self.nativeTurn += 1
                self.pending = "turn"
                return None
            if method == "getTurn":
                return self.nativeTurn
            if method == "getStringProperty" and args == ["mapName"]:
                return "ritual"
            if method == "getObjectByName":
                return {"ritualLeader": "leader", "bossSpawn": "spawn"}[args[0]]
        if handle == "loop" and method == "run":
            if self.defeatOn is not None and self.pending == self.defeatOn and not self.defeated:
                self.receipt = json.dumps({"map": "Ritual", "hp": 0, "x": 1, "y": 0, "z": 0, "lostItemCount": 12})
                self.hp = 1
                self.position = (0, 0, 0)
                self.defeated = True
            elif self.pending == "movement" and (self.blocked or (self.victoryRollback and self.moves == 1)):
                self.position = (0, 0, 0)
            self.pending = None
            return None
        raise AssertionError((handle, method, args))

    def driver(self):
        driver = NarrativeWalkthrough(self.engineCall, self.handleCall, "game", "map", "player")
        driver.walkable = {(0, 0, 0), (1, 0, 0)}
        driver.objects = {"bossSpawn": (1, 0, 0)}
        return driver


class NarrativeWalkthroughSurvivalTest(unittest.TestCase):
    def assertDefeatState(self, error, session, *, target, movement_steps, map_turns):
        state = error.exception.args[0]
        self.assertEqual("Walkthrough player was defeated", state["reason"])
        self.assertEqual(session.receipt, state["uiDefeatReceipt"])
        self.assertEqual(session.position, state["playerCoords"])
        self.assertEqual(session.nativeTurn, state["nativeTurn"])
        self.assertEqual(movement_steps, state["movementSteps"])
        self.assertEqual(map_turns, state["mapTurns"])
        self.assertEqual(target, state["target"]["coords"])
        self.assertEqual(1, state["player"]["hp"])
        self.assertEqual(
            {"hp": 1, "hpMax": 10, "mana": 4, "manaMax": 8, "LifePotion": 6, "ManaPotion": 6}, state["resources"]
        )
        if target:
            self.assertEqual(9, state["target"]["objects"]["ritualLeader"]["hp"])
            self.assertEqual(3, state["target"]["objects"]["ritualLeader"]["mana"])

    def testFreshFixtureRejectsAnExistingReceiptWithoutClearingIt(self):
        session = RouteSession(receipt='{"map":"Earlier defeat"}')
        with self.assertRaises(AssertionError) as error:
            session.driver()
        self.assertEqual("fresh fixture", error.exception.args[0]["stage"])
        self.assertEqual(session.receipt, error.exception.args[0]["uiDefeatReceipt"])
        self.assertEqual(0, session.moves + session.turns)
        self.assertFalse(any(method.startswith("set") for _, method, _ in session.calls))

    def testMoveToPumpRejectsRevivedDefeatBeforeAnotherMapTurn(self):
        session = RouteSession(defeat_on="movement")
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.walkTo((1, 0, 0))
        self.assertDefeatState(error, session, target=(1, 0, 0), movement_steps=1, map_turns=0)
        self.assertEqual(1, session.moves)
        self.assertEqual(0, session.turns)
        self.assertTrue(session.hp > 0)

    def testMapMovePumpRejectsRevivedDefeat(self):
        session = RouteSession(defeat_on="turn")
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.tick()
        self.assertDefeatState(error, session, target=None, movement_steps=0, map_turns=1)
        self.assertEqual(1, session.turns)
        self.assertTrue(session.hp > 0)

    def testArrivalAndStopCannotHideAnExistingDefeatReceipt(self):
        for stop in (None, lambda: True):
            with self.subTest(stop=stop is not None):
                session = RouteSession()
                driver = session.driver()
                session.receipt = "defeat recorded since the previous pump"
                with self.assertRaises(AssertionError):
                    driver.walkTo((0, 0, 0), stop=stop)
                self.assertEqual(0, session.moves + session.turns)

    def testOrdinaryVictoryRollbackCanRetryWithAnEmptyReceipt(self):
        session = RouteSession(victory_rollback=True)
        driver = session.driver()
        driver.walkTo((1, 0, 0))
        self.assertEqual((1, 0, 0), session.position)
        self.assertEqual("", session.receipt)
        self.assertEqual(2, session.moves)
        self.assertEqual(2, session.turns)
        self.assertEqual(2, driver.log["movementSteps"])
        self.assertEqual(2, driver.log["mapTurns"])

    def testEmptyReceiptAllowsOrdinaryMovementAndTurns(self):
        session = RouteSession()
        driver = session.driver()
        driver.walkTo((1, 0, 0))
        driver.tick()
        self.assertEqual("", session.receipt)
        self.assertEqual(1, session.moves)
        self.assertEqual(2, session.turns)

    def testHealthyMovementBudgetFailureIncludesResourcesAndKeeps256Steps(self):
        session = RouteSession(blocked=True)
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.walkTo((1, 0, 0))
        state = error.exception.args[0]
        self.assertEqual("Movement did not reach the authored target", state["reason"])
        self.assertEqual("movement budget", state["stage"])
        self.assertEqual("", state["uiDefeatReceipt"])
        self.assertEqual(256, session.moves)
        self.assertEqual(256, session.turns)
        self.assertEqual(297, state["nativeTurn"])
        self.assertEqual(10, state["resources"]["hp"])
        self.assertEqual(6, state["resources"]["LifePotion"])
        self.assertEqual(6, state["resources"]["ManaPotion"])
        self.assertEqual(9, state["target"]["objects"]["ritualLeader"]["hp"])

    def testMissingAuthoredRouteIncludesResourcesAndTheOriginalRouteError(self):
        session = RouteSession()
        driver = session.driver()
        driver.walkable = {(0, 0, 0)}
        with self.assertRaises(AssertionError) as error:
            driver.walkTo((1, 0, 0))
        state = error.exception.args[0]
        self.assertEqual("No adjacent authored route", state["reason"])
        self.assertEqual("", state["uiDefeatReceipt"])
        self.assertEqual(41, state["nativeTurn"])
        self.assertEqual(10, state["resources"]["hp"])
        self.assertEqual(9, state["target"]["objects"]["ritualLeader"]["hp"])
        self.assertIn("No authored walkable route", str(error.exception.__cause__))
        self.assertEqual(0, session.moves + session.turns)


if __name__ == "__main__":
    unittest.main()
