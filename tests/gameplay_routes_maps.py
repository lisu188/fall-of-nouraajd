# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored standalone routes, using only ordinary movement, combat and inventory actions."""

import json
from functools import partial
from pathlib import Path

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_branch_journals import verifyJournals

ROOT = Path(__file__).resolve().parents[1]


def mapObjects(map_name):
    document = json.loads((ROOT / "res/maps" / map_name / "map.json").read_text(encoding="utf-8"))
    return {
        item["name"]: (int(item["x"] // 32), int(item["y"] // 32), int(layer["properties"]["level"]))
        for layer in document["layers"]
        if layer["type"] == "objectgroup"
        for item in layer["objects"]
        if item.get("name")
    }


def startMap(d, map_name, start_name):
    d.startMap(map_name)
    start = d.object(start_name, required=False)
    if start:
        if d.coords() == d.coords(start):
            d.revisit(start_name)
        else:
            d.navigateTo(start_name)


def hostiles(d):
    result = []
    for actor in d.call(d.game_map, "getObjects"):
        properties = d.properties(actor)
        if "baseStats" not in properties:
            continue
        if not d.call(actor, "isPlayer") and not d.call(actor, "isNpc"):
            result.append(d.call(actor, "getName"))
    return sorted(result)


def clearHostiles(d, limit=256):
    for _ in range(limit):
        names = hostiles(d)
        if not names:
            return
        d.fight(names[0])
    d.test.fail({"reason": "Authored encounter did not finish", "map": d.map_name, "remaining": hostiles(d)})


def visitCaves(d, names, prefix):
    for name in names:
        cave = d.object(name, required=False)
        if cave:
            initial = d.call(cave, "getNumericProperty", "monsters")
            if initial > 0:
                d.waitTurns(512, lambda: d.call(cave, "getNumericProperty", "monsters") < initial)
                d.test.assertLess(d.call(cave, "getNumericProperty", "monsters"), initial)
            d.navigateTo(name)
        clearHostiles(d)
        d.check(prefix + ".cave." + name, d.object(name, required=False) is None, cave=name)


def tradeSupplies(d, market_name, branch):
    """Buy a real stocked potion only after ordinary loot has paid for it."""
    d.navigateTo(market_name)
    market = d.call(d.object(market_name), "getObjectProperty", "market")
    items = d.call(market, "getItems")
    d.test.assertTrue(items)
    choices = sorted(
        [
            (
                d.call(market, "getSellCost", item),
                d.call(item, "getTypeId"),
                item,
            )
            for item in items
        ],
        key=lambda entry: (entry[0], entry[1], entry[2]["__handle__"]),
    )
    price, item_id, item = choices[0]
    gold_before = d.gold()
    inventory_before = d.count(item_id)
    if gold_before < price:
        # A genuine insufficient-funds attempt must leave the stock and player unchanged.
        d.test.assertFalse(d.call(market, "sellItem", d.player, item))
        d.test.assertEqual(gold_before, d.gold())
        d.test.assertEqual(inventory_before, d.count(item_id))
        d.check(branch, item in d.call(market, "getItems"), outcome="insufficientGold", price=price)
        return
    d.buyAt(market_name, item_id, 1)
    d.check(
        branch,
        d.gold() == gold_before - price and d.count(item_id) == inventory_before + 1,
        outcome="purchased",
        item=item_id,
        price=price,
    )


def vhulmarn(d, informed):
    startMap(d, "vhulmarn", "vhulmarnStart")
    d.check("vhulmarn.arrival", "drownedTitheQuest" in d.questNames())
    verifyJournals(d)
    if informed:
        d.navigateTo("oldTollman")
        d.test.assertFalse(d.condition("tollmanDialog", "has_heard_tithe"))
        d.choose("tollmanDialog", "hear_the_tithe")
        d.check("vhulmarn.tollman.learned", d.flag("tithe_heard") and d.condition("tollmanDialog", "has_heard_tithe"))
        d.navigateTo("markedWidow")
        before = (d.gold(), d.count("tiaraOfTheDrownedTithe"))
        d.select("widowDialog", "ENTRY", 0)
        d.check("vhulmarn.widow.warning", before == (d.gold(), d.count("tiaraOfTheDrownedTithe")))
        visitCaves(d, ("caveTarnMouth", "caveSunkenWharf", "caveHybridWarren"), "vhulmarn")
        tradeSupplies(d, "tarnBarter", "vhulmarn.market")
    d.navigateTo("tideBell")
    d.check("vhulmarn.bell.tolled", d.flag("bell_tolled"))
    clearHostiles(d)
    d.revisit("tideBell")
    d.check("vhulmarn.bell.repeat", d.flag("bell_tolled"))
    if not informed:
        d.check("vhulmarn.tollman.bypassed", not d.flag("tithe_heard"))
    count_before = d.count("tiaraOfTheDrownedTithe")
    d.navigateTo("altarThreshold")
    d.check(
        "vhulmarn.altar.pickup",
        d.flag("tithe_taken") and d.flag("boss_woken") and d.count("tiaraOfTheDrownedTithe") == count_before + 1,
    )
    d.test.assertNotIn("drownedTitheQuest", d.questNames(completed=True))
    d.saveAndReload("vhulmarn-altar")
    d.fight("theNamelessBoss")
    d.check("vhulmarn.boss.defeated", d.flag("boss_defeated"))
    d.check("vhulmarn.quest.complete", "drownedTitheQuest" in d.questNames(completed=True))
    verifyJournals(d)
    d.revisit("altarThreshold")
    d.check(
        "vhulmarn.altar.repeat",
        d.count("tiaraOfTheDrownedTithe") == count_before + 1 and d.object("theNamelessBoss", required=False) is None,
    )


def kadath(d, informed):
    startMap(d, "kadath", "kadathStart")
    d.check("kadath.arrival", "kadathAscentQuest" in d.questNames())
    verifyJournals(d)
    if informed:
        d.navigateTo("dreamerGuide")
        d.test.assertFalse(d.condition("dreamerDialog", "has_heard_ascent"))
        d.choose("dreamerDialog", "hear_the_ascent")
        d.check("kadath.guide.learned", d.flag("ascent_heard") and d.condition("dreamerDialog", "has_heard_ascent"))
        d.navigateTo("lengPriest")
        before = (d.gold(), d.count("onyxSignetOfNyarlathotep"))
        d.select("lengPriestDialog", "ENTRY", 0)
        d.check("kadath.priest.refuse", before == (d.gold(), d.count("onyxSignetOfNyarlathotep")))
        visitCaves(d, ("roostNightGaunt", "warrenLeng", "vaultElder", "roostNorth", "nestLengSpider"), "kadath")
        tradeSupplies(d, "campBarter", "kadath.market")
        d.navigateTo("dreamGate")
        d.check("kadath.gate.opened", d.flag("gate_opened"))
        clearHostiles(d)
        d.revisit("dreamGate")
        d.check("kadath.gate.repeat", d.flag("gate_opened"))
    else:
        # The second basalt-road lane is authored and bypasses the standing stones.
        for y in range(64, 55, -1):
            d.navigateCoords((101, y, 0))
        d.check("kadath.guide.bypassed", not d.flag("ascent_heard"))
        d.check("kadath.gate.bypassed", not d.flag("gate_opened"))
    count_before = d.count("onyxSignetOfNyarlathotep")
    d.navigateTo("onyxThrone")
    d.check(
        "kadath.throne.pickup",
        d.flag("throne_taken") and d.flag("boss_woken") and d.count("onyxSignetOfNyarlathotep") == count_before + 1,
    )
    d.test.assertNotIn("kadathAscentQuest", d.questNames(completed=True))
    d.saveAndReload("kadath-throne")
    d.fight("theCrawlingChaosBoss")
    d.check("kadath.boss.defeated", d.flag("boss_defeated"))
    d.check("kadath.quest.complete", "kadathAscentQuest" in d.questNames(completed=True))
    verifyJournals(d)
    d.revisit("onyxThrone")
    d.check(
        "kadath.throne.repeat",
        d.count("onyxSignetOfNyarlathotep") == count_before + 1
        and d.object("theCrawlingChaosBoss", required=False) is None,
    )


def sunderedmarch(d, banner_first):
    startMap(d, "sunderedmarch", "marchStart")
    d.check("sunderedmarch.arrival", "sunderedMarchQuest" in d.questNames())
    verifyJournals(d)
    d.navigateTo("gateThreshold")
    d.check("sunderedmarch.gate.locked", not d.flag("gate_open") and d.object("borderGate", required=False) is not None)
    d.navigateTo("keymasterCache")
    d.check("sunderedmarch.key.pickup", d.count("ironKey") == 1)
    d.revisit("keymasterCache")
    d.check("sunderedmarch.key.repeat", d.count("ironKey") == 1)
    d.navigateTo("gateThreshold")
    d.check("sunderedmarch.gate.open", d.flag("gate_open") and d.object("borderGate", required=False) is None)
    d.revisit("gateThreshold")
    d.check("sunderedmarch.gate.repeat", d.flag("gate_open") and d.count("ironKey") == 1)
    d.navigateTo("digSite")
    d.check("sunderedmarch.dig.locked0", not d.flag("crown_taken") and d.number("sigils_found") == 0)
    if banner_first:
        d.navigateTo("bannerCache")
    d.navigateTo("seerHut")
    d.test.assertTrue(d.condition("seerDialog", "not_yet_started"))
    d.choose("seerDialog", "start_seer_hunt")
    d.check(
        "sunderedmarch.seer.bannerFirst" if banner_first else "sunderedmarch.seer.questFirst", d.flag("seer_started")
    )
    d.select("seerDialog", "ACCEPTED", 0)
    if not banner_first:
        d.select("seerDialog", "ENTRY", 2)
        d.check("sunderedmarch.seer.reminder", d.condition("seerDialog", "questInProgress"))
        d.select("seerDialog", "REMINDER", 0)
        d.navigateTo("bannerCache")
    d.check("sunderedmarch.banner.pickup", d.count("warBanner") == 1)
    d.revisit("bannerCache")
    d.check("sunderedmarch.banner.repeat", d.count("warBanner") == 1)
    d.navigateTo("seerHut")
    gold_before, potions_before = d.gold(), d.count("GreaterLifePotion")
    d.choose("seerDialog", "finish_seer_hunt", "can_return_banner")
    d.check(
        "sunderedmarch.seer.reward",
        d.flag("seer_done") and d.gold() == gold_before + 300 and d.count("GreaterLifePotion") == potions_before + 1,
    )
    d.check("sunderedmarch.seer.bannerRetained", d.count("warBanner") == 1)
    d.test.assertFalse(d.condition("seerDialog", "can_return_banner"))
    d.call(d.player, "checkQuests")
    d.check("sunderedmarch.seer.complete", "seerHuntQuest" in d.questNames(completed=True))
    verifyJournals(d)
    d.navigateTo("learningStone", adjacent=True)
    gold_before = d.gold()
    d.navigateTo("learningStone")
    d.check("sunderedmarch.learningStone.first", d.flag("shrine_used") and d.gold() == gold_before + 100)
    gold_before = d.gold()
    d.revisit("learningStone")
    d.check("sunderedmarch.learningStone.repeat", d.flag("shrine_used") and d.gold() == gold_before)
    for index, name in enumerate(("obeliskVale", "obeliskBarrow", "obeliskPyre"), 1):
        d.navigateTo(name)
        d.check("sunderedmarch.obelisk." + name, d.number("sigils_found") == index)
        d.revisit(name)
        d.test.assertEqual(index, d.number("sigils_found"))
        if index < 3:
            d.navigateTo("digSite")
            d.check("sunderedmarch.dig.locked" + str(index), not d.flag("crown_taken"))
    d.navigateTo("artifactCache")
    d.check("sunderedmarch.artifact.pickup", d.count("reaverBlade") == 1)
    d.revisit("artifactCache")
    d.check("sunderedmarch.artifact.repeat", d.count("reaverBlade") == 1)
    for name, target in (("monolithVale", "monolithPyre"), ("monolithPyre", "monolithVale")):
        d.navigateTo(name)
        d.check("sunderedmarch.portal." + name, d.coords() == d.coords(d.object(target)))
    visitCaves(d, ("valeGuard", "gateGuard", "barrowGuard", "fenGuard", "pyreGuard"), "sunderedmarch")
    for name in ("valeChest", "fenChest", "pyreChest", "barrowChest"):
        d.navigateTo(name)
        chest = d.object(name)
        d.test.assertTrue(d.call(chest, "getBoolProperty", "looted"))
        gold_before = d.gold()
        d.revisit(name)
        d.check("sunderedmarch.chest." + name, d.gold() == gold_before)
    tradeSupplies(d, "valeBarter", "sunderedmarch.market")
    d.navigateTo("digSite")
    d.check("sunderedmarch.dig.crown", d.flag("crown_taken") and d.flag("boss_woken") and d.count("barrowCrown") == 1)
    d.test.assertNotIn("sunderedMarchQuest", d.questNames(completed=True))
    d.saveAndReload("sunderedmarch-crown")
    d.fight("theBarrowWarlordBoss")
    d.check("sunderedmarch.boss.defeated", d.flag("boss_defeated"))
    d.check("sunderedmarch.quest.complete", "sunderedMarchQuest" in d.questNames(completed=True))
    verifyJournals(d)
    d.revisit("digSite")
    d.check(
        "sunderedmarch.dig.repeat",
        d.count("barrowCrown") == 1 and d.object("theBarrowWarlordBoss", required=False) is None,
    )


def multilevel(d):
    startMap(d, "multilevel", "multilevelStart")
    d.check("multilevel.arrival", d.flag("visited_multilevel_start"))
    d.navigateTo("stairsUp")
    d.check("multilevel.stairs.up", d.coords()[2] == 1 and d.flag("used_stairs_up"))
    d.navigateTo("multilevelUpperGoal")
    d.check("multilevel.goal.upper", d.flag("visited_upper_goal"))
    d.navigateTo("stairsDown")
    d.check("multilevel.stairs.down", d.coords()[2] == 0 and d.flag("used_stairs_down"))
    d.navigateTo("multilevelLowerGoal")
    d.check("multilevel.goal.lower", d.flag("visited_lower_goal"))
    before = d.number("levelTransitionCount")
    d.saveAndReload("multilevel-both-goals")
    d.navigateTo("stairsUp")
    d.navigateTo("multilevelUpperGoal")
    d.navigateTo("stairsDown")
    d.check("multilevel.stairs.repeat", d.number("levelTransitionCount") == before + 2 and d.coords()[2] == 0)


def testMarket(d, purchased, earned_items=()):
    d.navigateTo("market1")
    market = d.call(d.object("market1"), "getObjectProperty", "market")
    stock = d.call(market, "getItems")
    d.test.assertTrue(stock)
    item = min(stock, key=lambda value: (d.call(market, "getSellCost", value), value["__handle__"]))
    price = d.call(market, "getSellCost", item)
    if purchased:
        while d.gold() < price:
            loot = [value for value in d.call(d.player, "getItems") if value["__handle__"] in earned_items]
            sale = [(d.call(market, "getBuyCost", value), value["__handle__"], value) for value in loot]
            sale = [value for value in sale if value[0] > 0]
            d.test.assertTrue(sale, "Real chest and encounter loot must fund the purchase")
            d.sellAt("market1", max(sale, key=lambda value: value[:2])[2])
        d.test.assertGreaterEqual(d.gold(), price)
    else:
        d.test.assertLess(d.gold(), price)
    gold_before = d.gold()
    stock_before = {value["__handle__"] for value in d.call(market, "getItems")}
    owned_before = {value["__handle__"] for value in d.call(d.player, "getItems")}
    accepted = d.call(market, "sellItem", d.player, item)
    stock_after = {value["__handle__"] for value in d.call(market, "getItems")}
    owned_after = {value["__handle__"] for value in d.call(d.player, "getItems")}
    d.check(
        "test.market.purchased" if purchased else "test.market.insufficientGold",
        accepted == purchased
        and d.gold() == gold_before - (price if purchased else 0)
        and stock_after == stock_before - ({item["__handle__"]} if purchased else set())
        and owned_after == owned_before | ({item["__handle__"]} if purchased else set()),
        item=item["__handle__"],
        price=price,
        goldBefore=gold_before,
        goldAfter=d.gold(),
    )


def testMap(d):
    d.startMap("test")
    d.tick()
    d.check("test.firstTurn.encounter", d.call(d.game_map, "getTurn") > 0 and bool(hostiles(d)))
    from tests.castle_walkthrough import TransitRoutes, shortestRoute
    from tests.narrative_walkthrough import authoredRegion

    positions, walkable = authoredRegion("test")
    reserved = {positions[name] for name in ("chest", "groundHole", "teleporter1", "teleporter2", "teleporter3")}
    for _step, arrival in shortestRoute(walkable - reserved, TransitRoutes(), d.coords(), positions["market1"]):
        d.navigateCoords(arrival)
        d.test.assertFalse(d.call(d.object("chest"), "getBoolProperty", "looted"))
    testMarket(d, False)
    owned_before_loot = {value["__handle__"] for value in d.call(d.player, "getItems")}
    clearHostiles(d)
    d.navigateTo("chest")
    d.check("test.chest.first", d.call(d.object("chest"), "getBoolProperty", "looted"))
    earned_items = {value["__handle__"] for value in d.call(d.player, "getItems")} - owned_before_loot
    gold_before = d.gold()
    d.revisit("chest")
    d.check("test.chest.repeat", d.gold() == gold_before)
    d.navigateTo("chaosSword")
    d.check("test.item.pickup", d.count("ChaosSword") >= 1)
    earned_items.update({value["__handle__"] for value in d.call(d.player, "getItems")} - owned_before_loot)
    testMarket(d, True, earned_items)
    target = mapObjects("test")["teleporter2"]
    d.navigateTo("teleporter1")
    d.check("test.teleporter.first", d.coords() == target)
    d.revisit("teleporter2")
    d.check("test.teleporter.disabled", d.coords() == target)
    d.navigateTo("teleporter3")
    d.check("test.teleporter.third", d.coords() == target)
    probe = d.object("initializationProbe")
    coordinates = d.coords(probe)
    d.check(
        "test.initialization.properties",
        d.call(probe, "getStringProperty", "observedMarker") == d.call(probe, "getStringProperty", "marker")
        and tuple(d.call(probe, "getNumericProperty", "observed" + axis) for axis in "XYZ") == coordinates,
    )
    d.navigateTo("changeMap")
    d.check("test.changeMap.inert", d.map_name == "test")
    d.navigateTo("groundHole")
    d.check("test.groundHole", d.coords() == (12, 7, -1))


VHULMARN_COMMON = (
    "vhulmarn.arrival",
    "vhulmarn.bell.tolled",
    "vhulmarn.bell.repeat",
    "vhulmarn.altar.pickup",
    "vhulmarn.boss.defeated",
    "vhulmarn.quest.complete",
    "vhulmarn.altar.repeat",
)
KADATH_COMMON = (
    "kadath.arrival",
    "kadath.throne.pickup",
    "kadath.boss.defeated",
    "kadath.quest.complete",
    "kadath.throne.repeat",
)
SUNDERED_COMMON = (
    "sunderedmarch.arrival",
    "sunderedmarch.gate.locked",
    "sunderedmarch.key.pickup",
    "sunderedmarch.key.repeat",
    "sunderedmarch.gate.open",
    "sunderedmarch.gate.repeat",
    "sunderedmarch.dig.locked0",
    "sunderedmarch.banner.pickup",
    "sunderedmarch.banner.repeat",
    "sunderedmarch.seer.reward",
    "sunderedmarch.seer.bannerRetained",
    "sunderedmarch.seer.complete",
    "sunderedmarch.learningStone.first",
    "sunderedmarch.learningStone.repeat",
    "sunderedmarch.obelisk.obeliskVale",
    "sunderedmarch.obelisk.obeliskBarrow",
    "sunderedmarch.obelisk.obeliskPyre",
    "sunderedmarch.dig.locked1",
    "sunderedmarch.dig.locked2",
    "sunderedmarch.artifact.pickup",
    "sunderedmarch.artifact.repeat",
    "sunderedmarch.portal.monolithVale",
    "sunderedmarch.portal.monolithPyre",
    "sunderedmarch.market",
    "sunderedmarch.cave.valeGuard",
    "sunderedmarch.cave.gateGuard",
    "sunderedmarch.cave.barrowGuard",
    "sunderedmarch.cave.fenGuard",
    "sunderedmarch.cave.pyreGuard",
    "sunderedmarch.chest.valeChest",
    "sunderedmarch.chest.fenChest",
    "sunderedmarch.chest.pyreChest",
    "sunderedmarch.chest.barrowChest",
    "sunderedmarch.dig.crown",
    "sunderedmarch.boss.defeated",
    "sunderedmarch.quest.complete",
    "sunderedmarch.dig.repeat",
)


def sources(map_name):
    return tuple("res/maps/" + map_name + "/" + name for name in ("script.py", "config.json", "map.json"))


CASES = (
    RouteCase(
        id="vhulmarn-informed",
        group="standalone",
        maps=("vhulmarn",),
        run=partial(vhulmarn, informed=True),
        branches=VHULMARN_COMMON
        + (
            "vhulmarn.tollman.learned",
            "vhulmarn.widow.warning",
            "vhulmarn.market",
            "vhulmarn.cave.caveTarnMouth",
            "vhulmarn.cave.caveSunkenWharf",
            "vhulmarn.cave.caveHybridWarren",
        ),
        sources=sources("vhulmarn"),
    ),
    RouteCase(
        id="vhulmarn-uninformed",
        group="standalone",
        maps=("vhulmarn",),
        run=partial(vhulmarn, informed=False),
        branches=VHULMARN_COMMON + ("vhulmarn.tollman.bypassed",),
        sources=sources("vhulmarn"),
    ),
    RouteCase(
        id="kadath-informed",
        group="standalone",
        maps=("kadath",),
        run=partial(kadath, informed=True),
        branches=KADATH_COMMON
        + (
            "kadath.guide.learned",
            "kadath.priest.refuse",
            "kadath.market",
            "kadath.gate.opened",
            "kadath.gate.repeat",
            "kadath.cave.roostNightGaunt",
            "kadath.cave.warrenLeng",
            "kadath.cave.vaultElder",
            "kadath.cave.roostNorth",
            "kadath.cave.nestLengSpider",
        ),
        sources=sources("kadath"),
    ),
    RouteCase(
        id="kadath-gate-bypassed",
        group="standalone",
        maps=("kadath",),
        run=partial(kadath, informed=False),
        branches=KADATH_COMMON + ("kadath.guide.bypassed", "kadath.gate.bypassed"),
        sources=sources("kadath"),
    ),
    RouteCase(
        id="sunderedmarch-quest-first",
        group="standalone",
        maps=("sunderedmarch",),
        run=partial(sunderedmarch, banner_first=False),
        branches=SUNDERED_COMMON + ("sunderedmarch.seer.questFirst", "sunderedmarch.seer.reminder"),
        sources=sources("sunderedmarch"),
    ),
    RouteCase(
        id="sunderedmarch-banner-first",
        group="standalone",
        maps=("sunderedmarch",),
        run=partial(sunderedmarch, banner_first=True),
        branches=SUNDERED_COMMON + ("sunderedmarch.seer.bannerFirst",),
        sources=sources("sunderedmarch"),
    ),
    RouteCase(
        id="multilevel-return",
        group="navigation",
        maps=("multilevel",),
        run=multilevel,
        branches=(
            "multilevel.arrival",
            "multilevel.stairs.up",
            "multilevel.goal.upper",
            "multilevel.stairs.down",
            "multilevel.goal.lower",
            "multilevel.stairs.repeat",
        ),
        sources=sources("multilevel"),
    ),
    RouteCase(
        id="test-authored-objects",
        group="navigation",
        maps=("test",),
        run=testMap,
        branches=(
            "test.firstTurn.encounter",
            "test.chest.first",
            "test.chest.repeat",
            "test.item.pickup",
            "test.market.insufficientGold",
            "test.market.purchased",
            "test.teleporter.first",
            "test.teleporter.disabled",
            "test.teleporter.third",
            "test.initialization.properties",
            "test.changeMap.inert",
            "test.groundHole",
        ),
        sources=sources("test") + ("res/plugins/object.py", "src/object/CMarket.cpp"),
    ),
)


DEFENSIVE_BRANCHES = {
    "vhulmarn.bell.bypassedFinale": "The bell is a cut vertex of the authored walkable causeway; no altar route avoids it.",
    "standalone.bossBeforePickup": "Each finale creates its unique boss only after granting the quest item.",
    "multilevel.blockedLanding": "The shipped stair destinations are walkable; requires a modified map fixture.",
}


SOURCE_BRANCHES = {
    "res/plugins/object.py:Market.onEnter": ("test.market.insufficientGold", "test.market.purchased"),
    "res/maps/vhulmarn/script.py:StartEvent.onEnter": ("vhulmarn.arrival",),
    "res/maps/vhulmarn/script.py:TideBell.onEnter": ("vhulmarn.bell.tolled", "vhulmarn.bell.repeat"),
    "res/maps/vhulmarn/script.py:AltarThreshold.onEnter": ("vhulmarn.altar.pickup", "vhulmarn.altar.repeat"),
    "res/maps/vhulmarn/script.py:DrownedTitheQuest.isCompleted": ("vhulmarn.quest.complete",),
    "res/maps/vhulmarn/script.py:DrownedTitheQuest.onComplete": ("vhulmarn.quest.complete",),
    "res/maps/vhulmarn/script.py:TollmanDialog.has_heard_tithe": (
        "vhulmarn.tollman.learned",
        "vhulmarn.tollman.bypassed",
    ),
    "res/maps/vhulmarn/script.py:TollmanDialog.hear_the_tithe": ("vhulmarn.tollman.learned",),
    "res/maps/vhulmarn/script.py:TollmanTrigger.trigger": ("vhulmarn.tollman.learned",),
    "res/maps/vhulmarn/script.py:WidowTrigger.trigger": ("vhulmarn.widow.warning",),
    "res/maps/vhulmarn/script.py:TarnMouthTrigger.trigger": ("vhulmarn.cave.caveTarnMouth",),
    "res/maps/vhulmarn/script.py:SunkenWharfTrigger.trigger": ("vhulmarn.cave.caveSunkenWharf",),
    "res/maps/vhulmarn/script.py:HybridWarrenTrigger.trigger": ("vhulmarn.cave.caveHybridWarren",),
    "res/maps/vhulmarn/script.py:NamelessTrigger.trigger": ("vhulmarn.boss.defeated",),
    "res/maps/kadath/script.py:StartEvent.onEnter": ("kadath.arrival",),
    "res/maps/kadath/script.py:DreamGate.onEnter": ("kadath.gate.opened", "kadath.gate.repeat"),
    "res/maps/kadath/script.py:OnyxThrone.onEnter": ("kadath.throne.pickup", "kadath.throne.repeat"),
    "res/maps/kadath/script.py:KadathAscentQuest.isCompleted": ("kadath.quest.complete",),
    "res/maps/kadath/script.py:KadathAscentQuest.onComplete": ("kadath.quest.complete",),
    "res/maps/kadath/script.py:DreamerDialog.has_heard_ascent": ("kadath.guide.learned", "kadath.guide.bypassed"),
    "res/maps/kadath/script.py:DreamerDialog.hear_the_ascent": ("kadath.guide.learned",),
    "res/maps/kadath/script.py:DreamerTrigger.trigger": ("kadath.guide.learned",),
    "res/maps/kadath/script.py:LengPriestTrigger.trigger": ("kadath.priest.refuse",),
    "res/maps/kadath/script.py:RoostNightGauntTrigger.trigger": ("kadath.cave.roostNightGaunt",),
    "res/maps/kadath/script.py:WarrenLengTrigger.trigger": ("kadath.cave.warrenLeng",),
    "res/maps/kadath/script.py:VaultElderTrigger.trigger": ("kadath.cave.vaultElder",),
    "res/maps/kadath/script.py:CrawlingChaosTrigger.trigger": ("kadath.boss.defeated",),
    "res/maps/sunderedmarch/script.py:StartEvent.onEnter": ("sunderedmarch.arrival",),
    "res/maps/sunderedmarch/script.py:LearningStone.onEnter": (
        "sunderedmarch.learningStone.first",
        "sunderedmarch.learningStone.repeat",
    ),
    "res/maps/sunderedmarch/script.py:Obelisk.onEnter": tuple(
        "sunderedmarch.obelisk." + name for name in ("obeliskVale", "obeliskBarrow", "obeliskPyre")
    ),
    "res/maps/sunderedmarch/script.py:KeymasterCache.onEnter": ("sunderedmarch.key.pickup", "sunderedmarch.key.repeat"),
    "res/maps/sunderedmarch/script.py:GateThreshold.onEnter": (
        "sunderedmarch.gate.locked",
        "sunderedmarch.gate.open",
        "sunderedmarch.gate.repeat",
    ),
    "res/maps/sunderedmarch/script.py:BannerCache.onEnter": (
        "sunderedmarch.banner.pickup",
        "sunderedmarch.banner.repeat",
    ),
    "res/maps/sunderedmarch/script.py:ArtifactCache.onEnter": (
        "sunderedmarch.artifact.pickup",
        "sunderedmarch.artifact.repeat",
    ),
    "res/maps/sunderedmarch/script.py:DigSite.onEnter": (
        "sunderedmarch.dig.locked0",
        "sunderedmarch.dig.locked1",
        "sunderedmarch.dig.locked2",
        "sunderedmarch.dig.crown",
        "sunderedmarch.dig.repeat",
    ),
    "res/maps/sunderedmarch/script.py:SunderedMarchQuest.isCompleted": ("sunderedmarch.quest.complete",),
    "res/maps/sunderedmarch/script.py:SunderedMarchQuest.onComplete": ("sunderedmarch.quest.complete",),
    "res/maps/sunderedmarch/script.py:SeerHuntQuest.isCompleted": ("sunderedmarch.seer.complete",),
    "res/maps/sunderedmarch/script.py:SeerDialog.can_return_banner": ("sunderedmarch.seer.reward",),
    "res/maps/sunderedmarch/script.py:SeerDialog.not_yet_started": (
        "sunderedmarch.seer.questFirst",
        "sunderedmarch.seer.bannerFirst",
    ),
    "res/maps/sunderedmarch/script.py:SeerDialog.questInProgress": ("sunderedmarch.seer.reminder",),
    "res/maps/sunderedmarch/script.py:SeerDialog.start_seer_hunt": (
        "sunderedmarch.seer.questFirst",
        "sunderedmarch.seer.bannerFirst",
    ),
    "res/maps/sunderedmarch/script.py:SeerDialog.finish_seer_hunt": ("sunderedmarch.seer.reward",),
    "res/maps/sunderedmarch/script.py:SeerTrigger.trigger": (
        "sunderedmarch.seer.questFirst",
        "sunderedmarch.seer.bannerFirst",
    ),
    "res/maps/sunderedmarch/script.py:ValeGuardTrigger.trigger": ("sunderedmarch.cave.valeGuard",),
    "res/maps/sunderedmarch/script.py:FenGuardTrigger.trigger": ("sunderedmarch.cave.fenGuard",),
    "res/maps/sunderedmarch/script.py:PyreGuardTrigger.trigger": ("sunderedmarch.cave.pyreGuard",),
    "res/maps/sunderedmarch/script.py:BarrowGuardTrigger.trigger": ("sunderedmarch.cave.barrowGuard",),
    "res/maps/sunderedmarch/script.py:BarrowWarlordTrigger.trigger": ("sunderedmarch.boss.defeated",),
    "res/maps/multilevel/script.py:LevelStairs.onCreate": ("multilevel.stairs.up", "multilevel.stairs.down"),
    "res/maps/multilevel/script.py:LevelStairs.onTurn": ("multilevel.stairs.repeat",),
    "res/maps/multilevel/script.py:LevelStairs.onEnter": (
        "multilevel.stairs.up",
        "multilevel.stairs.down",
        "multilevel.stairs.repeat",
    ),
    "res/maps/multilevel/script.py:MultilevelStart.onCreate": ("multilevel.arrival",),
    "res/maps/multilevel/script.py:MultilevelStart.onEnter": ("multilevel.arrival",),
    "res/maps/multilevel/script.py:MultilevelGoal.onEnter": ("multilevel.goal.upper", "multilevel.goal.lower"),
    "res/maps/test/script.py:InitializationProbe.onCreate": ("test.initialization.properties",),
    "res/maps/test/script.py:TurnTrigger.trigger": ("test.firstTurn.encounter",),
}

DEFENSIVE_SOURCE_BRANCHES = {
    "res/maps/multilevel/script.py:LevelStairs.onDestroy": "The authored route traverses intact stairs; destruction is a teardown contract.",
}
