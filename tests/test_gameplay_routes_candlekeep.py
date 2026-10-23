# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Candlekeep route API/reward regressions with strict model handles; no native MCP acceptance."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from tests import gameplay_routes_candlekeep as routes
from tests.test_candlekeep_content import CandlekeepModel

ROOT = Path(__file__).resolve().parents[1]


def exportedHandleMethods():
    tree = ast.parse((ROOT / "mcp.py").read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "MCP_ALLOWED_HANDLE_METHODS" for target in item.targets)
    )
    return ast.literal_eval(node.value)


class GameplayCandlekeepRoutesTest(unittest.TestCase):
    def driver(self, actor, *, intelligence=8, standing=0, corrupt=None):
        model = CandlekeepModel(intelligence=intelligence)
        model.player.base_stats.setNumericProperty("intelligence", 99)
        model.game_map.setNumericProperty("candlekeepStanding", standing)
        dialog = model.dialog(actor)
        if actor == "dreppin":
            model.enter(actor)
            model.enter(actor)
            self.assertTrue(dialog.questActive())
        else:
            self.assertTrue(dialog.acceptQuest())
        if actor == "reevor":
            model.game_map.setNumericProperty("candlekeepRatsSlain", 5)
        else:
            model.player.addItem(model.namespace["QUEST_ITEMS"][actor])
        allowed, calls, checked = exportedHandleMethods(), [], []

        def call(target, method, *args):
            classes = ("CGameObject", "CCreature", "CPlayer") if target is model.player else ("CGameObject", "CItem")
            self.assertTrue(
                any(method in allowed[class_id] for class_id in classes),
                "Method `" + method + "` is not exported for handle calls",
            )
            calls.append(("call", method, args))
            return getattr(target, method)(*args)

        def condition(dialog_id, method):
            self.assertIn("createObject", allowed["CGame"])
            self.assertIn("invokeCondition", allowed["CDialog"])
            calls.append(("condition", dialog_id, method))
            return bool(getattr(model.createObject(dialog_id), method)())

        def choose(dialog_id, action, condition=None):
            self.assertIn("invokeAction", allowed["CDialog"])
            authored = model.createObject(dialog_id)
            if condition:
                self.assertTrue(getattr(authored, condition)())
            result = getattr(authored, action)()
            calls.append(("choose", dialog_id, action))
            if action == "returnQuest" and corrupt:
                corrupt(model)
            return result

        def navigateTo(name):
            point = model.game_map.getObjectByName(name).getCoords()
            model.player.moveTo(point.x, point.y, point.z)

        def questNames(completed=False):
            quests = model.player.getCompletedQuests() if completed else model.player.getQuests()
            return [quest.getTypeId() for quest in quests]

        def check(branch, success, **_details):
            self.assertTrue(success, branch)
            checked.append(branch)

        driver = SimpleNamespace(
            test=self,
            player=model.player,
            call=call,
            condition=condition,
            navigateTo=navigateTo,
            choose=choose,
            gold=model.player.getGold,
            number=model.game_map.getNumericProperty,
            questNames=questNames,
            check=check,
        )
        return driver, model, calls, checked

    def testCompletionReadsAuthoredComposedReactionThroughExportedDialogCondition(self):
        for actor in ("hull", "fuller"):
            for intelligence, standing, gold_delta in (
                (11, 0, 10),
                (12, 0, 20 if actor == "hull" else 0),
                (8, 3, 10),
                (8, 4, 20 if actor == "hull" else 0),
                (15, -4, 10),
                (15, -3, 20 if actor == "hull" else 0),
            ):
                with self.subTest(actor=actor, intelligence=intelligence, standing=standing):
                    driver, model, calls, checked = self.driver(actor, intelligence=intelligence, standing=standing)
                    before = model.player.getGold(), model.player.getNumericProperty("exp")
                    routes.complete(driver, actor)
                    self.assertEqual(before[0] + gold_delta, model.player.getGold())
                    self.assertEqual(before[1] + 50, model.player.getNumericProperty("exp"))
                    self.assertEqual(
                        [("condition", actor + "Dialog", "highReaction")],
                        [row for row in calls if row[0] == "condition"],
                    )
                    self.assertFalse(any(row[:2] == ("call", "getStats") for row in calls))
                    self.assertEqual(
                        ["candlekeep.quest." + actor + ".complete", "candlekeep.quest." + actor + ".repeat"], checked
                    )
                    if actor == "fuller":
                        self.assertEqual(
                            int(intelligence + standing >= 12), model.player.countItems("candlekeepDaggerPlusOne")
                        )

    def testEveryErrandRetainsExactExperienceItemConsumptionCompletionAndRepeatChecks(self):
        for actor in routes.QUESTS:
            with self.subTest(actor=actor):
                driver, model, _calls, _checked = self.driver(actor, intelligence=12)
                before = model.player.getGold(), model.player.getNumericProperty("exp")
                routes.complete(driver, actor)
                self.assertEqual(
                    before[0] + (20 if actor == "hull" else 5 if actor == "reevor" else 0), model.player.getGold()
                )
                self.assertEqual(before[1] + 50, model.player.getNumericProperty("exp"))
                self.assertIn(actor + "Quest", driver.questNames(completed=True))
                self.assertNotIn(actor + "Quest", driver.questNames())
                if actor != "reevor":
                    self.assertEqual(0, model.player.countItems(model.namespace["QUEST_ITEMS"][actor]))
                self.assertEqual("completed", model.game_map.getStringProperty("candlekeep_" + actor + "Stage"))

    def testIncorrectGoldOrExperienceStillFailsTheExactRouteAssertions(self):
        for actor, corrupt in (
            ("hull", lambda model: model.player.addGold(1)),
            ("fuller", lambda model: model.player.addGold(1)),
            ("reevor", lambda model: model.player.addExp(1)),
        ):
            with self.subTest(actor=actor):
                driver, _model, _calls, _checked = self.driver(actor, intelligence=11, corrupt=corrupt)
                with self.assertRaises(AssertionError):
                    routes.complete(driver, actor)

    def testFullerFavorableRewardKeepsTheSameAlreadyStolenUniqueDagger(self):
        driver, model, _calls, _checked = self.driver("fuller", intelligence=12)
        fuller = model.game_map.getObjectByName("fuller")
        dagger = next(item for item in fuller.getItems() if item.getTypeId() == "candlekeepDaggerPlusOne")
        fuller.removeQuestItem(lambda item: item is dagger)
        model.player.addItem(dagger)
        before = model.player.getGold()
        routes.complete(driver, "fuller")
        self.assertEqual(before, model.player.getGold())
        self.assertEqual(1, model.player.countItems("candlekeepDaggerPlusOne"))
        self.assertIn(dagger, model.player.getItems())
        self.assertNotIn(dagger, fuller.getItems())
