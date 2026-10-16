# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact native potion receipts for ordinary owned-item consumption."""

from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def potionDefinitions():
    path = Path(__file__).resolve().parents[1] / "res/config/potions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def potionRestoration(before, maximum, power):
    return min(maximum, before + max(1, int((power * 20 / 100.0) * maximum)))


def potionUseWitness(record, *, player_name, map_name):
    """Return evidence only for an actual matching-player ordinary Life/Mana potion."""
    if record.get("event") != "item_used" or record.get("map") != map_name:
        return None
    actor = record.get("actor", {})
    if actor.get("isPlayer") is not True or actor.get("name") != player_name:
        return None
    item = record.get("item", {})
    definition = potionDefinitions().get(item.get("typeId"), {})
    class_id = definition.get("class")
    if class_id not in {"LifePotion", "ManaPotion"}:
        return None
    category = "life" if class_id == "LifePotion" else "mana"

    def require(condition, reason):
        if not condition:
            raise AssertionError(("Invalid native potion consumption", reason, record))

    require(item.get("type") == class_id, "The runtime potion class disagrees with the authored callback")
    name = item.get("name")
    require(isinstance(name, str) and bool(name), "The exact consumed identity is absent")
    require(record.get("itemNameLength") == len(name.encode("utf-8")), "The consumed identity was truncated")
    require(type(record.get("seq")) is int and record["seq"] > 0, "A native sequence is required")
    power = record.get("power")
    properties = definition["properties"]
    require(type(power) is int and power > 0 and power == properties["power"], "The authored potion power changed")
    require(properties.get("singleUse") is True and record.get("disposable") is True, "The potion is not disposable")
    require(record.get("restoresHp") is (category == "life"), "The HP restoration tag disagrees with its callback")
    require(record.get("restoresMana") is (category == "mana"), "The mana restoration tag disagrees with its callback")
    for key in (
        "hpBefore",
        "hpAfter",
        "hpMaxBefore",
        "hpMaxAfter",
        "manaBefore",
        "manaAfter",
        "manaMaxBefore",
        "manaMaxAfter",
        "inventoryBeforeCount",
        "inventoryAfterCount",
        "removedCount",
        "addedCount",
    ):
        require(type(record.get(key)) is int, "Missing or noninteger native field: " + key)
    require(record["hpMaxBefore"] == record["hpMaxAfter"] > 0, "Potion use changed maximum health")
    require(record["manaMaxBefore"] == record["manaMaxAfter"] > 0, "Potion use changed maximum mana")
    # Expired stat effects can lower derived caps without clamping stored HP/mana.
    # Ordinary callbacks leave the other resource untouched; the restored one must have a deficit below.
    require(record["hpBefore"] > 0, "A defeated player cannot earn a potion witness")
    require(record["manaBefore"] >= 0, "Invalid native mana before consumption")
    require(
        record.get("ownedBefore") is True and record.get("ownedAfter") is False, "The exact owned item was not consumed"
    )
    require(record["inventoryBeforeCount"] > 0, "The potion did not begin in the native inventory")
    require(
        record["inventoryAfterCount"] == record["inventoryBeforeCount"] - 1, "Consumption changed the wrong item count"
    )
    require(record["removedCount"] == 1 and record["addedCount"] == 0, "Consumption changed unrelated inventory")
    require(record.get("onlyUsedItemRemoved") is True, "The selected native identity was not the only removed item")
    require(record.get("equipmentUnchanged") is True, "Potion use changed equipment")
    key = "hp" if category == "life" else "mana"
    other = "mana" if category == "life" else "hp"
    require(record[key + "Before"] < record[key + "MaxBefore"], "No actual resource deficit preceded consumption")
    expected = potionRestoration(record[key + "Before"], record[key + "MaxBefore"], power)
    require(record[key + "After"] == expected, "Restoration disagrees with the exact capped percentage")
    require(record[other + "After"] == record[other + "Before"], "The ordinary potion changed the other resource")
    return category, {
        "item": name,
        "typeId": item["typeId"],
        "power": power,
        "callbackSeq": record["seq"],
        "resourceBefore": record[key + "Before"],
        "resourceAfter": record[key + "After"],
        "resourceMaximum": record[key + "MaxBefore"],
        "nativeItemUse": record,
    }


def observePotionConsumptions(d, records, *, player_name):
    """Called only after the shared reader commits its cursor, so checks cannot reread it."""
    for record in records:
        witness = potionUseWitness(record, player_name=player_name, map_name=d.map_name)
        if witness is None:
            continue
        category, evidence = witness
        branch = d.map_name + ".potion." + category + ".used"
        if branch in d.case.branches and branch not in d.branches:
            d.check(branch, True, **evidence)


def ownedPotions(d, category):
    class_id = "LifePotion" if category == "life" else "ManaPotion"
    return [
        item
        for item in d.call(d.player, "getItems")
        if potionDefinitions().get(d.call(item, "getTypeId"), {}).get("class") == class_id
    ]


def preparePotionStock(d, market_name, earned_items, *, categories=("life", "mana"), navigate=None):
    """Buy only finite authored stock, selling a bounded explicitly earned item list if needed."""
    from tests.gameplay_routes_services import ownedIdentities

    categories = tuple(
        category
        for category in categories
        if d.map_name + ".potion." + category + ".used" in d.case.branches
        and d.map_name + ".potion." + category + ".used" not in d.branches
    )
    if not categories:
        return
    (navigate or d.navigateTo)(market_name)
    market = d.call(d.object(market_name), "getObjectProperty", "market")
    d.test.assertIsNotNone(market)
    stock, selected = d.call(market, "getItems"), []
    for category in categories:
        if ownedPotions(d, category):
            continue
        class_id = "LifePotion" if category == "life" else "ManaPotion"
        candidates = [
            item for item in stock if potionDefinitions().get(d.call(item, "getTypeId"), {}).get("class") == class_id
        ]
        d.test.assertTrue(candidates, ("Finite authored potion stock is unavailable", market_name, category))
        selected.append(
            min(candidates, key=lambda item: (d.call(market, "getSellCost", item), d.call(item, "getName")))
        )
    required_gold = sum(d.call(market, "getSellCost", item) for item in selected)
    equipped = {item["__handle__"] for item in d.call(d.player, "getEquipped").values() if item}
    candidates = [
        item
        for item in d.call(d.player, "getItems")
        if item["__handle__"] in earned_items
        and item["__handle__"] not in equipped
        and not d.call(item, "hasTag", "quest")
        and potionDefinitions().get(d.call(item, "getTypeId"), {}).get("class") not in {"LifePotion", "ManaPotion"}
    ]
    d.test.assertLessEqual(len(candidates), 128, "Only existing finite earned loot may fund potion stock")
    candidates.sort(key=lambda item: (-d.call(market, "getBuyCost", item), d.call(item, "getName")))
    for item in candidates:
        if d.gold() >= required_gold:
            break
        if d.call(market, "getBuyCost", item) > 0:
            d.sellAt(market_name, item)
    d.test.assertGreaterEqual(
        d.gold(), required_gold, "Actual earned funds/loot did not fund the finite potion itinerary"
    )
    for item in selected:
        before, gold_before = ownedIdentities(d), d.gold()
        stock_before = {entry["__handle__"] for entry in d.call(market, "getItems")}
        price, identity = d.call(market, "getSellCost", item), item["__handle__"]
        d.test.assertGreater(price, 0)
        d.test.assertIn(identity, stock_before)
        d.test.assertTrue(d.call(market, "sellItem", d.player, item))
        d.test.assertEqual(gold_before - price, d.gold())
        d.test.assertEqual(before | {identity}, ownedIdentities(d))
        d.test.assertEqual(stock_before - {identity}, {entry["__handle__"] for entry in d.call(market, "getItems")})
    for category in categories:
        d.test.assertTrue(
            ownedPotions(d, category) or d.map_name + ".potion." + category + ".used" in d.branches,
            ("An actual owned potion or native consumption is required before the remaining fixed fights", category),
        )


def consumePotionsAtDeficits(d, *, categories=("life", "mana")):
    """Use finite owned stock at a witnessed deficit before ordinary road recovery erases it."""
    case = getattr(d, "case", None)
    if case is None:
        return
    for category in categories:
        branch = d.map_name + ".potion." + category + ".used"
        if branch not in case.branches or branch in d.branches:
            continue
        current, maximum = ("getHp", "getHpMax") if category == "life" else ("getMana", "getManaMax")
        if d.call(d.player, current) >= d.call(d.player, maximum):
            continue
        potions = ownedPotions(d, category)
        if potions:
            selected = min(
                potions, key=lambda item: (d.call(item, "getNumericProperty", "power"), d.call(item, "getName"))
            )
            useOwnedPotion(d, selected, branch)


def requirePotionConsumptions(d, *, categories=("life", "mana")):
    """Finish fixed gameplay with actual receipts, consuming a remaining owned potion only at a real deficit."""
    d.assertNativeCombatOutcomes()
    consumePotionsAtDeficits(d, categories=categories)
    d.test.assertTrue(
        all(
            d.map_name + ".potion." + category + ".used" in d.branches
            for category in categories
            if d.map_name + ".potion." + category + ".used" in d.case.branches
        ),
        "Every declared potion branch requires its actual native item-use event",
    )


def useOwnedPotion(d, item, branch):
    """An ordinary manual use needs both current MCP state and the actual native receipt."""
    from tests.gameplay_routes_services import nativeCheckpoint, nativeEventsSince, ownedIdentities

    d.test.assertIn(branch, d.case.branches)
    item_identity = item["__handle__"]
    owned_before = ownedIdentities(d)
    d.test.assertIn(item_identity, owned_before, "A borrowed or stocked potion cannot be consumed")
    type_id = d.call(item, "getTypeId")
    definition = potionDefinitions().get(type_id, {})
    d.test.assertIn(definition.get("class"), {"LifePotion", "ManaPotion"})
    category = "life" if definition["class"] == "LifePotion" else "mana"
    d.test.assertEqual(d.map_name + ".potion." + category + ".used", branch)
    d.test.assertEqual(definition["class"], d.call(item, "getType"))
    power = d.call(item, "getNumericProperty", "power")
    d.test.assertEqual(definition["properties"]["power"], power)
    before = {key: d.call(d.player, method) for key, method in (("hp", "getHp"), ("mana", "getMana"))}
    maximum = {key: d.call(d.player, method) for key, method in (("hp", "getHpMax"), ("mana", "getManaMax"))}
    key = "hp" if category == "life" else "mana"
    d.test.assertLess(before[key], maximum[key], "An actual combat/casting deficit is required")
    continuity = (d.game_map["__handle__"], d.player["__handle__"], d.coords(), d.call(d.game_map, "getTurn"))
    player_name, item_name = d.call(d.player, "getName"), d.call(item, "getName")
    checkpoint = nativeCheckpoint(d)
    d.call(d.player, "useItem", item)
    d.pump()
    d.assertSurvival()
    d.test.assertEqual(
        continuity,
        (d.game_map["__handle__"], d.player["__handle__"], d.coords(), d.call(d.game_map, "getTurn")),
        "Using a potion must not advance a map turn or change the real player",
    )
    d.test.assertEqual(owned_before - {item_identity}, ownedIdentities(d))
    for resource in ("hp", "mana"):
        current = d.call(d.player, "getHp" if resource == "hp" else "getMana")
        expected = (
            potionRestoration(before[resource], maximum[resource], power) if resource == key else before[resource]
        )
        d.test.assertEqual(expected, current)
    receipts = [
        witness
        for record in nativeEventsSince(d, checkpoint, "item_used")
        if (witness := potionUseWitness(record, player_name=player_name, map_name=d.map_name)) is not None
        and witness[1]["item"] == item_name
        and witness[1]["typeId"] == type_id
    ]
    d.test.assertEqual(1, len(receipts), "The exact selected potion needs one actual native consumption receipt")
    native_use = receipts[0][1]["nativeItemUse"]
    d.test.assertEqual(len(owned_before), native_use["inventoryBeforeCount"])
    d.test.assertEqual(len(owned_before) - 1, native_use["inventoryAfterCount"])
    for resource in ("hp", "mana"):
        d.test.assertEqual(before[resource], native_use[resource + "Before"])
        d.test.assertEqual(maximum[resource], native_use[resource + "MaxBefore"])
    d.check(branch, True, ownedIdentity=item_identity, **receipts[0][1])
