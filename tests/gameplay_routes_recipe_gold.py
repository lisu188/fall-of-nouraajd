# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite authored purchases that preserve every ingredient before a gold refusal."""

from collections import Counter
from functools import partial

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_routes_crafting import recipeAttempt
from tests.gameplay_routes_ninemarches import recruit as recruitNine, start as startNine, walk as walkNine
from tests.gameplay_routes_nouraajd import SOURCES as NOURAAJD_SOURCES, prepareRolf, raceAid, victorRoute
from tests.gameplay_routes_services import ownedIdentities, visitService

NINE_STOCK_PRICES = {
    "Scroll": 200,
    "ManaPotion": 1600,
    "LifePotion": 800,
    "GreaterLifePotion": 1600,
    "LesserLifePotion": 400,
}
SOURCES = (
    "res/maps/ninemarches/script.py",
    "res/maps/ninemarches/config.json",
    "res/maps/ninemarches/map.json",
    "res/maps/ninemarches/dialog.json",
    "res/plugins/object.py",
    "res/plugins/crafting.py",
    "res/config/crafting.json",
    "res/config/potions.json",
    "res/config/items.json",
    "res/config/armors.json",
    "src/object/CMarket.cpp",
)


def stockIdentities(d, market):
    return {item["__handle__"] for item in d.call(market, "getItems")}


def purchaseIdentity(d, market, item, expected_price):
    """Buy one already observed finite identity through its actual active market."""
    identity = item["__handle__"]
    before_gold, before_stock, before_owned = d.gold(), stockIdentities(d, market), ownedIdentities(d)
    d.test.assertIn(identity, before_stock)
    d.test.assertNotIn(identity, before_owned)
    d.test.assertEqual(expected_price, d.call(market, "getSellCost", item))
    d.test.assertTrue(d.call(market, "sellItem", d.player, item))
    d.test.assertEqual(before_gold - expected_price, d.gold())
    d.test.assertEqual(before_stock - {identity}, stockIdentities(d, market))
    d.test.assertEqual(before_owned | {identity}, ownedIdentities(d))
    d.record({"recipeGoldPurchase": identity, "price": expected_price, "goldAfter": d.gold()})


def sellIdentity(d, market_name, market, item, expected_price):
    identity = item["__handle__"]
    before_gold, before_stock, before_owned = d.gold(), stockIdentities(d, market), ownedIdentities(d)
    d.test.assertNotIn(identity, before_stock)
    d.test.assertIn(identity, before_owned)
    d.test.assertFalse(d.call(item, "hasTag", "quest"))
    d.test.assertEqual(expected_price, d.call(market, "getBuyCost", item))
    d.sellAt(market_name, item)
    d.test.assertEqual(before_gold + expected_price, d.gold())
    d.test.assertEqual(before_stock | {identity}, stockIdentities(d, market))
    d.test.assertEqual(before_owned - {identity}, ownedIdentities(d))
    d.record({"recipeGoldSale": identity, "price": expected_price, "goldAfter": d.gold()})


def nineScrollGoldRefusal(d):
    startNine(d)
    starting_owned = ownedIdentities(d)
    starting_equipped = d.call(d.player, "getEquipped")
    navigate = partial(walkNine, d)
    walkNine(d, "learningStone")
    d.test.assertTrue(d.flag("CAN_CRAFT_SCROLLS"))
    d.test.assertEqual(120, d.gold())
    _actor, _dialog, gift_type = recruitNine(d, "halda")
    d.test.assertEqual("aegisOfHalda", gift_type)
    visitService(d, "gravewatchBarter", "trade_requested", navigate=navigate)
    market = d.call(d.object("gravewatchBarter"), "getObjectProperty", "market")
    original_stock = d.call(market, "getItems")
    d.test.assertEqual(Counter(NINE_STOCK_PRICES.keys()), Counter(d.call(item, "getTypeId") for item in original_stock))
    stock = {d.call(item, "getTypeId"): item for item in original_stock}
    gifts = [item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == gift_type]
    d.test.assertEqual(1, len(gifts))
    gift = gifts[0]
    d.test.assertNotIn(gift["__handle__"], starting_owned)
    d.test.assertNotIn(gift, starting_equipped.values())
    d.test.assertEqual(120, d.gold(), "Halda's real recruitment grants an item and reputation, not gold")
    sellIdentity(d, "gravewatchBarter", market, gift, 5000)
    d.test.assertEqual(5120, d.gold())
    scrolls = [
        item
        for item in d.call(d.player, "getItems")
        if d.call(item, "getTypeId") == "TownPortalScroll" and d.call(item, "getName") == d._marches_retreat_scroll_name
    ]
    d.test.assertEqual(1, len(scrolls), "Only the actual collected entry scroll may supply this buyback")
    portal = scrolls[0]
    recovery = d.recoveryEnabled
    d.recoveryEnabled = False
    try:
        for type_id, price in NINE_STOCK_PRICES.items():
            purchaseIdentity(d, market, stock[type_id], price)
        d.test.assertEqual({gift["__handle__"]}, stockIdentities(d, market))
        d.test.assertEqual(520, d.gold())
        protected = {stock[type_id]["__handle__"] for type_id in ("Scroll", "ManaPotion")}
        # Three distinct, once-only buybacks spend the actual 80% merchant spread.
        # The two recipe reagents never participate in a sale or another craft.
        for item, buyback, price, remaining in (
            (stock["LifePotion"], 640, 800, 360),
            (stock["GreaterLifePotion"], 1280, 1600, 40),
            (portal, 160, 200, 0),
        ):
            d.test.assertNotIn(item["__handle__"], protected)
            sellIdentity(d, "gravewatchBarter", market, item, buyback)
            purchaseIdentity(d, market, item, price)
            d.test.assertEqual(remaining, d.gold())
        d.test.assertLess(0, d.count("Scroll"))
        d.test.assertLess(0, d.count("ManaPotion"))
        d.test.assertTrue(protected <= ownedIdentities(d))
        d.test.assertTrue(starting_owned <= ownedIdentities(d))
        d.test.assertEqual(starting_equipped, d.call(d.player, "getEquipped"))
        recipeAttempt(
            d,
            "gravewatchScribe",
            "craft_town_portal_scroll",
            "ninemarches.crafting.craft_town_portal_scroll.insufficientGold",
            outcome="insufficientGold",
            navigate=navigate,
        )
    finally:
        d.recoveryEnabled = recovery


def namedInventory(d):
    return {d.call(item, "getName"): d.call(item, "getTypeId") for item in d.call(d.player, "getItems")}


def namedEquipment(d):
    return {
        slot: (d.call(item, "getName"), d.call(item, "getTypeId")) if item else None
        for slot, item in d.call(d.player, "getEquipped").items()
    }


def nourLifeGoldRefusal(d):
    d.test.assertEqual("humanRace", d.race_id)
    raceAid(d)
    d.test.assertEqual(20, d.gold())
    starting_items, starting_equipment = namedInventory(d), namedEquipment(d)
    prepareRolf(d)
    d.hunt("finishOriginalMainQuest")
    d.test.assertIn("mainQuest", d.questNames(completed=True))
    d.test.assertEqual(220, d.gold())
    victorRoute(d, "deescalated", direct=False, saved=True, start_new=False, ask_girl=True)
    d.test.assertEqual(720, d.gold())
    inventory = namedInventory(d)
    d.test.assertTrue(
        starting_items.items() <= inventory.items(), "Native reloads must preserve the original owned names/types"
    )
    d.test.assertEqual(starting_equipment, namedEquipment(d))
    portals = [item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == "TownPortalScroll"]
    d.test.assertEqual(1, len(portals), "Only the actual collected entry scroll may fund this independent case")
    portal = portals[0]
    visitService(d, "market1", "trade_requested")
    market = d.call(d.object("market1"), "getObjectProperty", "market")
    lessers = sorted(
        [item for item in d.call(market, "getItems") if d.call(item, "getTypeId") == "LesserLifePotion"],
        key=lambda item: d.call(item, "getName"),
    )
    d.test.assertEqual(3, len(lessers), "The three original authored lesser draughts must remain finite and unbought")
    before, equipment = ownedIdentities(d), d.call(d.player, "getEquipped")
    recovery = d.recoveryEnabled
    d.recoveryEnabled = False
    try:
        sellIdentity(d, "market1", market, portal, 160)
        d.test.assertEqual(880, d.gold())
        for ingredient in lessers[:2]:
            purchaseIdentity(d, market, ingredient, 400)
        d.test.assertEqual(80, d.gold())
        sellIdentity(d, "market1", market, lessers[0], 320)
        purchaseIdentity(d, market, lessers[0], 400)
        d.test.assertEqual(0, d.gold())
        ingredients = {item["__handle__"] for item in lessers[:2]}
        d.test.assertEqual((before - {portal["__handle__"]}) | ingredients, ownedIdentities(d))
        d.test.assertEqual(equipment, d.call(d.player, "getEquipped"))
        recipeAttempt(
            d,
            "alchemyTable1",
            "brew_life_potion",
            "nouraajd.crafting.brew_life_potion.insufficientGold",
            outcome="insufficientGold",
        )
        d.test.assertTrue(ingredients <= ownedIdentities(d))
        retained = {name: item_type for name, item_type in starting_items.items() if item_type != "TownPortalScroll"}
        d.test.assertTrue(retained.items() <= namedInventory(d).items())
        d.test.assertEqual(starting_equipment, namedEquipment(d))
    finally:
        d.recoveryEnabled = recovery


CASES = (
    RouteCase(
        id="nouraajd_recipe_gold_life",
        group="nouraajd",
        maps=("nouraajd",),
        branches=(
            "nouraajd.aid.humanRace.claimed",
            "nouraajd.aid.humanRace.persisted",
            "nouraajd.victor.approach.deescalated",
            "nouraajd.victor.entry.records",
            "nouraajd.victor.countdownPersisted",
            "nouraajd.victor.rescued",
            "nouraajd.victor.endingPersisted",
            "nouraajd.crafting.brew_life_potion.insufficientGold",
        ),
        run=nourLifeGoldRefusal,
        campaign="fallOfNouraajd",
        sources=tuple(dict.fromkeys((*NOURAAJD_SOURCES, *SOURCES[4:]))),
        duration_seconds=1200.0,
    ),
    RouteCase(
        id="ninemarches_recipe_gold_scroll",
        group="ninemarches",
        maps=("ninemarches",),
        branches=("ninemarches.crafting.craft_town_portal_scroll.insufficientGold",),
        run=nineScrollGoldRefusal,
        sources=SOURCES,
        duration_seconds=1200.0,
    ),
)
