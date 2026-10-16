# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trade only against the exact actual headless callback request in its native context."""

from tests.gameplay_routes_services import ownedIdentities


def callbackContext(d):
    return (d.game_map["__handle__"], d.player["__handle__"], d.map_name, d.coords(), d.call(d.game_map, "getTurn"))


def requestedMarket(d, type_id):
    handler = d.call(d.game, "getGuiHandler")
    market = d.call(handler, "getRequestedTradeMarket")
    d.test.assertIsNotNone(market, "The authored callback must expose its actual finite market")
    d.test.assertEqual(type_id, d.call(market, "getTypeId"))
    requests = d.tradeRequests()
    d.test.assertTrue(requests, "A retained market without an actual native trade request is not evidence")
    actual = requests[-1]["market"]
    d.test.assertEqual(type_id, actual["typeId"])
    d.test.assertEqual(d.call(market, "getName"), actual["name"])
    d.test.assertEqual(d.map_name, requests[-1]["map"])
    return handler, market


def purchaseCallbackItem(d, market_type, item_type, earned_items, *, protected_types=()):
    """Fund one real purchase from bounded earned unequipped loot; never recreate stock."""
    context = callbackContext(d)
    handler, market = requestedMarket(d, market_type)
    stock = d.call(market, "getItems")
    matching = [item for item in stock if d.call(item, "getTypeId") == item_type]
    d.test.assertEqual(1, len(matching), "The exact one-time authored item must still be in original stock")
    selected = matching[0]
    price = d.call(market, "getSellCost", selected)
    d.test.assertGreater(price, 0)
    equipped = {item["__handle__"] for item in d.call(d.player, "getEquipped").values() if item}
    candidates = [
        item
        for item in d.call(d.player, "getItems")
        if item["__handle__"] in earned_items
        and item["__handle__"] not in equipped
        and d.call(item, "getTypeId") not in protected_types
        and not d.call(item, "hasTag", "quest")
    ]
    d.test.assertLessEqual(len(candidates), 128, "Only finite already-earned loot may fund a callback purchase")
    candidates.sort(key=lambda item: (-d.call(market, "getBuyCost", item), d.call(item, "getName")))
    for item in candidates:
        if d.gold() >= price:
            break
        d.test.assertEqual(context, callbackContext(d))
        d.test.assertEqual(market, d.call(handler, "getRequestedTradeMarket"))
        payment = d.call(market, "getBuyCost", item)
        if payment <= 0:
            continue
        owned, gold = ownedIdentities(d), d.gold()
        stock_before = {entry["__handle__"] for entry in d.call(market, "getItems")}
        identity = item["__handle__"]
        d.call(market, "buyItem", d.player, item)
        d.test.assertEqual(gold + payment, d.gold())
        d.test.assertEqual(owned - {identity}, ownedIdentities(d))
        d.test.assertEqual(stock_before | {identity}, {entry["__handle__"] for entry in d.call(market, "getItems")})
    d.test.assertGreaterEqual(d.gold(), price, "Actual earned funds and loot cannot afford the one-time callback item")
    d.test.assertEqual(context, callbackContext(d))
    d.test.assertEqual(market, d.call(handler, "getRequestedTradeMarket"))
    owned, gold = ownedIdentities(d), d.gold()
    stock_before = {entry["__handle__"] for entry in d.call(market, "getItems")}
    identity = selected["__handle__"]
    d.test.assertTrue(d.call(market, "sellItem", d.player, selected))
    d.test.assertEqual(gold - price, d.gold())
    d.test.assertEqual(owned | {identity}, ownedIdentities(d))
    d.test.assertEqual(stock_before - {identity}, {entry["__handle__"] for entry in d.call(market, "getItems")})
    d.test.assertEqual(market, d.call(handler, "getRequestedTradeMarket"))
    # A second purchase of that actual identity must fail without changing payment or stock.
    after = (d.gold(), ownedIdentities(d), {entry["__handle__"] for entry in d.call(market, "getItems")})
    d.test.assertFalse(d.call(market, "sellItem", d.player, selected))
    d.test.assertEqual(
        after, (d.gold(), ownedIdentities(d), {entry["__handle__"] for entry in d.call(market, "getItems")})
    )
    d.test.assertEqual(context, callbackContext(d))
    d.record(
        {
            "actualCallbackPurchase": item_type,
            "market": market_type,
            "price": price,
            "identity": identity,
            "nativeRequest": d.tradeRequests()[-1],
        }
    )
    return selected
