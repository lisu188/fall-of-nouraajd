# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Journal verifier failures are tested with doubles; natural witnesses run over MCP."""

from pathlib import Path
import unittest

import mcp

from tests.gameplay_branch_journals import assertOutcomeText, questSpecs, rememberJournalContext, verifyJournals


class JournalDriver:
    def __init__(self, test):
        self.test = test
        self.player = "player"
        self.map_name = "ritual"
        self.active = []
        spec = questSpecs()["mainQuest"]
        self.quest = {
            "name": "mainQuest",
            "type": "mainQuest",
            "description": spec["description"],
            "objective": "Follow Sergeant Rolf's trail, recover his skull, then slay Gooby beneath Nouraajd.",
            "reward": "200 gold from relieved townsfolk.",
            "hint": "Search the cave outside town.",
            "questJournalVersion": 1,
            "questJournalOrigin": "nouraajd",
            "questJournalCompleted": True,
        }
        for field in ("objective", "reward", "hint"):
            self.quest["questJournal" + field.capitalize()] = self.quest[field]
        self.completed = [self.quest]
        self.player_properties = {"campaign_history": "", "nouraajdVictorState": "good_end"}

    def call(self, handle, method, *args):
        if handle == self.player:
            if method == "getQuests":
                return self.active
            if method == "getCompletedQuests":
                return self.completed
            if method == "getStringProperty":
                return self.player_properties.get(args[0], "")
        if method in ("getNumericProperty", "getStringProperty", "getBoolProperty"):
            return handle.get(
                args[0], {"getNumericProperty": 0, "getStringProperty": "", "getBoolProperty": False}[method]
            )
        return handle[
            {
                "getName": "name",
                "getTypeId": "type",
                "getObjective": "objective",
                "getReward": "reward",
                "getHint": "hint",
            }[method]
        ]

    def flag(self, name):
        return False

    def number(self, name):
        return 0

    def string(self, name):
        return ""


class GameplayBranchJournalsTest(unittest.TestCase):
    def testJournalUsesTheBoundMcpDescriptionPropertyAndQuestTextGetters(self):
        driver = JournalDriver(self)

        class CGameObject:
            def getName(self):
                return driver.quest["name"]

            def getTypeId(self):
                return driver.quest["type"]

            def getStringProperty(self, name):
                return driver.quest.get(name, "")

            def getNumericProperty(self, name):
                return driver.quest.get(name, 0)

            def getBoolProperty(self, name):
                return driver.quest.get(name, False)

        class CQuest(CGameObject):
            def getObjective(self):
                return driver.quest["objective"]

            def getReward(self):
                return driver.quest["reward"]

            def getHint(self):
                return driver.quest["hint"]

        server = mcp.EngineMcpServer(Path("."), Path("."))
        server.handles["quest"] = CQuest()
        original_call = driver.call
        calls = []

        def call(handle, method, *args):
            if handle is not driver.quest:
                return original_call(handle, method, *args)
            calls.append((method, args))
            response = server._engine_handle_call({"handle": "quest", "method": method, "args": list(args)})
            self.assertFalse(response["isError"], response)
            return response["structuredContent"]["result"]

        driver.call = call
        records = verifyJournals(driver)
        self.assertEqual(driver.quest["description"], records["mainQuest"]["description"])
        self.assertIn(("getStringProperty", ("description",)), calls)
        self.assertNotIn("getDescription", {method for method, _args in calls})
        for method in ("getObjective", "getReward", "getHint"):
            self.assertIn((method, ()), calls)

    def testOffMapCompletedJournalRetainsSourceDescriptionAndCapturedText(self):
        driver = JournalDriver(self)
        result = verifyJournals(driver)
        self.assertEqual("nouraajd", result["mainQuest"]["origin"])
        self.assertTrue(result["mainQuest"]["completed"])
        self.assertIn("slay Gooby", result["mainQuest"]["objective"])
        self.assertEqual(result, verifyJournals(driver))

    def testDestinationDependentGetterCannotReplaceCapturedObjective(self):
        driver = JournalDriver(self)
        driver.quest["objective"] = "Defeat the ritual leader."
        with self.assertRaisesRegex(AssertionError, "off-map journal changed"):
            verifyJournals(driver)

    def testNeutralLegacyTextIsRejectedForFreshAuthoredRoutes(self):
        driver = JournalDriver(self)
        driver.quest["hint"] = "This older save has no recorded outcome details; details are unavailable."
        with self.assertRaisesRegex(AssertionError, "unexpected legacy neutral text"):
            verifyJournals(driver)

    def testCompletedJournalCannotChangeAcrossLaterProgression(self):
        driver = JournalDriver(self)
        verifyJournals(driver)
        driver.quest["objective"] += " A later map incorrectly appended text."
        driver.quest["questJournalObjective"] = driver.quest["objective"]
        with self.assertRaisesRegex(AssertionError, "Completed history changed"):
            verifyJournals(driver)

    def testOneQuestCannotBeBothActiveAndCompleted(self):
        driver = JournalDriver(self)
        driver.active = [driver.quest]
        with self.assertRaises(AssertionError):
            verifyJournals(driver)

    def testVictorAndVossOutcomesMustAgreeWithObservedCampaignState(self):
        driver = JournalDriver(self)
        victor = {
            "id": "victorQuest",
            "completed": True,
            "origin": "nouraajd",
            "objective": "Victor's daughter was taken when the courtyard rite ended.",
            "reward": "No reward.",
        }
        with self.assertRaises(AssertionError):
            assertOutcomeText(driver, victor, {})
        driver.player_properties["campaign_history"] = "homecoming:completed,rescue:spared"
        voss = {
            "id": "gravemoorQuest",
            "completed": True,
            "origin": "gravemoor",
            "objective": "The moor keeps the traitor. The Usurper's Gate lies ahead.",
            "reward": "The loyalists.",
        }
        with self.assertRaises(AssertionError):
            assertOutcomeText(driver, voss, {})

    def testOffMapCaptiveJournalRequiresActualSourceObservation(self):
        driver = JournalDriver(self)
        driver.map_name = "siege"
        record = {
            "id": "rescueCaptiveQuest",
            "completed": True,
            "origin": "ritual",
            "objective": "The captive was lost to the rite.",
            "reward": "100 gold for the warning.",
        }
        with self.assertRaisesRegex(AssertionError, "real source-state observation"):
            assertOutcomeText(driver, record, {})
        assertOutcomeText(driver, record, {"ritual": {"lost": True}})

    def testStandaloneJudgmentReadsTheRetainedSourceMapAfterTransition(self):
        driver = JournalDriver(self)
        driver.map_name = "usurpergate"
        driver._journal_source_context = {"gravemoor": {"judged": False, "spared": False}}
        source_map = {"voss_judged": True, "voss_spared": True}
        context = rememberJournalContext(driver, source_map=source_map, map_name="gravemoor")
        record = {
            "id": "gravemoorQuest",
            "completed": True,
            "origin": "gravemoor",
            "objective": "Voss lives in the Warden's debt. The Usurper's Gate lies ahead.",
            "reward": "The loyalists of the marches.",
        }
        self.assertEqual({"judged": True, "spared": True}, context["gravemoor"])
        assertOutcomeText(driver, record, context)
        source_map["voss_spared"] = False
        context = rememberJournalContext(driver, source_map=source_map, map_name="gravemoor")
        with self.assertRaises(AssertionError):
            assertOutcomeText(driver, record, context)


if __name__ == "__main__":
    unittest.main()
