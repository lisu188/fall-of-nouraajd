# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored dialog graph regressions for natural route sequencing, without native gameplay credit."""

from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_branch_driver import GameplayBranchDriver
from tests.gameplay_branch_types import RouteCase
from tests import gameplay_routes_ninemarches as marches
from tests import gameplay_routes_nouraajd as nouraajd


class GameplayRouteDialogTest(unittest.TestCase):
    def driver(self, map_name):
        case = RouteCase("dialog-regression", "unit", (map_name,), ("unit.branch",), lambda d: None)
        driver = GameplayBranchDriver(self, Mock(), None, case, "Warrior", Path("."))
        driver.map_name = map_name
        driver.game = {"__handle__": "game"}
        driver.game_map = {"__handle__": "map"}
        driver.player = {"__handle__": "player"}
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
                driver.navigateTo = lambda name: state.update(item=True) if name == "banditCache" else None
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
