# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure recipe witness regressions; mocked outcomes provide no native branch evidence."""

from copy import deepcopy
from types import SimpleNamespace
import json
import unittest
from unittest.mock import Mock, patch

from tests import gameplay_routes_crafting as crafting


class GameplayCraftingRoutesTest(unittest.TestCase):
    def driver(self, *, outcome="success", chance=100):
        recipe = {
            "station": "scribeDesk",
            "inputs": [{"item": "Scroll", "count": 1}, {"item": "ManaPotion", "count": 1}],
            "output": {"item": "TownPortalScroll", "count": 1},
            "gold": 35,
            "unlockFlag": "CAN_CRAFT_SCROLLS",
            "successChance": chance,
        }
        items = {"paper": "Scroll", "mana": "ManaPotion", "retained": "Sword"}
        if outcome == "missingIngredients":
            del items["paper"]
        state = {
            "items": items,
            "gold": 20 if outcome == "insufficientGold" else 90,
            "unlocked": outcome != "locked",
            "hp": 50,
            "coords": (5, 6, 0),
            "corrupt": None,
        }
        player, world, station = ({"__handle__": identity} for identity in ("player", "world", "station"))
        definitions = patch.object(crafting, "recipeDefinitions", return_value={"recipe": recipe})
        definitions.start()
        self.addCleanup(definitions.stop)

        def call(handle, method, *args):
            if method == "getItems":
                return [{"__handle__": identity} for identity in state["items"]]
            if method == "getTypeId":
                return state["items"][handle["__handle__"]]
            if method == "getType":
                return "CraftingStation"
            if method == "getBoolProperty":
                return True if args[0] == "enabled" else state["unlocked"]
            if method == "getStringProperty":
                return "scribeDesk" if args[0] == "craftingStationId" else "Actual scribe desk"
            if method == "getTurn":
                return 12
            if method == "getHp":
                return state["hp"]
            if method == "getMana":
                return 30
            if method == "getNumericProperty":
                return 500
            if method == "getEquipped":
                return {"0": {"__handle__": "equipped"}}
            if method == "getName":
                return "hero"
            raise AssertionError((handle, method, args))

        def visit(driver, name, event, *, navigate=None):
            self.assertEqual(("station", "choice_requested"), (name, event))
            detail = (
                "Locked" if not state["unlocked"] else "Missing: Scroll" if "paper" not in state["items"] else "Ready"
            )
            payload = json.dumps([{"id": "recipe", "enabled": outcome in {"success", "failure"}, "detail": detail}])
            return (
                {
                    "seq": 4,
                    "title": "Actual scribe desk",
                    "headless": True,
                    "choicesJson": payload,
                    "choicesJsonLength": len(payload.encode()),
                    "actionLabel": "Craft",
                    "backLabel": "Leave station",
                    "playerCoords": dict(zip("xyz", state["coords"])),
                    "player": {"name": "hero"},
                },
            )

        visitor = patch.object(crafting, "visitService", side_effect=visit)
        visitor_mock = visitor.start()
        self.addCleanup(visitor.stop)

        def engine(name, *args):
            self.assertEqual("craftRecipe", name)
            if outcome in {"success", "failure"}:
                state["items"].pop("paper")
                state["items"].pop("mana")
                state["gold"] -= 35
                if outcome == "success":
                    state["items"]["output"] = "TownPortalScroll"
            if state["corrupt"]:
                state["corrupt"]()
            reason = {
                "success": "",
                "failure": "failed",
                "locked": "locked",
                "missingIngredients": "missing:Scroll",
                "insufficientGold": "missing:gold",
            }[outcome]
            return {"ok": outcome == "success", "reason": reason}

        driver = SimpleNamespace(
            test=self,
            player=player,
            game_map=world,
            game={"__handle__": "game"},
            coords=lambda: state["coords"],
            call=call,
            gold=lambda: state["gold"],
            questNames=lambda completed=False: ["completed" if completed else "active"],
            object=lambda name: station,
            engine=Mock(side_effect=engine),
            pump=Mock(),
            check=Mock(),
        )
        return driver, state, recipe, visitor_mock

    def testEveryDeclaredOutcomeHasExactCostsAndOneActualAttempt(self):
        for outcome in ("locked", "missingIngredients", "insufficientGold", "success", "failure"):
            with self.subTest(outcome=outcome):
                driver, state, _, visitor = self.driver(outcome=outcome, chance=85)
                before = deepcopy(state["items"])
                crafting.recipeAttempt(driver, "station", "recipe", "branch", outcome=outcome)
                driver.engine.assert_called_once_with("craftRecipe", driver.game, driver.object("station"), "recipe")
                driver.pump.assert_called_once_with()
                driver.check.assert_called_once()
                visitor.assert_called_once()
                if outcome not in {"success", "failure"}:
                    self.assertEqual(before, state["items"])

    def testRecipeWitnessRejectsWrongCostsForeignConsumptionExtraOutputAndUnrelatedChanges(self):
        for corruption in ("gold", "foreign-item", "duplicate-output", "wrong-output", "retained-type", "hp"):
            with self.subTest(corruption=corruption):
                driver, state, _, _ = self.driver()

                def corrupt():
                    if corruption == "gold":
                        state["gold"] += 1
                    elif corruption == "foreign-item":
                        state["items"].pop("retained")
                    elif corruption == "duplicate-output":
                        state["items"]["duplicate"] = "TownPortalScroll"
                    elif corruption == "wrong-output":
                        state["items"]["output"] = "Scroll"
                    elif corruption == "retained-type":
                        state["items"]["retained"] = "Armor"
                    else:
                        state["hp"] -= 1

                state["corrupt"] = corrupt
                with self.assertRaises(AssertionError):
                    crafting.recipeAttempt(driver, "station", "recipe", "branch", outcome="success")
                driver.engine.assert_called_once()
                driver.check.assert_not_called()

    def testRejectionCannotConsumeInputsOrChargeGold(self):
        for outcome in ("locked", "missingIngredients", "insufficientGold"):
            for corruption in ("item", "gold"):
                with self.subTest(outcome=outcome, corruption=corruption):
                    driver, state, _, _ = self.driver(outcome=outcome)
                    state["corrupt"] = (
                        (lambda: state["items"].pop("retained"))
                        if corruption == "item"
                        else (lambda: state.update(gold=state["gold"] - 1))
                    )
                    with self.assertRaises(AssertionError):
                        crafting.recipeAttempt(driver, "station", "recipe", "branch", outcome=outcome)
                    driver.check.assert_not_called()

    def testUnmetPreconditionAndGuaranteedFailureNeverDispatchOrRetry(self):
        for violation in ("locked", "missing", "poor", "guaranteed-failure"):
            with self.subTest(violation=violation):
                driver, state, _, _ = self.driver(outcome="failure" if violation == "guaranteed-failure" else "success")
                if violation == "locked":
                    state["unlocked"] = False
                elif violation == "missing":
                    state["items"].pop("paper")
                elif violation == "poor":
                    state["gold"] = 0
                with self.assertRaises(AssertionError):
                    crafting.recipeAttempt(
                        driver,
                        "station",
                        "recipe",
                        "branch",
                        outcome=("failure" if violation == "guaranteed-failure" else "success"),
                    )
                driver.engine.assert_not_called()
                driver.check.assert_not_called()

    def testWrongStochasticOutcomeFailsAfterExactlyOneAttempt(self):
        driver, _, _, _ = self.driver(outcome="failure", chance=85)
        with self.assertRaisesRegex(AssertionError, "declared outcome was not observed"):
            crafting.recipeAttempt(driver, "station", "recipe", "branch", outcome="success")
        driver.engine.assert_called_once()
        driver.check.assert_not_called()

    def testStationWitnessUsesOptionalNavigatorAndCreditsOnlyActualFullPayload(self):
        driver, _, _, visitor = self.driver(outcome="locked")
        navigate = Mock()
        choices = crafting.openStation(driver, "station", "opened", navigate=navigate)
        self.assertEqual("recipe", choices[0]["id"])
        visitor.assert_called_once_with(driver, "station", "choice_requested", navigate=navigate)
        driver.check.assert_called_once()
        driver.engine.assert_not_called()
        original = visitor.side_effect
        visitor.side_effect = lambda *args, **kwargs: ({**original(*args, **kwargs)[0], "choicesJsonLength": 99999},)
        driver.check.reset_mock()
        with self.assertRaisesRegex(AssertionError, "Choice payload was truncated"):
            crafting.openStation(driver, "station", "opened")
        driver.check.assert_not_called()
