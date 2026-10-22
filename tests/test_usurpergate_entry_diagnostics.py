# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source/model coverage of Usurpergate entry failure diagnostics, not native route proof."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def entryFunction():
    tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_usurpergate_mercy_route_diverges_from_wrath_and_standalone"
    )
    return next(node for node in method.body if isinstance(node, ast.FunctionDef) and node.name == "enter_start")


class UsurpergateEntryDiagnosticsTest(unittest.TestCase):
    def fixture(self, *, settled=False, fail_coords=False, messages=None, panel_count=0):
        calls = []
        start = object()
        panel_type = type("ObservedPanel", (), {})
        panels = [panel_type() for _ in range(panel_count)]
        world = SimpleNamespace(
            start=start,
            mapName="usurpergate",
            isMoving=lambda: True,
            getObjectByName=lambda name: world.start,
            getBoolProperty=lambda name: name == "usurpergate_intro",
        )

        def canStep(coords):
            calls.append(("canStep", (coords.x, coords.y, coords.z)))
            return True

        world.canStep = canStep
        position = [12, 22, 0]

        def coords():
            if fail_coords:
                raise RuntimeError("position diagnostic sentinel")
            return SimpleNamespace(x=position[0], y=position[1], z=position[2])

        def moveTo(x, y, z):
            calls.append(("moveTo", (x, y, z)))
            position[:] = [x, y, z]

        player = SimpleNamespace(getCoords=coords, moveTo=moveTo)
        game = SimpleNamespace(
            getMap=lambda: world,
            getGui=lambda: SimpleNamespace(getChildren=lambda: panels),
        )

        def pump(predicate, *, timeout):
            if settled:
                world.start = None
            calls.append(("pump", timeout, predicate()))
            return settled

        namespace = {
            "self": self,
            "game": SimpleNamespace(Coords=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)),
            "start_definition": {"x": 12 * 32, "y": 21 * 32},
            "messages": messages if messages is not None else [],
            "pumpQueuedUntil": pump,
            "json": json,
        }
        exec(
            compile(ast.Module(body=[entryFunction()], type_ignores=[]), "authored-usurpergate-entry", "exec"),
            namespace,
        )
        return namespace["enter_start"], game, player, calls

    def failureReceipt(self, entry, game, player):
        with self.assertRaises(AssertionError) as failure:
            entry(game, player)
        message = str(failure.exception)
        self.assertIn("Usurpergate start did not settle: ", message)
        return json.loads(message.split("Usurpergate start did not settle: ", 1)[1])

    def testTimeoutRecordsActualBeforeAndAfterWithoutChangingTheDeadline(self):
        entry, game, player, calls = self.fixture(messages=["The captured introduction"])
        receipt = self.failureReceipt(entry, game, player)
        self.assertEqual([12, 21, 0], receipt["authoredTarget"])
        self.assertEqual([12, 22, 0], receipt["before"]["playerCoords"])
        self.assertEqual([12, 21, 0], receipt["after"]["playerCoords"])
        for state in (receipt["before"], receipt["after"]):
            self.assertEqual("usurpergate", state["activeMapName"])
            self.assertTrue(state["mapMoving"])
            self.assertTrue(state["targetCanStep"])
            self.assertTrue(state["startPresent"])
            self.assertTrue(state["sameInitialStart"])
            self.assertTrue(state["intro"])
            self.assertFalse(state["mercyRouteApplied"])
            self.assertEqual(["The captured introduction"], state["messages"])
        self.assertEqual(1, sum(call[0] == "moveTo" for call in calls))
        self.assertEqual([("pump", 2.0, False)], [call for call in calls if call[0] == "pump"])

    def testSuccessKeepsTheExistingRemovalPredicateAndDoesNotCollectAnAfterReceipt(self):
        entry, game, player, calls = self.fixture(settled=True)
        self.assertIsNone(entry(game, player))
        self.assertEqual([("pump", 2.0, True)], [call for call in calls if call[0] == "pump"])
        self.assertEqual(1, sum(call[0] == "canStep" for call in calls))
        self.assertEqual(1, sum(call[0] == "moveTo" for call in calls))

    def testDiagnosticMessagesAndAttachedPanelNamesAreBounded(self):
        entry, game, player, _calls = self.fixture(
            messages=[str(index) + "x" * 900 for index in range(30)], panel_count=30
        )
        receipt = self.failureReceipt(entry, game, player)
        for state in (receipt["before"], receipt["after"]):
            self.assertEqual(8, len(state["messages"]))
            self.assertTrue(all(len(message) <= 512 for message in state["messages"]))
            self.assertTrue(state["messages"][0].startswith("22"))
            self.assertEqual(["ObservedPanel"] * 16, state["attachedPanelClasses"])

    def testUnavailableDiagnosticFieldRetainsTheOriginalTimeoutFailure(self):
        entry, game, player, _calls = self.fixture(fail_coords=True)
        receipt = self.failureReceipt(entry, game, player)
        for state in (receipt["before"], receipt["after"]):
            self.assertEqual({"error": "RuntimeError: position diagnostic sentinel"}, state["playerCoords"])
            self.assertTrue(state["startPresent"])


if __name__ == "__main__":
    unittest.main()
