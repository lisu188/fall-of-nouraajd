# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure contract regressions for the natural-play MCP driver."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_branch_driver import FORBIDDEN_METHODS, GameplayBranchDriver, canonicalNativeState
from tests.gameplay_branch_types import RouteCase


class GameplayBranchDriverTest(unittest.TestCase):
    def testNativeSetComparisonsIgnoreAllocationOrderAndPreserveFullIdentity(self):
        first = {
            "items": [
                {"properties": {"name": "sword", "typeId": "Sword", "power": 2, "tags": ["owned", "sharp"]}},
                {"properties": {"name": "potion", "typeId": "LifePotion", "power": 1}},
            ],
            "quests": [{"properties": {"name": "questA"}}, {"properties": {"name": "questB"}}],
            "completedQuests": [{"properties": {"name": "oldA"}}, {"properties": {"name": "oldB"}}],
            "equipped": {"weapon": {"properties": {"name": "sword", "coveredSlots": ["weapon", "offhand"]}}},
            "campaign_history": "first:won,second:left",
            "orderedRoute": ["north", "south"],
        }
        reordered = deepcopy(first)
        for key in ("items", "quests", "completedQuests"):
            reordered[key].reverse()
        reordered["items"][1]["properties"]["tags"].reverse()
        reordered["equipped"]["weapon"]["properties"]["coveredSlots"].reverse()
        self.assertEqual(canonicalNativeState(first), canonicalNativeState(reordered))
        self.assertEqual(["north", "south"], canonicalNativeState(first)["orderedRoute"])
        self.assertEqual("first:won,second:left", canonicalNativeState(first)["campaign_history"])
        self.assertEqual("sword", canonicalNativeState(first)["equipped"]["weapon"]["properties"]["name"])
        for difference in ("missing", "changed", "extra", "duplicate", "differentIdentity", "ordered", "slot"):
            changed = deepcopy(reordered)
            if difference == "missing":
                changed["items"].pop()
            elif difference == "changed":
                changed["items"][0]["properties"]["power"] += 1
            elif difference == "extra":
                changed["quests"].append({"properties": {"name": "extra"}})
            elif difference == "duplicate":
                changed["items"].append(deepcopy(changed["items"][0]))
            elif difference == "differentIdentity":
                changed["items"][0]["properties"]["name"] = "other-instance"
            elif difference == "ordered":
                changed["orderedRoute"].reverse()
            elif difference == "slot":
                changed["equipped"]["offhand"] = changed["equipped"].pop("weapon")
            with self.subTest(difference=difference):
                self.assertNotEqual(canonicalNativeState(first), canonicalNativeState(changed))
        self.assertEqual(["owned", "sharp"], first["items"][0]["properties"]["tags"])

    def driver(self):
        case = RouteCase("unit", "unit", ("test",), ("unit.branch",), lambda driver: None)
        driver = GameplayBranchDriver(self, Mock(), None, case, "Warrior", Path("."))
        driver.game = {"__handle__": "game"}
        driver.game_map = {"__handle__": "map"}
        driver.player = {"__handle__": "player"}
        driver.map_name = "test"
        driver._rawCall = Mock()
        return driver

    def testProgressAndResourceActionsAreIncludedInTheDurableActionSequence(self):
        driver = self.driver()
        driver.record = Mock()
        for method in ("useAction", "sealBreach", "checkQuests"):
            with self.subTest(method=method):
                driver.call(driver.player, method)
                self.assertTrue(driver.record.call_args.kwargs["replay"])
                self.assertEqual(method, driver.record.call_args.args[0]["method"])

    def testFixtureMutationsAreRejectedBeforeDispatch(self):
        driver = self.driver()
        for method in sorted(FORBIDDEN_METHODS):
            with self.subTest(method=method), self.assertRaises(AssertionError):
                driver.call(driver.player, method)
        driver._rawCall.assert_not_called()

    def testMovementRequiresActualPlayerAndOneNativeStep(self):
        driver = self.driver()
        driver.coords = Mock(return_value=(2, 3, 0))
        for target, destination in ((driver.player, (4, 3, 0)), ({"__handle__": "npc"}, (3, 3, 0))):
            with self.subTest(target=target, destination=destination), self.assertRaises(AssertionError):
                driver.call(target, "moveTo", *destination)
        driver._rawCall.assert_not_called()
        driver.call(driver.player, "moveTo", 3, 3, 0)
        driver._rawCall.assert_called_once_with(driver.player, "moveTo", 3, 3, 0)

    def testConsumablesAndEquipmentMustBeOwned(self):
        for method, prefix in (("useItem", ()), ("equipItem", ("weapon",))):
            with self.subTest(method=method):
                driver = self.driver()
                owned, borrowed = {"__handle__": "owned"}, {"__handle__": "shop-stock"}
                driver._rawCall.side_effect = lambda handle, action, *args: [owned] if action == "getItems" else True
                with self.assertRaises(AssertionError):
                    driver.call(driver.player, method, *prefix, borrowed)
                self.assertEqual(["getItems"], [call.args[1] for call in driver._rawCall.call_args_list])
                driver.call(driver.player, method, *prefix, owned)
                driver._rawCall.assert_called_with(driver.player, method, *prefix, owned)

    def testCastleCaptureRejectsRemoteOrNoncanonicalInteractions(self):
        for violation in ("remote", "otherLevel", "otherMap", "detached", "otherPlayer", "notObjective"):
            with self.subTest(violation=violation):
                driver = self.driver()
                marker = {"__handle__": "marker"}
                marker_coords = (
                    (5, 5, 1) if violation == "otherLevel" else (7, 5, 0) if violation == "remote" else (6, 5, 0)
                )
                driver.coords = lambda handle=None: marker_coords if handle == marker else (5, 5, 0)

                def rawCall(handle, method, *args):
                    if method == "getMap":
                        return {"__handle__": "old-map"} if violation == "otherMap" else driver.game_map
                    if method == "getName":
                        return "objective"
                    if method == "getObjectByName":
                        return {"__handle__": "canonical-marker"} if violation == "detached" else marker
                    if method == "getStringProperty":
                        return "" if violation == "notObjective" else "objective"
                    raise AssertionError(("Rejected capture reached native dispatch", method))

                driver._rawCall.side_effect = rawCall
                player = {"__handle__": "npc"} if violation == "otherPlayer" else driver.player
                with self.assertRaises(AssertionError):
                    driver.call(marker, "capture", player)
                self.assertFalse(any(call.args[1] == "capture" for call in driver._rawCall.call_args_list))

    def testCastleCaptureAllowsCanonicalAdjacentPlayerInteraction(self):
        driver = self.driver()
        marker = {"__handle__": "marker"}
        driver.coords = lambda handle=None: (6, 6, 0) if handle == marker else (5, 5, 0)
        values = {
            "getMap": driver.game_map,
            "getName": "objective",
            "getObjectByName": marker,
            "getStringProperty": "objective",
            "capture": False,
        }
        driver._rawCall.side_effect = lambda handle, method, *args: values[method]
        self.assertFalse(driver.call(marker, "capture", driver.player))
        driver._rawCall.assert_called_with(marker, "capture", driver.player)

    def testCastleCaptureAllowlistIsNarrow(self):
        import mcp

        self.assertEqual({"capture"}, mcp.MCP_ALLOWED_HANDLE_METHODS["CastleObjective"])
        self.assertNotIn("capture", mcp.MCP_ALLOWED_HANDLE_METHODS.get("CMapObject", set()))
        self.assertNotIn("capture", mcp.MCP_ALLOWED_HANDLE_METHODS.get("CBuilding", set()))

    def testSuccessfulHotAssertionsDoNotSerializeSnapshots(self):
        driver = self.driver()
        actor = {"__handle__": "enemy"}
        driver._rawCall.side_effect = lambda handle, method, *args: {
            "getObjectByName": actor,
            "getHp": 10,
            "getStringProperty": "",
        }[method]
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        self.assertEqual(actor, driver.object("enemy"))
        driver.assertSurvival()
        driver.snapshot.assert_not_called()

    def testSuccessfulCombatDoesNotSerializeFailureSnapshot(self):
        driver = self.driver()
        actor = {"__handle__": "enemy"}
        state = {"alive": True, "exp": 0}
        driver.object = Mock(side_effect=lambda name, required=True: actor if state["alive"] else None)
        driver._rawCall.side_effect = lambda handle, method, *args: (
            state["alive"] if method == "isAlive" else state["exp"]
        )

        def defeat(name):
            state.update(alive=False, exp=10)

        driver.navigateTo = defeat
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        driver.fight("enemy")
        self.assertEqual(1, driver.combats)
        driver.snapshot.assert_not_called()

    def testOrdinaryAdjacentCellIsNotAPortalArrival(self):
        driver = self.driver()
        for arrival in ((4, 5, 0), (5, 5, 0), (6, 5, 0)):
            self.assertFalse(driver._traversedTarget((5, 5, 0), arrival))
        driver._rawCall.assert_not_called()

    def testPortalArrivalRequiresAuthoredNavigationEdge(self):
        driver = self.driver()
        driver._coordinateHandle = Mock(return_value={"__handle__": "point"})
        driver._rawCall.return_value = [(5, 5, 1), (20, 8, 0)]
        self.assertTrue(driver._traversedTarget((5, 5, 0), (5, 5, 1)))
        self.assertTrue(driver._traversedTarget((5, 5, 0), (20, 8, 0)))
        driver._rawCall.return_value = []
        self.assertFalse(driver._traversedTarget((5, 5, 0), (20, 8, 0)))

    def testPositiveMovementCostDoesNotProveAuthoredRelocation(self):
        driver = self.driver()
        driver._coordinateHandle = lambda coords: {"__handle__": "point", "coords": tuple(coords)}
        driver._rawCall.side_effect = lambda handle, method, *args: (7 if method == "lookupNavigationStepCost" else [])
        self.assertFalse(driver._traversedTarget((5, 5, 0), (20, 8, 0)))
        with self.assertRaisesRegex(AssertionError, "Unexpected unauthored relocation"):
            driver._validateMovement((5, 5, 0), (20, 8, 0))
        with self.assertRaisesRegex(AssertionError, "Unexpected unauthored relocation"):
            driver._validateMovement((5, 5, 0), (5, 5, 1))

    def testMovementValidationAllowsCardinalStepAndRequiresEnabledDirectionalNeighborsForTransit(self):
        driver = self.driver()
        driver._coordinateHandle = lambda coords: {"__handle__": "point", "coords": tuple(coords)}
        origin, entrance, arrival = (5, 5, 0), (6, 5, 0), (20, 8, 1)
        for adjacent in (origin, entrance, (4, 5, 0), (5, 4, 0), (5, 6, 0)):
            driver._validateMovement(origin, adjacent)
        driver._rawCall.assert_not_called()
        driver._rawCall.side_effect = lambda handle, method, *args: ([arrival] if args[0]["coords"] == entrance else [])
        driver._validateMovement(origin, arrival)
        self.assertTrue(driver._traversedTarget(entrance, arrival))
        self.assertFalse(driver._traversedTarget(arrival, entrance))
        driver._rawCall.side_effect = lambda handle, method, *args: [
            (args[0]["coords"][0] + 1, args[0]["coords"][1], args[0]["coords"][2])
        ]
        with self.assertRaisesRegex(AssertionError, "Unexpected unauthored relocation"):
            driver._validateMovement(origin, (7, 5, 0))

    def testMcpNavigationNeighborsExposeOnlyCoordinateValuesWithoutLeakingHandles(self):
        import mcp

        neighbors = [SimpleNamespace(x=6, y=5, z=0), SimpleNamespace(x=20, y=8, z=1)]
        native_map = type("CMap", (), {"getNavigationNeighbors": lambda self, coords: neighbors})()
        server = mcp.EngineMcpServer(Path("."), Path("."))
        map_handle = server._serialize_result(native_map)
        source_handle = server._serialize_result(SimpleNamespace(x=5, y=5, z=0))
        baseline = len(server.handles)
        result = server._engine_handle_call(
            {"handle": map_handle["__handle__"], "method": "getNavigationNeighbors", "args": [source_handle]}
        )
        self.assertFalse(result["isError"])
        self.assertEqual([[6, 5, 0], [20, 8, 1]], result["structuredContent"]["result"])
        self.assertEqual(baseline, len(server.handles))
        self.assertIn("getNavigationNeighbors", mcp.MCP_ALLOWED_HANDLE_METHODS["CMap"])
        for mutation in ("registerNavigationEdge", "unregisterNavigationEdgesForObject"):
            self.assertNotIn(mutation, mcp.MCP_ALLOWED_HANDLE_METHODS["CMap"])
        neighbors.append(SimpleNamespace(x="bad", y=8, z=1))
        result = server._engine_handle_call(
            {"handle": map_handle["__handle__"], "method": "getNavigationNeighbors", "args": [source_handle]}
        )
        self.assertTrue(result["isError"])
        self.assertEqual(baseline, len(server.handles))

    def testCanStepReleasesItsTemporaryCoordinatesOnSuccessAndFailure(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                driver = self.driver()
                point = {"__handle__": "coords"}
                driver._coordinateHandle = Mock(return_value=point)
                driver._ephemeral_handles.add("coords")
                driver._rawCall.side_effect = RuntimeError("native failed") if failure else None
                driver._rawCall.return_value = True
                if failure:
                    with self.assertRaisesRegex(RuntimeError, "native failed"):
                        driver.canStep((5, 6, 0))
                else:
                    self.assertTrue(driver.canStep((5, 6, 0)))
                driver._coordinateHandle.assert_called_once_with((5, 6, 0))
                driver._rawCall.assert_called_once_with(driver.game_map, "canStep", point)
                driver.harness._mcp_tool.assert_called_once_with(
                    None, "engine_release_handles", {"handles": ["coords"]}
                )
                self.assertFalse(driver._ephemeral_handles)

    def testNavigateCoordsReachesTargetRatherThanStoppingAdjacent(self):
        driver = self.driver()
        position = [0, 0, 0]
        driver.coords = lambda handle=None: tuple(position)
        driver._coordinateHandle = Mock(return_value={"__handle__": "point"})
        controller = {"__handle__": "controller"}
        driver._rawCall.side_effect = lambda handle, method, *args: (
            controller if method == "getController" else [] if method == "getNavigationNeighbors" else 0
        )

        def advance():
            position[0] += 1

        driver.tick = Mock(side_effect=advance)
        driver.step = Mock(side_effect=AssertionError("Ordinary navigation switched to legacy adjacent steps"))
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        driver.navigateCoords((3, 0, 0))
        self.assertEqual((3, 0, 0), driver.coords())
        self.assertEqual(3, driver.tick.call_count)
        driver.snapshot.assert_not_called()
        driver.step.assert_not_called()

    def testNavigateToRecognizesPortalAfterEnteringTarget(self):
        driver = self.driver()
        portal, controller, target = ({"__handle__": identity} for identity in ("portal", "controller", "target"))
        position = [0, 0, 0]
        driver.object = Mock(return_value=portal)
        driver._coordinateHandle = Mock(return_value=target)
        driver.coords = lambda handle=None: (1, 0, 0) if handle == portal else tuple(position)
        driver._rawCall.side_effect = lambda handle, method, *args: {
            "getController": controller,
            "getCoords": target,
            "setTarget": None,
            "getNavigationNeighbors": [(9, 0, 1)],
        }[method]

        def enterPortal():
            position[:] = (9, 0, 1)

        driver.tick = Mock(side_effect=enterPortal)
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        driver.navigateTo("portal")
        self.assertEqual((9, 0, 1), driver.coords())
        driver.tick.assert_called_once()
        driver.snapshot.assert_not_called()

    def testStepClearsStaleTargetAtActualPortalArrivalBeforeTurn(self):
        for arrival in ((1, 0, 0), (9, 0, 1)):
            with self.subTest(arrival=arrival):
                driver = self.driver()
                position = [0, 0, 0]
                controller = {"__handle__": "controller"}
                driver.coords = lambda handle=None: tuple(position)
                driver.recover = Mock()
                driver.pump = Mock()
                driver._validateMovement = Mock()
                driver._coordinateHandle = lambda coords: {"__handle__": "point", "coords": coords}
                targets = []

                def rawCall(handle, method, *args):
                    if method == "moveTo":
                        position[:] = arrival
                    elif method == "getController":
                        return controller
                    elif method == "setTarget":
                        targets.append(args[-1]["coords"])

                driver._rawCall.side_effect = rawCall
                driver.tick = Mock(side_effect=lambda: self.assertEqual([arrival], targets))
                driver.step((1, 0, 0))
                driver._validateMovement.assert_called_once_with((0, 0, 0), arrival)
                driver.tick.assert_called_once()

    def testAdjacentCombatPumpsBeforeBoundaryRecoveryAndNextNativeMapTurn(self):
        driver = self.driver()
        position, events, state = [0, 0, 0], [], {"turn": 0}
        controller, point, loop = ({"__handle__": name} for name in ("controller", "point", "loop"))
        driver.coords = lambda handle=None: tuple(position)
        driver.recover = Mock()
        driver.assertSurvival = Mock()
        driver.refresh = Mock()
        driver._captureHuntMovement = Mock()
        driver._validateMovement = Mock()
        driver._coordinateHandle = Mock(return_value=point)
        driver.engine = Mock(return_value=loop)
        driver._hunt_adapter = SimpleNamespace(recover_before_map_turn=lambda: events.append("boundaryRecovery"))

        def rawCall(handle, method, *args):
            if method == "moveTo":
                position[:] = args
                events.append("moveTo")
            elif method == "getController":
                return controller
            elif method == "run":
                events.append("pump")
            elif method == "getTurn":
                return state["turn"]
            elif method == "move":
                events.append("mapMove")
                state["turn"] += 1

        driver._rawCall.side_effect = rawCall
        driver.step((1, 0, 0))
        self.assertLess(events.index("moveTo"), events.index("pump"))
        self.assertLess(events.index("pump"), events.index("boundaryRecovery"))
        self.assertLess(events.index("boundaryRecovery"), events.index("mapMove"))
        self.assertEqual(1, events.count("boundaryRecovery"))
        self.assertEqual(1, state["turn"])

    def testHuntAdapterUsesLegacyAdjacentRouteOnlyForAnActiveCombatBoundary(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        driver = self.driver()
        driver.session = {"proc": object()}
        driver.navigateTo = Mock()
        driver.object = Mock(return_value={"__handle__": "alpha"})
        with patch.object(
            OctobogzMcpWalkthroughTest,
            "defeat",
            lambda instance, name: instance.walkTo(name, allow_removed=True),
        ), patch.object(OctobogzMcpWalkthroughTest, "walkRoute", return_value="adjacent-route") as adjacent, patch(
            "tests.narrative_walkthrough.authoredRegion", return_value=({}, {(0, 0, 0), (1, 0, 0)})
        ):
            driver.hunt("defeat", "alpha")
            driver.navigateTo.assert_called_once_with("alpha")
            adjacent.assert_not_called()
            driver._hunt_adapter.recover_before_map_turn = Mock()
            self.assertEqual("adjacent-route", driver.hunt("defeat", "alpha"))
            adjacent.assert_called_once_with("alpha", allow_removed=True)
            driver.navigateTo.assert_called_once_with("alpha")

    def testLongNavigationReusesDetachedPointAndReleasesConsumedCoordinates(self):
        driver = self.driver()
        point, controller = {"__handle__": "point"}, {"__handle__": "controller"}
        live_coordinates = set()
        state = {"created": 0, "coordinates": 0, "released": 0, "maximumLive": 0}

        def rawCall(handle, method, *args):
            if method == "createObject":
                self.assertEqual(("CMapObject",), args)
                state["created"] += 1
                return point
            if method == "setNumericProperty":
                self.assertEqual(point, handle)
            elif method == "getCoords":
                state["coordinates"] += 1
                identity = "coords-" + str(state["coordinates"])
                live_coordinates.add(identity)
                state["maximumLive"] = max(state["maximumLive"], len(live_coordinates))
                return {"__handle__": identity}
            elif method in {"setTarget", "canStep"}:
                self.assertIn(args[-1]["__handle__"], live_coordinates)
                return True

        def release(session, method, arguments):
            self.assertEqual("engine_release_handles", method)
            live_coordinates.difference_update(arguments["handles"])
            state["released"] += len(arguments["handles"])

        driver._rawCall = rawCall
        driver.harness._mcp_tool = release
        for index in range(10002):
            coordinates = driver._coordinateHandle((index, 1, 0))
            if index % 2:
                driver.call(controller, "setTarget", driver.player, coordinates)
            else:
                driver.call(driver.game_map, "canStep", coordinates)
            self.assertFalse(driver._ephemeral_handles)
        self.assertEqual(1, state["created"])
        self.assertEqual(10002, state["released"])
        self.assertEqual(1, state["maximumLive"])
        self.assertFalse(live_coordinates)

    def testActualDialogResolvesNestedInheritedOptions(self):
        driver = self.driver()
        driver.map_name = "nouraajd"
        states = driver._dialogStates("tavernDialog1")
        options = [entry["properties"] for entry in states["INKEEPER_ABOUT_CULTISTS"]["options"]]
        beer = next(option for option in options if option.get("action") == "sell_beer")
        self.assertEqual("EXIT", beer["nextStateId"])
        self.assertTrue(any(option.get("action") == "asked_about_girl" for option in options))
        self.assertNotIn("ref", beer)

    def testActualNestedDialogActionIsReachableAndExecutedOnce(self):
        driver = self.driver()
        driver.map_name = "nouraajd"
        dialog = {"__handle__": "dialog"}
        driver._rawCall.return_value = dialog
        driver.pump = Mock()
        selected = driver.choose("tavernDialog1", "sell_beer")
        self.assertEqual("sell_beer", selected["action"])
        actions = [call.args for call in driver._rawCall.call_args_list if call.args[1] == "invokeAction"]
        self.assertEqual([(dialog, "invokeAction", "sell_beer")], actions)
        self.assertEqual("EXIT", driver._dialog_positions[("nouraajd", "tavernDialog1")])

    def testActualDialogChecksVisibilityBeforeAction(self):
        driver = self.driver()
        driver.map_name = "ninemarches"
        dialog = {"__handle__": "dialog"}
        driver._rawCall.side_effect = lambda handle, method, *args: dialog if method == "createObject" else False
        driver.pump = Mock()
        with self.assertRaisesRegex(AssertionError, "Authored option is unavailable"):
            driver.choose("knightDialog", "banter", condition="is_joined")
        self.assertFalse(any(call.args[1] == "invokeAction" for call in driver._rawCall.call_args_list))
        driver.pump.assert_not_called()

    def testActualDialogAfterConditionSelectsPostActionState(self):
        for leaves in (False, True):
            with self.subTest(leaves=leaves):
                driver = self.driver()
                driver.map_name = "ninemarches"
                dialog = {"__handle__": "dialog"}
                state = {"acted": False}

                def rawCall(handle, method, *args):
                    if method == "createObject":
                        return dialog
                    if method == "invokeCondition":
                        return args[0] == "is_joined" or (args[0] == "has_left" and state["acted"] and leaves)
                    if method == "invokeAction":
                        state["acted"] = True

                driver._rawCall.side_effect = rawCall
                driver.pump = Mock()
                driver.choose("knightDialog", "banter", condition="is_joined")
                self.assertTrue(state["acted"])
                self.assertEqual(
                    "GONE" if leaves else "LOYAL", driver._dialog_positions[("ninemarches", "knightDialog")]
                )
                methods = [call.args[1:] for call in driver._rawCall.call_args_list]
                self.assertLess(
                    methods.index(("invokeAction", "banter")), methods.index(("invokeCondition", "has_left"))
                )


if __name__ == "__main__":
    unittest.main()
