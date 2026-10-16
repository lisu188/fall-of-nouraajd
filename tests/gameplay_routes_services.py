# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact shared-service witnesses; every attempt has a declared expected outcome."""

from tests.gameplay_branch_driver import readNewNativeTrace


def ownedIdentities(d):
    return {item["__handle__"] for item in d.call(d.player, "getItems")}


def nativeCheckpoint(d):
    d.test.assertIsNotNone(d.trace_path, "A service requires its actual native callback trace")
    d.assertNativeCombatOutcomes()
    return d._combat_trace_seq, dict(d._combat_trace_positions)


def nativeEventsSince(d, checkpoint, event):
    seq, positions = checkpoint
    records = readNewNativeTrace(d.trace_path, positions, after_seq=seq)
    return tuple(record for record in records if record.get("event") == event and record.get("map") == d.map_name)


def visitService(d, name, event, *, navigate=None):
    # Checkpoint immediately before entering, so a long approach cannot rotate
    # away the evidence for the actual service callback.
    navigate = navigate or d.navigateTo
    navigate(name, adjacent=True)
    checkpoint = nativeCheckpoint(d)
    if d.coords() == d.coords(d.object(name)):
        d.revisit(name)
    else:
        navigate(name)
    d.test.assertEqual(d.coords(d.object(name)), d.coords())
    requests = nativeEventsSince(d, checkpoint, event)
    d.test.assertTrue(requests, ("Authored service callback was not observed", name, event))
    return requests


def marketAttempt(d, market_name, branch, *, purchased, earned_items=(), navigate=None):
    """Assert one native refusal or purchase, funding only from explicitly earned inventory."""
    requests = visitService(d, market_name, "trade_requested", navigate=navigate)
    market = d.call(d.object(market_name), "getObjectProperty", "market")
    d.test.assertIsNotNone(market)
    d.test.assertEqual(d.call(market, "getName"), requests[-1]["market"]["name"])
    stock = d.call(market, "getItems")
    d.test.assertTrue(stock, "The authored finite stock must exist")
    item = min(
        stock,
        key=lambda value: (
            d.call(market, "getSellCost", value),
            d.call(value, "getTypeId"),
            d.call(value, "getName"),
        ),
    )
    price = d.call(market, "getSellCost", item)
    d.test.assertGreater(price, 0)
    sold = []
    if purchased:
        # The finite initial list bounds fundraising. A route cannot loop on
        # manufactured loot, sell an unowned item or silently spend its loadout.
        candidates = [value for value in d.call(d.player, "getItems") if value["__handle__"] in earned_items]
        candidates.sort(key=lambda value: (-d.call(market, "getBuyCost", value), d.call(value, "getName")))
        for candidate in candidates:
            if d.gold() >= price:
                break
            if d.call(market, "getBuyCost", candidate) <= 0 or d.call(candidate, "hasTag", "quest"):
                continue
            d.sellAt(market_name, candidate)
            sold.append(candidate["__handle__"])
        d.test.assertGreaterEqual(d.gold(), price, "Real earned funds/loot did not fund the declared purchase")
    else:
        d.test.assertLess(d.gold(), price, "An affordability refusal requires actually insufficient gold")
    gold_before = d.gold()
    stock_before = {value["__handle__"] for value in d.call(market, "getItems")}
    owned_before = ownedIdentities(d)
    item_identity = item["__handle__"]
    d.test.assertIn(item_identity, stock_before)
    d.test.assertNotIn(item_identity, owned_before)
    accepted = d.call(market, "sellItem", d.player, item)
    stock_after = {value["__handle__"] for value in d.call(market, "getItems")}
    owned_after = ownedIdentities(d)
    d.check(
        branch,
        accepted is purchased
        and d.gold() == gold_before - (price if purchased else 0)
        and stock_after == stock_before - ({item_identity} if purchased else set())
        and owned_after == owned_before | ({item_identity} if purchased else set()),
        price=price,
        item=item_identity,
        itemType=d.call(item, "getTypeId"),
        goldBefore=gold_before,
        goldAfter=d.gold(),
        soldEarnedItems=sold,
        callbackSeq=requests[-1]["seq"],
    )
    # A sold-out identity cannot be bought again. Refusal also must not consume
    # the finite stock or charge a partial payment.
    d.test.assertFalse(d.call(market, "sellItem", d.player, item))
    d.test.assertEqual(stock_after, {value["__handle__"] for value in d.call(market, "getItems")})
    d.test.assertEqual(owned_after, ownedIdentities(d))
    d.test.assertEqual(gold_before - (price if purchased else 0), d.gold())
    return item if purchased else None


def collectedScrollRetreat(d, branch, name="townPortalScroll", *, navigate=None):
    """Collect an authored world item and consume that exact identity to return to the entry."""
    navigate = navigate or d.navigateTo
    navigate(name, adjacent=True)
    actor = d.object(name)
    d.test.assertEqual("TownPortalScroll", d.call(actor, "getTypeId"))
    identity = actor["__handle__"]
    before = ownedIdentities(d)
    d.test.assertNotIn(identity, before)
    navigate(name)
    d.test.assertIsNone(d.object(name, required=False))
    d.test.assertEqual(before | {identity}, ownedIdentities(d))
    return useOwnedScroll(d, actor, branch)


def useOwnedScroll(d, item, branch):
    d.test.assertEqual("TownPortalScroll", d.call(item, "getTypeId"))
    identity = item["__handle__"]
    before = ownedIdentities(d)
    d.test.assertIn(identity, before)
    entry = tuple(d.call(d.game_map, method) for method in ("getEntryX", "getEntryY", "getEntryZ"))
    d.test.assertNotEqual(entry, d.coords(), "A retreat witness must begin away from the destination")
    continuity = (d.game_map["__handle__"], d.player["__handle__"])
    origin = d.coords()
    d.call(d.player, "useItem", item)
    d.pump()
    d.assertSurvival()
    d.check(
        branch,
        continuity == (d.game_map["__handle__"], d.player["__handle__"])
        and d.coords() == entry
        and ownedIdentities(d) == before - {identity},
        item=identity,
        origin=origin,
        destination=entry,
    )


def signRewardState(d):
    return {
        "gold": d.gold(),
        "items": ownedIdentities(d),
        "activeQuests": tuple(sorted(d.questNames())),
        "completedQuests": tuple(sorted(d.questNames(completed=True))),
        "reputation": d.call(d.player, "getNumericProperty", "reputation"),
    }


def readSignpost(d, name, prefix=None, *, navigate=None):
    prefix = prefix or d.map_name
    navigate = navigate or d.navigateTo
    navigate(name, adjacent=True)
    sign = d.object(name)
    body = d.call(sign, "getStringProperty", "text")
    d.test.assertTrue(body)
    before = signRewardState(d)
    for suffix in ("read", "repeat"):
        requests = visitService(d, name, "reader_requested", navigate=navigate)
        matching = [request for request in requests if request.get("title") == "Signpost"]
        d.test.assertEqual(1, len(matching), "The actual authored sign must request its text exactly once per entry")
        request = matching[0]
        d.check(
            f"{prefix}.signpost.{suffix}",
            request.get("body") == body
            and request.get("bodyLength") == len(body.encode("utf-8"))
            and request.get("headless") is True
            and signRewardState(d) == before,
            sign=name,
            callbackSeq=request["seq"],
            text=body,
        )
