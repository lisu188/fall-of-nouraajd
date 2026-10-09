# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite authored purchases that preserve every ingredient before a gold refusal."""

from collections import Counter
from functools import partial
from itertools import product

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_routes_crafting import recipeAttempt, recipeDefinitions
from tests.gameplay_routes_callback_markets import callbackContext, requestedMarket
from tests.gameplay_routes_ninemarches import recruit as recruitNine, start as startNine, walk as walkNine
from tests.gameplay_routes_nouraajd import (
    SOURCES as NOURAAJD_SOURCES,
    letter,
    meetVictor,
    prepareRolf,
    relic,
    handInRelic,
    raceAid,
    victorCountdownCheckpoint,
    victorRoute,
)
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


def assertRecipeInventoryPreserved(d, expected, stage):
    """Keep the exact preservation guard; gather bounded read-only context only on failure."""
    inventory = d.call(d.player, "getItems")
    missing = sorted(set(expected) - {item["__handle__"] for item in inventory})
    if not missing:
        return
    diagnostic = {
        "stage": str(stage)[:96],
        "map": d.map_name,
        "missingCount": len(missing),
        "missingOmitted": max(0, len(missing) - 12),
        "inventoryCount": len(inventory),
        "inventoryOmitted": max(0, len(inventory) - 12),
    }

    def describe(item):
        return {
            "identity": item["__handle__"],
            "name": str(d.call(item, "getName"))[:96],
            "type": str(d.call(item, "getTypeId"))[:96],
        }

    try:
        # Native handles retain the removed objects, so their actual names and
        # types remain available without restoring or re-adding any identity.
        diagnostic["missing"] = [describe({"__handle__": identity}) for identity in missing[:12]]
        diagnostic["currentInventory"] = [describe(item) for item in inventory[:12]]
        diagnostic["coords"] = d.coords()
        diagnostic["hp"] = d.call(d.player, "getHp")
        diagnostic["hpMax"] = d.call(d.player, "getHpMax")
        diagnostic["mana"] = d.call(d.player, "getMana")
        diagnostic["manaMax"] = d.call(d.player, "getManaMax")
        diagnostic["gold"] = d.gold()
        diagnostic["turn"] = d.call(d.game_map, "getTurn")
        actors = [
            actor
            for actor in d.call(d.game_map, "getObjects")
            if actor["__handle__"] != d.player["__handle__"]
            and (
                actor.get("__type__") in {"CCreature", "CPlayer"}
                or any(method["name"] == "isAlive" for method in actor.get("pythonMethods", ()))
            )
        ]
        diagnostic["remainingActors"] = [
            {**describe(actor), "alive": d.call(actor, "isAlive"), "coords": d.coords(actor)} for actor in actors[:8]
        ]
        diagnostic["actorsOmitted"] = max(0, len(actors) - 8)
    except Exception as error:
        diagnostic["diagnosticError"] = str(error)[:240]
    d.record({"recipeInventoryFailure": diagnostic})
    d.test.fail(f"Recipe inventory preservation failed: {diagnostic}")


def finitePortalGoldPlan(gold, loot_quotes, mana_price, scroll_price, lesser_quotes, portal_quote, life_quote, fee=35):
    """Plan once from finite observed quotes; each original identity can be sold at most once."""
    if not 0 < fee <= 100 or len(loot_quotes) > 128 or len(lesser_quotes) != 4:
        raise ValueError("Unexpected finite portal recipe economy")
    all_ids = [identity for identity, _price in loot_quotes]
    all_ids += [identity for identity, _sell, _buy in lesser_quotes]
    all_ids += [portal_quote[0], life_quote[0]]
    if len(set(all_ids)) != len(all_ids) or gold < 0 or min(mana_price, scroll_price) <= 0:
        raise ValueError("Distinct actual identities and positive required quotes are necessary")
    for _identity, sell, buy in (*lesser_quotes, portal_quote, life_quote):
        if not 0 < buy <= min(5000, sell) or sell > 100000:
            raise ValueError("The actual merchant spread must be positive and bounded by its price")
    if any(not 0 < price <= 5000 for _identity, price in loot_quotes):
        raise ValueError("Only actual positively quoted earned loot may fund this plan")
    maximum = mana_price + scroll_price + life_quote[1] + sum(sell for _identity, sell, _buy in lesser_quotes)
    maximum += portal_quote[1] - portal_quote[2] + fee - 1 - gold
    sums = {0: ()}
    for identity, quote in sorted(loot_quotes):
        for total, identities in tuple(sums.items()):
            new_total = total + quote
            if new_total > maximum:
                continue
            selected = (*identities, identity)
            previous = sums.get(new_total)
            if previous is None or (len(selected), selected) < (len(previous), previous):
                sums[new_total] = selected
    plans = []
    for life_mode, *lesser_modes in product(range(3), repeat=5):
        life_cost = (0, life_quote[1], life_quote[1] - life_quote[2])[life_mode]
        costs = [(0, sell, sell - buy)[mode] for mode, (_identity, sell, buy) in zip(lesser_modes, lesser_quotes)]
        for portal_cycle in (False, True):
            portal_cost = portal_quote[1] - portal_quote[2] if portal_cycle else 0
            expense = mana_price + scroll_price + life_cost + sum(costs) + portal_cost
            for remaining in range(fee):
                selected = sums.get(expense + remaining - gold)
                if selected is None:
                    continue
                available = gold + sum(dict(loot_quotes)[identity] for identity in selected)
                if life_mode and available < life_quote[1]:
                    continue
                # Callback trades must finish before any permanent-market movement.
                if available - life_cost < mana_price:
                    continue
                available -= life_cost + mana_price
                actions = []
                if portal_cycle:
                    available += portal_quote[2]
                    actions.append(("sale", portal_quote[0], portal_quote[2]))
                spending = sorted(zip(lesser_modes, lesser_quotes), key=lambda entry: (entry[0] != 2, entry[1][0]))
                for mode, (identity, sell, buy) in spending:
                    if not mode:
                        continue
                    if available < sell:
                        break
                    available -= sell
                    actions.append(("purchase", identity, sell))
                    if mode == 2:
                        available += buy
                        actions.append(("sale", identity, buy))
                else:
                    if portal_cycle:
                        if available < portal_quote[1]:
                            continue
                        available -= portal_quote[1]
                        actions.append(("purchase", portal_quote[0], portal_quote[1]))
                    if available < scroll_price:
                        continue
                    available -= scroll_price
                    if available != remaining:
                        continue
                    plans.append(
                        {
                            "loot": selected,
                            "lifeMode": life_mode,
                            "actions": tuple(actions),
                            "remaining": remaining,
                            "expense": expense,
                        }
                    )
    if not plans:
        return None
    return min(
        plans,
        key=lambda plan: (
            len(plan["loot"]),
            bool(plan["lifeMode"]),
            len(plan["actions"]) + plan["lifeMode"],
            plan["expense"],
            plan["loot"],
        ),
    )


def finiteGreaterLifeGoldPlan(
    gold, loot_quotes, life_quote, lesser_quotes, optional_quotes, portal_quote, *, required_sales=()
):
    """Plan the actual finite two-Life itinerary once, before any owned identity is sold."""
    quotes = (life_quote, *lesser_quotes, *optional_quotes, portal_quote)
    owned_quotes = (*loot_quotes, *required_sales)
    identities = [identity for identity, *_ in (*owned_quotes, *quotes)]
    if (
        type(gold) is not int
        or gold < 0
        or len(owned_quotes) > 128
        or len(lesser_quotes) != 2
        or len(optional_quotes) != 3
    ):
        raise ValueError("The finite greater-life economy requires bounded actual quotes")
    if len(set(identities)) != len(identities) or any(
        not isinstance(identity, str) or not identity for identity in identities
    ):
        raise ValueError("Every observed market/owned identity must be distinct")
    for _identity, sell, buy in quotes:
        if type(sell) is not int or type(buy) is not int or not 0 < buy <= min(5000, sell) or sell > 100000:
            raise ValueError("Only positive bounded native merchant quotes may fund the itinerary")
    if any(type(price) is not int or not 0 < price <= 5000 for _identity, price in owned_quotes):
        raise ValueError("Only bounded positively quoted earned loot may be sold")
    recipe = recipeDefinitions()
    brew_fee, greater_fee = recipe["brew_life_potion"]["gold"], recipe["blend_greater_life_potion"]["gold"]
    mandatory = life_quote[1] + sum(sell for _identity, sell, _buy in lesser_quotes) + brew_fee
    maximum = (
        mandatory + sum(sell for _identity, sell, _buy in optional_quotes) + portal_quote[1] + greater_fee - 1 - gold
    )
    required_ids = tuple(sorted(identity for identity, _price in required_sales))
    sums = {sum(price for _identity, price in required_sales): required_ids}
    for identity, price in sorted(loot_quotes):
        for total, selected in tuple(sums.items()):
            new_total = total + price
            if new_total > maximum:
                continue
            candidate = (*selected, identity)
            previous = sums.get(new_total)
            if previous is None or (len(candidate), candidate) < (len(previous), previous):
                sums[new_total] = candidate
    plans = []
    for portal_mode, *modes in product(range(3), repeat=4):
        if modes[0] == 1:
            # A retained third lesser would make the native predicate choose an
            # unspecified pair instead of the two captured original inputs.
            continue
        optional_cost = sum((0, sell, sell - buy)[mode] for mode, (_identity, sell, buy) in zip(modes, optional_quotes))
        portal_cost = (0, -portal_quote[2], portal_quote[1] - portal_quote[2])[portal_mode]
        expense = mandatory + optional_cost + portal_cost
        for remaining in range(greater_fee):
            selected = sums.get(expense + remaining - gold)
            if selected is None:
                continue
            available = gold + sum(dict(owned_quotes)[identity] for identity in selected)
            callback_actions = []
            if portal_mode:
                available += portal_quote[2]
                callback_actions.append(("sale", portal_quote[0], portal_quote[2]))
            if available < life_quote[1]:
                continue
            available -= life_quote[1]
            callback_actions.append(("purchase", life_quote[0], life_quote[1]))
            if portal_mode == 2:
                if available < portal_quote[1]:
                    continue
                available -= portal_quote[1]
                callback_actions.append(("purchase", portal_quote[0], portal_quote[1]))
            actions = []
            spending = sorted(zip(modes, optional_quotes), key=lambda entry: (entry[0] != 2, -entry[1][1], entry[1][0]))
            for mode, (identity, sell, buy) in spending:
                if not mode:
                    continue
                if available < sell:
                    break
                available -= sell
                actions.append(("purchase", identity, sell))
                if mode == 2:
                    available += buy
                    actions.append(("sale", identity, buy))
            else:
                for identity, sell, _buy in lesser_quotes:
                    if available < sell:
                        break
                    available -= sell
                    actions.append(("purchase", identity, sell))
                else:
                    if available - brew_fee == remaining:
                        plans.append(
                            {
                                "loot": selected,
                                "portalMode": portal_mode,
                                "callbackActions": tuple(callback_actions),
                                "actions": tuple(actions),
                                "remaining": remaining,
                                "expense": expense,
                            }
                        )
    if not plans:
        return None
    return min(
        plans,
        key=lambda plan: (
            len(plan["loot"]),
            bool(plan["portalMode"]),
            len(plan["actions"]),
            plan["expense"],
            plan["loot"],
        ),
    )


def sellInCurrentMarket(d, market, item, expected_price):
    identity = item["__handle__"]
    gold, stock, owned = d.gold(), stockIdentities(d, market), ownedIdentities(d)
    d.test.assertIn(identity, owned)
    d.test.assertNotIn(identity, stock)
    d.test.assertFalse(d.call(item, "hasTag", "quest"))
    d.test.assertEqual(expected_price, d.call(market, "getBuyCost", item))
    d.call(market, "buyItem", d.player, item)
    d.test.assertEqual(gold + expected_price, d.gold())
    d.test.assertEqual(stock | {identity}, stockIdentities(d, market))
    d.test.assertEqual(owned - {identity}, ownedIdentities(d))
    d.record({"recipeGoldSale": identity, "price": expected_price, "goldAfter": d.gold()})


def nourPortalGoldRefusal(d):
    d.test.assertEqual("humanRace", d.race_id)
    raceAid(d)
    d.test.assertEqual(20, d.gold())
    starting_items, starting_equipment = namedInventory(d), namedEquipment(d)
    prepareRolf(d)
    d.hunt("finishOriginalMainQuest")
    d.test.assertIn("mainQuest", d.questNames(completed=True))
    d.test.assertEqual(220, d.gold())
    meetVictor(d, "deescalated", False)
    victorCountdownCheckpoint(d, "portal-gold-victor-active", credit=True)
    d.check(
        "nouraajd.victor.approach.deescalated",
        d.call(d.player, "getStringProperty", "campaign_var_nouraajdVictorConfrontation") == "deescalated",
    )
    d.check("nouraajd.victor.entry.records", d.object("cultLeaderQuest", required=False) is not None)
    d.fight("cultLeaderQuest")
    d.test.assertEqual(720, d.gold())
    d.check("nouraajd.victor.rescued", d.string("quest_state_victor") == "good_end" and d.flag("VICTOR_REWARD_GRANTED"))
    d.call(d.player, "checkQuests")
    d.test.assertIn("victorQuest", d.questNames(completed=True))
    context = callbackContext(d)
    handler, callback_market = requestedMarket(d, "victorMarket")
    callback_stock = {d.call(item, "getTypeId"): item for item in d.call(callback_market, "getItems")}
    d.test.assertEqual({"LifePotion", "ManaPotion"}, set(callback_stock))
    market = d.call(d.object("market1"), "getObjectProperty", "market")
    original_stock = d.call(market, "getItems")
    d.test.assertEqual(
        Counter({"DaggerOfVileHeart": 1, "LesserLifePotion": 3, "LesserManaPotion": 1, "Scroll": 1}),
        Counter(d.call(item, "getTypeId") for item in original_stock),
    )
    lesser = sorted(
        [item for item in original_stock if d.call(item, "getTypeId") in {"LesserLifePotion", "LesserManaPotion"}],
        key=lambda item: d.call(item, "getName"),
    )
    scroll = next(item for item in original_stock if d.call(item, "getTypeId") == "Scroll")
    inventory = d.call(d.player, "getItems")
    d.test.assertTrue(starting_items.items() <= namedInventory(d).items())
    d.test.assertEqual(starting_equipment, namedEquipment(d))
    portals = [item for item in inventory if d.call(item, "getTypeId") == "TownPortalScroll"]
    d.test.assertEqual(1, len(portals), "Only the actual collected entry scroll may supply one buyback")
    portal = portals[0]
    equipped = {item["__handle__"] for item in d.call(d.player, "getEquipped").values() if item}
    protected_types = {entry["item"] for recipe in recipeDefinitions().values() for entry in recipe["inputs"]}
    protected_types.add("TownPortalScroll")
    protected_types.update({"holyRelic", "skullOfRolf", "letterFromRolf", "letterToBeren"})
    earned = {
        item["__handle__"]: item
        for item in inventory
        if d.call(item, "getName") not in starting_items
        and item["__handle__"] not in equipped
        and d.call(item, "getTypeId") not in protected_types
        and not d.call(item, "hasTag", "quest")
    }
    loot_quotes = [(identity, d.call(callback_market, "getBuyCost", item)) for identity, item in earned.items()]
    loot_quotes = tuple((identity, price) for identity, price in loot_quotes if price > 0)

    def quote(item, actual_market):
        return (
            item["__handle__"],
            d.call(actual_market, "getSellCost", item),
            d.call(actual_market, "getBuyCost", item),
        )

    mana, life = callback_stock["ManaPotion"], callback_stock["LifePotion"]
    mana_price, scroll_price = d.call(callback_market, "getSellCost", mana), d.call(market, "getSellCost", scroll)
    plan = finitePortalGoldPlan(
        d.gold(),
        loot_quotes,
        mana_price,
        scroll_price,
        tuple(quote(item, market) for item in lesser),
        quote(portal, market),
        quote(life, callback_market),
    )
    d.test.assertIsNotNone(plan, ("Actual finite earned quotes cannot fund a portal recipe gold refusal", loot_quotes))
    d.record({"recipeGoldPlan": plan, "actualEarnedQuotes": loot_quotes})
    protected = ownedIdentities(d) - set(earned)
    recovery = d.recoveryEnabled
    d.recoveryEnabled = False
    try:
        for identity in plan["loot"]:
            d.test.assertEqual(context, callbackContext(d))
            d.test.assertEqual(callback_market, d.call(handler, "getRequestedTradeMarket"))
            sellInCurrentMarket(d, callback_market, earned[identity], dict(loot_quotes)[identity])
        if plan["lifeMode"]:
            _identity, sell, buy = quote(life, callback_market)
            purchaseIdentity(d, callback_market, life, sell)
            if plan["lifeMode"] == 2:
                sellInCurrentMarket(d, callback_market, life, buy)
        purchaseIdentity(d, callback_market, mana, mana_price)
        after = (d.gold(), ownedIdentities(d), stockIdentities(d, callback_market))
        d.test.assertFalse(d.call(callback_market, "sellItem", d.player, mana))
        d.test.assertEqual(after, (d.gold(), ownedIdentities(d), stockIdentities(d, callback_market)))
        d.test.assertEqual(context, callbackContext(d))
        d.test.assertEqual(callback_market, d.call(handler, "getRequestedTradeMarket"))
        d.test.assertTrue(protected <= ownedIdentities(d))
        visitService(d, "market1", "trade_requested")
        handles = {item["__handle__"]: item for item in (*lesser, portal)}
        for action, identity, price in plan["actions"]:
            d.test.assertEqual(context[:3], callbackContext(d)[:3])
            if action == "sale":
                sellInCurrentMarket(d, market, handles[identity], price)
            else:
                purchaseIdentity(d, market, handles[identity], price)
        purchaseIdentity(d, market, scroll, scroll_price)
        d.test.assertEqual(plan["remaining"], d.gold())
        exact_inputs = {mana["__handle__"], scroll["__handle__"], portal["__handle__"]}
        d.test.assertTrue((protected | exact_inputs) <= ownedIdentities(d))
        d.test.assertEqual(starting_equipment, namedEquipment(d))
        letter(d)
        d.test.assertEqual(plan["remaining"], d.gold(), "The actual letter unlock cannot alter the funding proof")
        d.test.assertTrue(exact_inputs <= ownedIdentities(d))
        recipeAttempt(
            d,
            "scribeDesk1",
            "craft_town_portal_scroll",
            "nouraajd.crafting.craft_town_portal_scroll.insufficientGold",
            outcome="insufficientGold",
        )
        d.test.assertTrue((protected | exact_inputs) <= ownedIdentities(d))
        d.navigateTo("nouraajdTownHall")
        gold = d.gold()
        d.test.assertTrue(d.condition("townHallDialog", "victor_good_end"))
        d.saveAndReload("portal-gold-victor-rescued")
        d.check(
            "nouraajd.victor.endingPersisted", d.gold() == gold and d.condition("townHallDialog", "victor_good_end")
        )
        d.test.assertTrue(starting_items.items() <= namedInventory(d).items())
        d.test.assertEqual(starting_equipment, namedEquipment(d))
    finally:
        d.recoveryEnabled = recovery


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


def nourGreaterLifeGoldRefusal(d):
    d.test.assertEqual("humanRace", d.race_id)
    raceAid(d)
    starting_items, starting_equipment = namedInventory(d), namedEquipment(d)
    entry_scrolls = [item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == "TownPortalScroll"]
    d.test.assertEqual(1, len(entry_scrolls), "Capture the actual collected entry scroll before any combat loot")
    portal = entry_scrolls[0]
    prepareRolf(d)
    d.hunt("finishOriginalMainQuest")
    letter(d)
    relic(d)
    handInRelic(d)
    d.test.assertTrue(d.call(d.player, "getBoolProperty", "CAN_BREW_GREATER_POTIONS"))
    meetVictor(d, "deescalated", False)
    gold = d.gold()
    d.fight("cultLeaderQuest")
    d.call(d.player, "checkQuests")
    d.test.assertEqual("good_end", d.string("quest_state_victor"))
    d.test.assertTrue(d.flag("VICTOR_REWARD_GRANTED"))
    d.test.assertEqual(gold + 500, d.gold())
    d.test.assertIn("victorQuest", d.questNames(completed=True))
    context = callbackContext(d)
    handler, callback_market = requestedMarket(d, "victorMarket")
    callback_stock = d.call(callback_market, "getItems")
    lives = [item for item in callback_stock if d.call(item, "getTypeId") == "LifePotion"]
    d.test.assertEqual(1, len(lives), "Only Victor's actual finite LifePotion may supply this recipe")
    life = lives[0]
    market = d.call(d.object("market1"), "getObjectProperty", "market")
    stock = d.call(market, "getItems")
    lessers = sorted(
        [item for item in stock if d.call(item, "getTypeId") == "LesserLifePotion"],
        key=lambda item: d.call(item, "getName"),
    )
    d.test.assertEqual(3, len(lessers), "The original three LesserLife identities must still be in stock")
    optional = [lessers[2]]
    for type_id in ("LesserManaPotion", "Scroll"):
        matching = [item for item in stock if d.call(item, "getTypeId") == type_id]
        d.test.assertEqual(1, len(matching), "The spending plan requires exact finite original stock")
        optional.append(matching[0])
    inventory = d.call(d.player, "getItems")
    d.test.assertIn(portal["__handle__"], ownedIdentities(d))
    d.test.assertTrue(starting_items.items() <= namedInventory(d).items())
    d.test.assertEqual(starting_equipment, namedEquipment(d))
    protected_types = {entry["item"] for recipe in recipeDefinitions().values() for entry in recipe["inputs"]}
    protected_types.update({"TownPortalScroll", "letterFromRolf", "letterToBeren", "skullOfRolf", "holyRelic"})
    equipped = {item["__handle__"] for item in d.call(d.player, "getEquipped").values() if item}
    earned = {
        item["__handle__"]: item
        for item in inventory
        if d.call(item, "getName") not in starting_items
        and item["__handle__"] not in equipped
        and d.call(item, "getTypeId") not in protected_types
        and not d.call(item, "hasTag", "quest")
    }
    loot_quotes = tuple(
        (identity, price)
        for identity, item in earned.items()
        if (price := d.call(callback_market, "getBuyCost", item)) > 0
    )
    extra_lessers = [item for item in inventory if d.call(item, "getTypeId") == "LesserLifePotion"]
    for item in extra_lessers:
        d.test.assertNotIn(d.call(item, "getName"), starting_items, "A starting reagent cannot be sold for this proof")
        d.test.assertNotIn(item["__handle__"], equipped)
        d.test.assertFalse(d.call(item, "hasTag", "quest"))
    required_sales = tuple((item["__handle__"], d.call(callback_market, "getBuyCost", item)) for item in extra_lessers)
    sale_items = {**earned, **{item["__handle__"]: item for item in extra_lessers}}

    def quote(item, actual_market):
        return item["__handle__"], d.call(actual_market, "getSellCost", item), d.call(actual_market, "getBuyCost", item)

    plan = finiteGreaterLifeGoldPlan(
        d.gold(),
        loot_quotes,
        quote(life, callback_market),
        tuple(quote(item, market) for item in lessers[:2]),
        tuple(quote(item, market) for item in optional),
        quote(portal, callback_market),
        required_sales=required_sales,
    )
    d.test.assertIsNotNone(plan, ("Actual finite quotes cannot fund greater-life gold refusal", loot_quotes))
    d.record(
        {"greaterLifeGoldPlan": plan, "actualEarnedQuotes": loot_quotes, "actualExtraReagentQuotes": required_sales}
    )
    protected = ownedIdentities(d) - set(plan["loot"])
    if plan["portalMode"] == 1:
        protected.remove(portal["__handle__"])
    handles = {item["__handle__"]: item for item in (life, portal, *lessers, *optional)}
    recovery = d.recoveryEnabled
    d.recoveryEnabled = False
    try:
        for identity in plan["loot"]:
            d.test.assertEqual(context, callbackContext(d))
            d.test.assertEqual(callback_market, d.call(handler, "getRequestedTradeMarket"))
            sellInCurrentMarket(
                d, callback_market, sale_items[identity], dict((*loot_quotes, *required_sales))[identity]
            )
        for action, identity, price in plan["callbackActions"]:
            d.test.assertEqual(context, callbackContext(d))
            d.test.assertEqual(callback_market, d.call(handler, "getRequestedTradeMarket"))
            operation = sellInCurrentMarket if action == "sale" else purchaseIdentity
            operation(d, callback_market, handles[identity], price)
        assertRecipeInventoryPreserved(d, protected, "greater-life.after-callback-transactions")
        visitService(d, "market1", "trade_requested")
        assertRecipeInventoryPreserved(d, protected, "greater-life.after-market-entry")
        for action, identity, price in plan["actions"]:
            d.test.assertEqual(context[:3], callbackContext(d)[:3])
            operation = sellInCurrentMarket if action == "sale" else purchaseIdentity
            operation(d, market, handles[identity], price)
        lesser_ids = {item["__handle__"] for item in lessers[:2]}
        before = ownedIdentities(d)
        d.test.assertTrue(lesser_ids | {life["__handle__"]} <= before)
        d.test.assertEqual(
            lesser_ids,
            {
                item["__handle__"]
                for item in d.call(d.player, "getItems")
                if d.call(item, "getTypeId") == "LesserLifePotion"
            },
            "The guaranteed brew must consume exactly the two original authored LesserLife identities",
        )
        recipeAttempt(
            d, "alchemyTable1", "brew_life_potion", "nouraajd.crafting.brew_life_potion.success", outcome="success"
        )
        after = ownedIdentities(d)
        created = after - before
        d.test.assertEqual(1, len(created))
        crafted = next(item for item in d.call(d.player, "getItems") if item["__handle__"] in created)
        d.test.assertEqual("LifePotion", d.call(crafted, "getTypeId"))
        d.test.assertEqual(before - lesser_ids, after - created)
        life_ids = {life["__handle__"], crafted["__handle__"]}
        d.test.assertEqual(2, len(life_ids))
        d.test.assertTrue((protected | life_ids) <= after)
        d.test.assertEqual(plan["remaining"], d.gold())
        d.test.assertEqual(starting_equipment, namedEquipment(d))
        recipeAttempt(
            d,
            "alchemyTable1",
            "blend_greater_life_potion",
            "nouraajd.crafting.blend_greater_life_potion.insufficientGold",
            outcome="insufficientGold",
        )
        d.test.assertEqual(after, ownedIdentities(d))
        d.test.assertTrue(life_ids <= ownedIdentities(d))
    finally:
        d.recoveryEnabled = recovery


CASES = (
    RouteCase(
        id="nouraajd_recipe_gold_greater_life",
        group="nouraajd",
        maps=("nouraajd",),
        branches=(
            "nouraajd.aid.humanRace.claimed",
            "nouraajd.aid.humanRace.persisted",
            "nouraajd.crafting.brew_life_potion.success",
            "nouraajd.crafting.blend_greater_life_potion.insufficientGold",
        ),
        run=nourGreaterLifeGoldRefusal,
        campaign="fallOfNouraajd",
        sources=tuple(dict.fromkeys((*NOURAAJD_SOURCES, *SOURCES[4:]))),
        duration_seconds=1200.0,
    ),
    RouteCase(
        id="nouraajd_recipe_gold_scroll",
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
            "nouraajd.crafting.craft_town_portal_scroll.insufficientGold",
        ),
        run=nourPortalGoldRefusal,
        campaign="fallOfNouraajd",
        sources=tuple(dict.fromkeys((*NOURAAJD_SOURCES, *SOURCES[4:]))),
        duration_seconds=1200.0,
    ),
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
