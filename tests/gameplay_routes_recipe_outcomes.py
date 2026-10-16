# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Recipe prerequisites reached through the real relic quest and finite native trade."""

from collections import Counter

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_routes_crafting import inventoryTypes, recipeAttempt, recipeDefinitions
from tests.gameplay_routes_nouraajd import SOURCES, handInRelic, letter, prepareRolf, relic, start
from tests.gameplay_routes_services import ownedIdentities

GREATER_RECIPES = (
    "blend_greater_life_potion",
    "blend_greater_mana_potion",
    "brew_full_life_potion",
    "brew_full_mana_potion",
)


def missingIngredientsBranch(recipe_id):
    return "nouraajd.crafting." + recipe_id + ".missingIngredients"


def sellForMissingIngredient(d, recipe_id, *, protected_items=()):
    """Sell only existing surplus recipe reagents when natural loot met every input."""
    requirements = Counter()
    for entry in recipeDefinitions()[recipe_id]["inputs"]:
        requirements[entry["item"]] += entry.get("count", 1)

    def isMissing(items):
        counts = Counter(items.values())
        return any(counts[identity] < count for identity, count in requirements.items())

    before = inventoryTypes(d)
    if isMissing(before):
        return ()
    # Travel may earn loot or use a potion; select sale handles only after actual arrival.
    d.navigateTo("market1")
    before = inventoryTypes(d)
    if isMissing(before):
        return ()
    reagent = next(iter(requirements))
    required_sales = Counter(before.values())[reagent] - requirements[reagent] + 1
    candidates = [
        item
        for item in d.call(d.player, "getItems")
        if before[item["__handle__"]] == reagent
        and item["__handle__"] not in protected_items
        and not d.call(item, "hasTag", "quest")
    ]
    d.test.assertLessEqual(len(candidates), 128, "Only the bounded observed reagent inventory may be sold")
    d.test.assertGreaterEqual(
        len(candidates),
        required_sales,
        "A negative recipe case cannot sell starter equipment or a protected quest item",
    )
    candidates.sort(key=lambda item: (d.call(item, "getName"), item["__handle__"]))
    sold = []
    for item in candidates[:required_sales]:
        identity = item["__handle__"]
        d.sellAt("market1", item)
        expected = {key: value for key, value in before.items() if key != identity}
        d.test.assertEqual(expected, inventoryTypes(d), "Reagent sale changed another actual owned identity")
        before = expected
        sold.append(identity)
    d.test.assertTrue(isMissing(before), "Native trade did not establish the missing ingredient prerequisite")
    return tuple(sold)


def unlockedMissingRecipes(d):
    start(d)
    protected_items = ownedIdentities(d)
    prepareRolf(d)
    letter(d)
    relic(d)
    handInRelic(d)
    d.test.assertTrue(
        d.call(d.player, "getBoolProperty", "CAN_BREW_GREATER_POTIONS"),
        "The actual relic hand-in must unlock greater brewing before any missing-ingredient witness",
    )
    for recipe_id in GREATER_RECIPES:
        sellForMissingIngredient(d, recipe_id, protected_items=protected_items)
        recipeAttempt(
            d,
            "alchemyTable1",
            recipe_id,
            missingIngredientsBranch(recipe_id),
            outcome="missingIngredients",
        )


CASES = (
    RouteCase(
        "nouraajd_unlocked_recipe_rejections",
        "nouraajd",
        ("nouraajd",),
        tuple(missingIngredientsBranch(recipe_id) for recipe_id in GREATER_RECIPES),
        unlockedMissingRecipes,
        campaign="fallOfNouraajd",
        sources=SOURCES
        + ("res/plugins/crafting.py", "res/config/crafting.json", "res/game.py", "res/plugins/object.py"),
        duration_seconds=1200.0,
    ),
)
