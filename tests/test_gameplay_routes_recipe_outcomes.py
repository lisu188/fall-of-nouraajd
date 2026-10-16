# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure proof of real quest ordering and bounded owned-reagent sale selection."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_branch_types import PLAYER_CLASSES
from tests import gameplay_routes_recipe_outcomes as routes


class GameplayRecipeOutcomesTest(unittest.TestCase):
    def driver(self, items, *, quest_items=()):
        state = {"items": dict(items), "gold": 0}
        player = {"__handle__": "player"}

        def call(handle, method, *args):
            if method == "getItems":
                return [{"__handle__": identity} for identity in state["items"]]
            if method == "getTypeId":
                return state["items"][handle["__handle__"]]
            if method == "getName":
                return handle["__handle__"]
            if method == "hasTag":
                self.assertEqual(("quest",), args)
                return handle["__handle__"] in quest_items
            self.fail((handle, method, args))

        def sell(market, item):
            self.assertEqual("market1", market)
            state["items"].pop(item["__handle__"])
            state["gold"] += 7

        driver = SimpleNamespace(test=self, player=player, call=call, navigateTo=Mock(), sellAt=Mock(side_effect=sell))
        return driver, state

    def testAllFourUnlockedRecipesHaveOneMandatoryCaseForEveryExistingClass(self):
        self.assertEqual(1, len(routes.CASES))
        case = routes.CASES[0]
        self.assertEqual(PLAYER_CLASSES, case.classes)
        self.assertEqual(("nouraajd",), case.maps)
        self.assertEqual("fallOfNouraajd", case.campaign)
        recipes = routes.recipeDefinitions()
        self.assertEqual(
            set(routes.GREATER_RECIPES),
            {
                identity
                for identity, recipe in recipes.items()
                if recipe.get("unlockFlag") == "CAN_BREW_GREATER_POTIONS"
            },
        )
        self.assertEqual(
            tuple("nouraajd.crafting." + identity + ".missingIngredients" for identity in routes.GREATER_RECIPES),
            case.branches,
        )

    def testMissingWitnessesFollowActualLetterRelicAndHandInWithoutTheConditionalCatacombsHelper(self):
        events = []
        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            call=Mock(side_effect=lambda *args: events.append("native-unlock-check") or True),
        )
        with (
            patch.object(routes, "start", side_effect=lambda d: events.append("start")),
            patch.object(
                routes, "ownedIdentities", side_effect=lambda d: events.append("protect-starting-items") or {"starter"}
            ),
            patch.object(routes, "prepareRolf", side_effect=lambda d: events.append("rolf")),
            patch.object(routes, "letter", side_effect=lambda d: events.append("letter")),
            patch.object(routes, "relic", side_effect=lambda d: events.append("actual-relic")),
            patch.object(routes, "handInRelic", side_effect=lambda d: events.append("actual-hand-in")),
            patch.object(
                routes,
                "sellForMissingIngredient",
                side_effect=lambda d, identity, **kw: events.append(("sale", identity, kw)),
            ) as sales,
            patch.object(
                routes,
                "recipeAttempt",
                side_effect=lambda d, station, identity, branch, **kw: events.append(("attempt", identity, branch, kw)),
            ) as attempts,
        ):
            routes.unlockedMissingRecipes(driver)
        self.assertEqual(
            [
                "start",
                "protect-starting-items",
                "rolf",
                "letter",
                "actual-relic",
                "actual-hand-in",
                "native-unlock-check",
            ],
            events[:7],
        )
        self.assertEqual(list(routes.GREATER_RECIPES), [call.args[1] for call in sales.call_args_list])
        self.assertEqual(list(routes.GREATER_RECIPES), [call.args[2] for call in attempts.call_args_list])
        self.assertTrue(all(call.kwargs == {"protected_items": {"starter"}} for call in sales.call_args_list))
        self.assertTrue(all(call.kwargs == {"outcome": "missingIngredients"} for call in attempts.call_args_list))

    def testAlreadyMissingIngredientDoesNotSellOrNavigate(self):
        driver, state = self.driver({"one": "LifePotion", "unrelated": "ManaPotion"})
        self.assertEqual((), routes.sellForMissingIngredient(driver, "blend_greater_life_potion"))
        driver.sellAt.assert_not_called()
        driver.navigateTo.assert_not_called()
        self.assertEqual(2, len(state["items"]))

    def testSurplusSaleUsesOnlyActualMatchingUnprotectedHandlesAndLeavesOneReagent(self):
        driver, state = self.driver(
            {"starter": "LifePotion", "third": "LifePotion", "second": "LifePotion", "mana": "ManaPotion"}
        )
        self.assertEqual(
            ("second", "third"),
            routes.sellForMissingIngredient(driver, "blend_greater_life_potion", protected_items={"starter"}),
        )
        self.assertEqual({"starter": "LifePotion", "mana": "ManaPotion"}, state["items"])
        self.assertEqual(14, state["gold"])
        driver.navigateTo.assert_called_once_with("market1")
        self.assertEqual(2, driver.sellAt.call_count)

    def testProtectedOrQuestReagentsCannotBeSoldToFabricateThePrerequisite(self):
        for protected, quest in (({"first", "second"}, ()), ((), {"first", "second"})):
            with self.subTest(protected=protected, quest=quest):
                driver, state = self.driver({"first": "LifePotion", "second": "LifePotion"}, quest_items=quest)
                with self.assertRaisesRegex(AssertionError, "cannot sell starter equipment"):
                    routes.sellForMissingIngredient(driver, "blend_greater_life_potion", protected_items=protected)
                driver.sellAt.assert_not_called()
                self.assertEqual(2, len(state["items"]))

    def testOverlargeObservedReagentListFailsBeforeAnyTrade(self):
        driver, state = self.driver({str(index): "LifePotion" for index in range(129)})
        with self.assertRaisesRegex(AssertionError, "bounded observed reagent inventory"):
            routes.sellForMissingIngredient(driver, "blend_greater_life_potion")
        driver.sellAt.assert_not_called()
        self.assertEqual(129, len(state["items"]))

    def testSaleSelectionRechecksInventoryAfterActualTravelAndRejectsCollateralMutation(self):
        driver, state = self.driver({"first": "LifePotion", "second": "LifePotion", "keep": "ManaPotion"})
        driver.navigateTo.side_effect = lambda name: state["items"].pop("first")
        self.assertEqual((), routes.sellForMissingIngredient(driver, "blend_greater_life_potion"))
        driver.sellAt.assert_not_called()

        driver, state = self.driver({"first": "LifePotion", "second": "LifePotion", "keep": "ManaPotion"})
        original = driver.sellAt.side_effect

        def corrupt(market, item):
            original(market, item)
            state["items"].pop("keep")

        driver.sellAt.side_effect = corrupt
        with self.assertRaisesRegex(AssertionError, "another actual owned identity"):
            routes.sellForMissingIngredient(driver, "blend_greater_life_potion")
        driver.sellAt.assert_called_once()


if __name__ == "__main__":
    unittest.main()
