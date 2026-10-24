# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source/model checks for Usurpergate entry boundaries and diagnostics, not native route proof."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import weakref

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

    def campaignBoundaryFixture(self, mode):
        from tests.test_castle_campaign import FakeMap, FakeObject

        source = ast.parse((ROOT / "res/maps/usurpergate/script.py").read_text(encoding="utf-8"))
        load = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "load")
        definitions = []
        for node in load.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in {"MERCY_ROUTE_DEFENDERS", "MERCY_ARRIVAL_TEXT"}
                for target in node.targets
            ):
                definitions.append(node)
            elif isinstance(node, ast.FunctionDef) and node.name in {
                "ensure_quest",
                "usurpergate_flags_default",
                "mercy_route_active",
                "applyMercyRouteFlow",
            }:
                definitions.append(node)
            elif isinstance(node, ast.ClassDef) and node.name == "UsurpergateStart":
                node.decorator_list = []
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        method.decorator_list = []
                definitions.append(node)
        world = FakeMap()

        class NativeGame:
            def getMap(self):
                return world

        native_game = NativeGame()
        world.game = native_game
        boundary_calls = []

        def state(argument):
            # Model the exact Py_TYPE comparison in CLoader::wrap_helper_function.
            if type(argument) is not NativeGame:
                raise TypeError("Resource helpers require the native game instance")
            boundary_calls.append(argument)
            return (
                None
                if mode == "standalone"
                else SimpleNamespace(active=lambda: True, campaign_id=lambda: "wardensRoad", scenario=lambda: mode)
            )

        namespace = {"CEvent": FakeObject, "campaign": SimpleNamespace(state=state), "ref": weakref.ref}
        ui_tree = ast.parse((ROOT / "res/ui.py").read_text(encoding="utf-8"))
        ui_helpers = [
            node
            for node in ui_tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            and node.name in {"UiFlowGame", "flowGame", "uiRequest"}
        ]
        helpers = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
        removals = [
            node
            for node in helpers.body
            if isinstance(node, ast.FunctionDef) and node.name in {"removeObjectFlow", "removeObjectsFlow"}
        ]
        exec(
            compile(
                ast.Module(body=ui_helpers + removals + definitions, type_ignores=[]), "authored-usurpergate", "exec"
            ),
            namespace,
        )
        start = namespace["UsurpergateStart"]("usurpergateStart", world, text="Standard source introduction")
        world.objects[start.getName()] = start
        defenders = ("curtainWallWest1", "curtainWallWest2", "housecarlWest")
        for name in defenders + ("curtainWallEast1", "curtainWallEast2", "housecarlEast", "theUsurper"):
            world.objects[name] = FakeObject(name, world)
        event = SimpleNamespace(getCause=lambda: world.player)
        return namespace, native_game, world, start, event, boundary_calls, defenders

    def testSourceEntryUsesNativeGameAtTheStrictCampaignBoundaryForAllThreeRoutes(self):
        for mode in ("standalone", "assault_wrath", "assault_mercy"):
            with self.subTest(mode=mode):
                namespace, native_game, world, start, event, boundary_calls, defenders = self.campaignBoundaryFixture(
                    mode
                )
                readers, removals = [], []
                flow = start.onEnter(event)
                self.addCleanup(flow.close)
                for request in flow:
                    if request["operation"] == "gui.removeObject":
                        target, actor = request["args"]
                        self.assertIs(world, target)
                        removals.append(actor.getName())
                        del world.objects[actor.getName()]
                    else:
                        self.assertEqual("showReader", request["operation"])
                        weak_game, title, body = request["args"]
                        self.assertIsInstance(weak_game, namespace["UiFlowGame"])
                        self.assertIs(native_game, weak_game.resolve())
                        readers.append((title, body))
                        self.assertEqual(mode == "assault_mercy", all(name not in world.objects for name in defenders))
                self.assertEqual([native_game], boundary_calls)
                self.assertEqual(1, len(readers))
                self.assertEqual(mode == "assault_mercy", "Voss's ledgers named" in readers[0][1])
                self.assertTrue(world.getBoolProperty("usurpergate_intro"))
                self.assertEqual(mode == "assault_mercy", world.getBoolProperty("mercy_route_applied"))
                self.assertNotIn("usurpergateStart", world.objects)
                self.assertEqual(
                    [*defenders, "usurpergateStart"] if mode == "assault_mercy" else ["usurpergateStart"], removals
                )
                self.assertEqual(["usurpergateQuest"], [quest.getName() for quest in world.player.getQuests()])
                repeated = start.onEnter(event)
                self.assertEqual([], list(repeated))
                self.assertEqual([native_game], boundary_calls)
                self.assertEqual(1, len(world.player.getQuests()))

    def testCampaignBoundaryRemainsStrictAndNonPlayerEntryDoesNotConsultIt(self):
        namespace, native_game, world, start, _event, calls, _defenders = self.campaignBoundaryFixture("standalone")
        source = (ROOT / "src/core/CLoader.cpp").read_text(encoding="utf-8")
        self.assertIn('owner.is_none() && (moduleName == "campaign" || craftingCall)', source)
        self.assertIn("reinterpret_cast<PyObject *>(Py_TYPE(gameArg.ptr())) != gameType.ptr()", source)
        weak_game = namespace["flowGame"](native_game)
        with self.assertRaisesRegex(TypeError, "require the native game instance"):
            namespace["campaign"].state(weak_game)
        other = SimpleNamespace(isPlayer=lambda: False)
        self.assertEqual([], list(start.onEnter(SimpleNamespace(getCause=lambda: other))))
        self.assertEqual([], calls)
        self.assertFalse(world.getBoolProperty("usurpergate_intro"))
        self.assertIn("usurpergateStart", world.objects)


if __name__ == "__main__":
    unittest.main()
