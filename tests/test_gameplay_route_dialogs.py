# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored route sequencing regressions, without native gameplay credit."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_branch_driver import GameplayBranchDriver
from tests.gameplay_branch_types import RouteCase
from tests import gameplay_routes_ninemarches as marches
from tests import gameplay_routes_nouraajd as nouraajd


def authoredFunction(source, function_name, *, class_id=None, **namespace):
    path = Path(__file__).resolve().parents[1] / source
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if class_id:
        tree = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_id)
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function_name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), source, "exec"), namespace)
    return namespace[function_name]


class GameplayRouteDialogTest(unittest.TestCase):
    def driver(self, map_name):
        case = RouteCase("dialog-regression", "unit", (map_name,), ("unit.branch",), lambda d: None)
        driver = GameplayBranchDriver(self, Mock(), None, case, "Warrior", Path("."))
        driver.harness._mcp_engine_call.return_value = True
        driver.map_name = map_name
        driver.game = {"__handle__": "game"}
        driver.game_map = {"__handle__": "map"}
        driver.player = {"__handle__": "player"}
        driver.trace_path = Path(__file__).with_name("absent-unit-native.trace.jsonl")
        driver.pump = Mock()
        driver.record = Mock()
        driver.navigateTo = Mock()
        driver.revisit = Mock()
        return driver

    def testThreatenedGateRouteClosesRejectionBeforeOpeningTheGate(self):
        driver = self.driver("nouraajd")
        driver.startCampaign = Mock()
        driver.hunt = Mock()
        driver.object = Mock(return_value={"__handle__": "door"})
        actions = []

        def call(handle, method, *args):
            if method == "createObject":
                return {"__handle__": args[0]}
            if method == "invokeAction":
                actions.append(args[0])
            elif method == "getBoolProperty":
                return "open_door" in actions
            elif method == "invokeCondition":
                return False

        driver.call = call
        nouraajd.start(driver, gate="threatened")
        self.assertEqual(["threatenGate", "open_door"], actions)
        self.assertEqual("EXIT", driver._dialog_positions[("nouraajd", "doorDialog")])

    def testCompanionRouteClosesAcceptanceReminderAndRecruitmentBeforeBanter(self):
        for item_first in (False, True):
            with self.subTest(item_first=item_first):
                driver = self.driver("ninemarches")
                state = {"started": False, "joined": False, "item": False, "gift": 0, "reputation": 0}
                actions = []

                def call(handle, method, *args):
                    if method == "createObject":
                        return {"__handle__": args[0]}
                    if method == "getNumericProperty":
                        return state[args[0]]
                    if method == "invokeCondition":
                        return {
                            "not_met": not state["started"],
                            "can_recruit": state["started"] and state["item"] and not state["joined"],
                            "is_joined": state["joined"],
                            "has_left": False,
                            "questInProgress": state["started"] and not state["item"] and not state["joined"],
                        }[args[0]]
                    if method == "invokeAction":
                        actions.append(args[0])
                        if args[0] == "start":
                            state["started"] = True
                        elif args[0] == "recruit":
                            state["joined"] = True
                            state["reputation"] += 2
                            state["gift"] += 1

                driver.call = call
                driver.navigateTo = lambda name, **kwargs: state.update(item=True) if name == "banditCache" else None
                driver.flag = lambda name: state["started"]
                driver.count = lambda item: int(state["item"]) if item == "banditLedger" else state["gift"]
                driver.questNames = lambda completed=False: ["haldaQuest"] if state["joined"] and completed else []
                with patch.object(marches, "verifyJournals"):
                    marches.recruit(driver, "halda", item_first=item_first)
                driver.choose("knightDialog", "banter", condition="is_joined")
                driver.select("knightDialog", "LOYAL", 0)
                self.assertEqual(["start", "recruit", "banter"], actions)
                self.assertEqual("EXIT", driver._dialog_positions[("ninemarches", "knightDialog")])

    def testDirectVictorRouteUsesTheAuthoredCourtyardPathState(self):
        driver = self.driver("nouraajd")
        driver.object = Mock(return_value={"__handle__": "tavern"})
        actions = []

        def call(handle, method, *args):
            if method == "createObject":
                return {"__handle__": args[0]}
            if method == "getNumericProperty":
                return 0
            if method == "getTurn":
                return 51
            if method == "invokeCondition":
                return False
            if method == "invokeAction":
                actions.append(args[0])

        driver.call = call
        driver.flag = lambda name: "talked_to_victor" in actions
        driver.string = lambda name: "encounter_active" if "spawn_cultists" in actions else "met_victor"
        nouraajd.meetVictor(driver, "forceful", direct=True, ask_girl=False)
        self.assertEqual(["confrontVictorForcefully", "talked_to_victor", "spawn_cultists"], actions)
        self.assertEqual("EXIT", driver._dialog_positions[("nouraajd", "tavernDialog2")])

    def testCompletedContractCannotReopenUntilAcknowledgementExits(self):
        driver = self.driver("nouraajd")
        driver.call = lambda handle, method, *args: (
            {"__handle__": args[0]}
            if method == "createObject"
            else args[0] == "contract_completed" if method == "invokeCondition" else None
        )
        driver.choose("dialog", "accept_quest", condition="contract_completed")
        with self.assertRaisesRegex(AssertionError, "No reachable authored dialog option"):
            driver.choose("dialog", "accept_quest", condition="contract_completed")
        driver.select("dialog", "COMPLETED_THANKS", 0)
        driver.choose("dialog", "accept_quest", condition="contract_completed")
        self.assertEqual("COMPLETED_THANKS", driver._dialog_positions[("nouraajd", "dialog")])

    def testVictorFleeUsesTheTurnObservedByTheAuthoredTimer(self):
        state = {"turn": 84, "quest": "encounter_active", "position": (60, 110, 0), "leader": True}
        quest = SimpleNamespace(
            get_state=lambda name: state["quest"],
            mark_victor_bad_end=lambda: state.update(quest="bad_end"),
        )
        game_map = SimpleNamespace(
            getNumericProperty=lambda name: 10,
            getTurn=lambda: state["turn"],
            getGame=lambda: None,
        )
        expire = authoredFunction(
            "res/maps/nouraajd/script.py",
            "_expire_victor_search",
            _get_quest_system=lambda game_map: quest,
            _clear_victor_encounter=lambda game_map: state.update(leader=False),
            VICTOR_COURTYARD_TIMEOUT_TURNS=75,
            showReader=Mock(),
        )

        def step(target):
            state["position"] = target
            # CMap::move dispatches synchronous onTurn callbacks before turn++.
            expire(game_map)
            state["turn"] += 1

        driver = SimpleNamespace(
            test=self,
            game_map=game_map,
            number=lambda name: 10,
            call=lambda handle, method: getattr(handle, method)(),
            coords=lambda handle=None: (45, 100, 0) if handle else state["position"],
            object=lambda name, required=False: "leader" if name == "cultLeaderQuest" and state["leader"] else None,
            canStep=lambda target: True,
            step=step,
            string=lambda name: state["quest"],
        )
        nouraajd.fleeCourtyardUntil(driver, 75, allow_timeout=True)
        self.assertEqual(85, state["turn"])
        self.assertEqual("encounter_active", state["quest"])
        self.assertTrue(state["leader"])
        nouraajd.fleeCourtyardUntil(driver, 76, allow_timeout=True)
        self.assertEqual(86, state["turn"])
        self.assertEqual("bad_end", state["quest"])
        self.assertFalse(state["leader"])

    def testPairedPortalsReenterTheArrivalObjectBeforeTestingItsReverse(self):
        driver = self.driver("ninemarches")
        definitions = json.loads(
            (Path(__file__).resolve().parents[1] / "res/maps/ninemarches/config.json").read_text(encoding="utf-8")
        )
        names = ("monolithHub", "monolithCoast", "monolithAsh", "monolithCold")
        positions = {name: (10 * index, 0, 0) for index, name in enumerate(names, 1)}
        state = {"position": (0, 0, 0)}
        entered = []
        on_enter = authoredFunction(
            "res/plugins/object.py", "onEnter", class_id="WayPoint", active_waypoint_causes=set()
        )

        class Creature:
            def setCoords(self, coords):
                state.update(position=coords)

        creature = Creature()
        event = SimpleNamespace(getCause=lambda: creature)

        def navigateTo(name, **kwargs):
            if state["position"] == positions[name]:
                return
            state["position"] = positions[name]
            entered.append(name)
            exit_name = definitions[name]["properties"]["exit"]
            on_enter(SimpleNamespace(getExit=lambda: positions[exit_name]), event)

        driver.object = lambda name: name
        driver.coords = lambda handle=None: positions[handle] if handle else state["position"]
        driver.navigateCoords = lambda coords: state.update(position=coords)
        driver.navigateTo = navigateTo
        driver._coordinateHandle = lambda coords: coords
        driver.call = lambda handle, method, *args: True if method == "canStep" else None
        driver.revisit = lambda name: GameplayBranchDriver.revisit(driver, name)
        driver.check = lambda branch_id, condition, **evidence: self.assertTrue(condition, branch_id)
        with patch.object(marches, "start"):
            marches.portals(driver)
        self.assertEqual(list(names), entered)
