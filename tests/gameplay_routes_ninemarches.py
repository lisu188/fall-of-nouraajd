# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored Nine Marches routes; combat, loot and reputation come from play."""

from functools import lru_cache, partial
import json
from pathlib import Path

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_branch_driver import authoredRoadCells
from tests.gameplay_branch_journals import verifyJournals
from tests.gameplay_routes_services import marketAttempt, readSignpost
from tests.gameplay_routes_crafting import openStation, recipeAttempt
from tests.gameplay_routes_waypoints import verifyWaypointPublication
from tests.gameplay_routes_potions import consumePotionsAtDeficits

SOURCES = (
    "res/maps/ninemarches/script.py",
    "res/maps/ninemarches/config.json",
    "res/maps/ninemarches/dialog.json",
    "res/maps/ninemarches/map.json",
    "res/plugins/object.py",
    "res/plugins/crafting.py",
    "res/config/crafting.json",
)
COMPANIONS = {
    "halda": ("companionKnight", "knightDialog", "banditCache", "banditLedger", "aegisOfHalda"),
    "morrigane": ("companionWitch", "witchDialog", "relicCache", "fenRelic", "morriganesCharm"),
    "corvyn": ("companionSellsword", "sellswordDialog", "ashRelicCache", "ashRelic", "corvynsBlade"),
}
GATES = (
    ("iron", "ironKeyCache", "ironGateThreshold", "ironGate", 2),
    ("bone", "boneKeyCache", "boneGateThreshold", "boneGate", 3),
    ("brass", "brassKeyCache", "brassGateThreshold", "brassGate", 3),
)
OBELISKS = ("obeliskFields", "obeliskFen", "obeliskBarrows", "obeliskAsh", "obeliskCoast", "obeliskCold")
MONOLITH_EXITS = {
    "monolithHub": "monolithCoast",
    "monolithCoast": "monolithHub",
    "monolithAsh": "monolithCold",
    "monolithCold": "monolithAsh",
}


@lru_cache(maxsize=1)
def authoredMonolithCoords():
    document = json.loads(
        (Path(__file__).resolve().parents[1] / "res/maps/ninemarches/map.json").read_text(encoding="utf-8")
    )
    return {
        actor["name"]: (
            int(actor["x"] // document["tilewidth"]),
            int(actor["y"] // document["tileheight"]),
            int(layer["properties"]["level"]),
        )
        for layer in document["layers"]
        if layer["type"] == "objectgroup"
        for actor in layer["objects"]
        if actor["name"] in MONOLITH_EXITS
    }


@lru_cache(maxsize=1)
def recoveryRoadCells():
    document = json.loads(
        (Path(__file__).resolve().parents[1] / "res/maps/ninemarches/map.json").read_text(encoding="utf-8")
    )
    reserved = {
        (
            int(actor["x"] // document["tilewidth"]),
            int(actor["y"] // document["tileheight"]),
            int(layer["properties"]["level"]),
        )
        for layer in document["layers"]
        if layer["type"] == "objectgroup"
        for actor in layer["objects"]
    }
    return authoredRoadCells("ninemarches") - reserved


def newCombatWitness(d):
    """Consume each real victory once, even after recovery turns rotate its already validated trace."""
    d.test.assertIsNotNone(d.trace_path, "Natural recovery requires the actual native combat trace")
    record = d.latestPlayerVictory("ninemarches")
    last_seq = getattr(d, "_marches_combat_seq", 0)
    if record is None or record["seq"] <= last_seq:
        return False
    d._marches_combat_seq = record["seq"]
    return True


def retreatWithOwnedScroll(d):
    name = getattr(d, "_marches_retreat_scroll_name", None)
    items = d.call(d.player, "getItems")
    scrolls = [
        item for item in items if d.call(item, "getName") == name and d.call(item, "getTypeId") == "TownPortalScroll"
    ]
    d.test.assertEqual(1, len(scrolls), "No unused, actually collected retreat scroll remains")
    entry = tuple(d.call(d.game_map, method) for method in ("getEntryX", "getEntryY", "getEntryZ"))
    origin = d.coords()
    d.test.assertNotEqual(entry, origin, "A retreat witness must begin away from the destination")
    identity = (d.game_map["__handle__"], d.player["__handle__"])
    owned = {item["__handle__"] for item in items}
    d.call(d.player, "useItem", scrolls[0])
    d.pump()
    d.test.assertEqual(identity, (d.game_map["__handle__"], d.player["__handle__"]))
    d.test.assertEqual(entry, d.coords(), "The owned scroll must actually reach the authored map entry")
    d.test.assertEqual(
        owned - {scrolls[0]["__handle__"]}, {item["__handle__"] for item in d.call(d.player, "getItems")}
    )
    d._marches_retreat_scroll_name = None
    if "ninemarches.scroll.retreat" in d.case.branches:
        d.check("ninemarches.scroll.retreat", True, item=scrolls[0]["__handle__"], origin=origin, destination=entry)


def retreatToRecoveryRoad(d):
    if getattr(d, "_marches_retreat_scroll_name", None) is not None:
        retreatWithOwnedScroll(d)
        return
    entry = tuple(d.call(d.game_map, method) for method in ("getEntryX", "getEntryY", "getEntryZ"))
    identity = (d.game_map["__handle__"], d.player["__handle__"])
    d.navigateCoords(entry)
    d.test.assertEqual(identity, (d.game_map["__handle__"], d.player["__handle__"]))
    d.test.assertEqual(entry, d.coords(), "Walking retreat must actually reach the authored map entry")
    d.record({"naturalWalkingRetreat": entry})


def afterCombat(d):
    if not newCombatWitness(d):
        return
    consumePotionsAtDeficits(d)
    if all(
        d.call(d.player, current) >= d.call(d.player, maximum)
        for current, maximum in (("getHp", "getHpMax"), ("getMana", "getManaMax"))
    ):
        return
    roads = recoveryRoadCells()
    if d.roadRecoveryTarget(road_cells=roads) is None:
        retreatToRecoveryRoad(d)
    recovery_enabled = d.recoveryEnabled
    d.recoveryEnabled = False
    try:
        turns = d.recoverOnAuthoredRoad(road_cells=roads)
    finally:
        d.recoveryEnabled = recovery_enabled
    d.test.assertGreaterEqual(d.call(d.player, "getHp"), d.call(d.player, "getHpMax"))
    d.test.assertGreaterEqual(d.call(d.player, "getMana"), d.call(d.player, "getManaMax"))
    d.record({"naturalRoadRecovery": turns, "nativeCombatSeq": d._marches_combat_seq})


def leaveIncidentalMonolith(d, target_name):
    """Leave a portal cell physically before another native path can execute its reverse edge."""
    if target_name in MONOLITH_EXITS or d.map_name != "ninemarches":
        return False
    coordinates = authoredMonolithCoords()
    origin = d.coords()
    matches = [name for name, coords in coordinates.items() if coords == origin]
    if not matches:
        return False
    d.test.assertEqual(1, len(matches))
    d.test.assertFalse(getattr(d, "_marches_departing_monolith", False), "Monolith departure cannot recurse")
    source_name = matches[0]
    source = d.object(source_name, required=False)
    if source is None:
        return False
    d.test.assertEqual(source_name, d.call(source, "getName"))
    d.test.assertEqual(source_name, d.call(source, "getTypeId"))
    d.test.assertEqual(origin, d.coords(source))
    if (
        d.call(source, "getBoolProperty", "enabled") is not True
        or d.call(source, "getBoolProperty", "waypoint") is not True
    ):
        return False
    exit_name = MONOLITH_EXITS[source_name]
    d.test.assertEqual(exit_name, d.call(source, "getStringProperty", "exit"))
    exit_object = d.object(exit_name)
    d.test.assertEqual(exit_name, d.call(exit_object, "getName"))
    d.test.assertEqual(exit_name, d.call(exit_object, "getTypeId"))
    d.test.assertEqual(coordinates[exit_name], d.coords(exit_object))
    if d.canStep(coordinates[exit_name]) is not True:
        return False
    target = d.object(target_name, required=False)
    if target is None:
        return False
    target_coords = d.coords(target)
    candidates = [
        (origin[0] + dx, origin[1] + dy, origin[2])
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))
        if (origin[0] + dx, origin[1] + dy, origin[2]) not in coordinates.values()
        and d.canStep((origin[0] + dx, origin[1] + dy, origin[2])) is True
    ]
    d.test.assertTrue(candidates, ("No live-passable cardinal monolith departure", source_name, origin))
    destination = min(candidates, key=lambda coords: (sum(abs(a - b) for a, b in zip(coords, target_coords)), coords))
    identity = (d.game_map["__handle__"], d.player["__handle__"])
    turn = d.call(d.game_map, "getTurn")
    d._marches_departing_monolith = True
    try:
        d.step(destination)
        d.test.assertEqual(identity, (d.game_map["__handle__"], d.player["__handle__"]))
        d.test.assertEqual(destination, d.coords(), "The monolith departure must be an actual cardinal entry")
        d.test.assertGreater(d.call(d.game_map, "getTurn"), turn)
        current_target = d.object(target_name, required=False)
        if current_target is not None:
            d.test.assertEqual(target["__handle__"], current_target["__handle__"], "The approach target was replaced")
            controller = d.call(d.player, "getController")
            d.call(controller, "setTarget", d.player, d._coordinateHandle(d.coords(current_target)))
        d.record(
            {
                "naturalMonolithDeparture": source_name,
                "origin": origin,
                "destination": destination,
                "target": target_name,
            }
        )
        return True
    finally:
        d._marches_departing_monolith = False


def walk(d, name, adjacent=False):
    def afterApproachTick():
        afterCombat(d)
        if leaveIncidentalMonolith(d, name):
            afterCombat(d)

    afterCombat(d)
    d.navigateTo(name, adjacent=adjacent, after_tick=afterApproachTick)
    afterCombat(d)


def fight(d, name):
    actor = d.object(name)
    d.test.assertTrue(d.call(actor, "isAlive"), name)
    experience = d.call(d.player, "getNumericProperty", "exp")
    afterCombat(d)
    if d.object(name, required=False) is not None:
        walk(d, name)
    d.test.assertIsNone(d.object(name, required=False), f"Enemy survived: {name}")
    d.test.assertFalse(d.call(actor, "isAlive"), "Despawn is not a combat victory")
    d.test.assertGreater(d.call(d.player, "getNumericProperty", "exp"), experience)
    d.combats += 1


def start(d):
    d.startMap("ninemarches")
    if d.object("ninemarchesStart", required=False):
        if d.coords() == d.coords(d.object("ninemarchesStart")):
            d.revisit("ninemarchesStart")
        else:
            walk(d, "ninemarchesStart")
    d.test.assertIn("ninemarchesQuest", d.questNames())
    before = {item["__handle__"] for item in d.call(d.player, "getItems")}
    walk(d, "townPortalScroll")
    d.test.assertIsNone(d.object("townPortalScroll", required=False))
    collected = [item for item in d.call(d.player, "getItems") if item["__handle__"] not in before]
    d.test.assertEqual(1, len(collected), "Preparation must collect exactly the authored nearby scroll")
    d.test.assertEqual("TownPortalScroll", d.call(collected[0], "getTypeId"))
    d._marches_retreat_scroll_name = d.call(collected[0], "getName")


def recruit(d, companion, *, item_first=False):
    actor, dialog, cache, item, gift = COMPANIONS[companion]
    if item_first:
        walk(d, cache)
        d.test.assertEqual(1, d.count(item))
    walk(d, actor)
    d.test.assertTrue(d.condition(dialog, "not_met"))
    # Leaving the authored offer does not silently accept the companion's quest.
    d.select(dialog, "ENTRY", 0)
    d.select(dialog, "OFFER", 1)
    d.test.assertFalse(d.flag(companion + "_started"))
    d.choose(dialog, "start")
    d.select(dialog, "ACCEPTED", 0)
    if not item_first:
        d.test.assertTrue(d.condition(dialog, "questInProgress"))
        d.select(dialog, "ENTRY", 4)
        d.select(dialog, "REMINDER", 0)
        walk(d, cache)
        d.test.assertEqual(1, d.count(item))
        d.revisit(cache)
        d.test.assertEqual(1, d.count(item))
        walk(d, actor)
    d.test.assertTrue(d.condition(dialog, "can_recruit"))
    before_rep = d.call(d.player, "getNumericProperty", "reputation")
    before_gift = d.count(gift)
    d.choose(dialog, "recruit", condition="can_recruit")
    d.select(dialog, "JOINED", 0)
    d.test.assertEqual(before_rep + 2, d.call(d.player, "getNumericProperty", "reputation"))
    d.test.assertEqual(before_gift + 1, d.count(gift))
    d.test.assertIn(companion + "Quest", d.questNames(completed=True))
    d.test.assertFalse(d.condition(dialog, "can_recruit"))
    verifyJournals(d)
    return actor, dialog, gift


def companionRoute(d, companion, item_first):
    start(d)
    actor, dialog, gift = recruit(d, companion, item_first=item_first)
    d.choose(dialog, "banter", condition="is_joined")
    d.select(dialog, "LOYAL", 0)
    d.check(f"ninemarches.companion.{companion}.loyal", d.condition(dialog, "is_joined"))
    d.check(f"ninemarches.companion.{companion}.{'itemFirst' if item_first else 'questFirst'}", d.count(gift) == 1)
    d.saveAndReload(f"{companion}-joined")
    walk(d, actor)
    d.check(f"ninemarches.companion.{companion}.persisted", d.condition(dialog, "is_joined") and d.count(gift) == 1)


def negativeReputationRoute(d, companion, leaves):
    start(d)
    actor, dialog, gift = recruit(d, companion)
    reputation = d.call(d.player, "getNumericProperty", "reputation")
    d.test.assertEqual(-5 if leaves else -4, reputation)
    d.choose(dialog, "banter", condition="is_joined")
    d.select(dialog, "GONE" if leaves else "LOYAL", 0)
    d.check(
        f"ninemarches.companion.{companion}.{'leftAtMinusFive' if leaves else 'loyalAtMinusFour'}",
        d.condition(dialog, "has_left") == leaves and d.condition(dialog, "is_joined") != leaves,
        reputation=reputation,
    )
    d.test.assertFalse(d.condition(dialog, "can_recruit"))
    d.saveAndReload(f"{companion}-negative-reputation")
    walk(d, actor)
    d.test.assertEqual(leaves, d.condition(dialog, "has_left"))
    d.test.assertEqual(1, d.count(gift))
    if leaves:
        d.select(dialog, "ENTRY", 3)
        d.select(dialog, "GONE", 0)


def corvynDeparture(d):
    start(d)
    actor, dialog, gift = recruit(d, "corvyn")
    recruit(d, "halda")
    walk(d, actor)
    d.test.assertEqual(4, d.call(d.player, "getNumericProperty", "reputation"))
    d.choose(dialog, "banter", condition="is_joined")
    d.select(dialog, "LOYAL", 0)
    d.check("ninemarches.companion.corvyn.loyalAtFour", d.condition(dialog, "is_joined"))
    walk(d, "witchHut")
    d.test.assertEqual(5, d.call(d.player, "getNumericProperty", "reputation"))
    walk(d, actor)
    d.choose(dialog, "banter", condition="is_joined")
    d.select(dialog, "GONE", 0)
    d.check("ninemarches.companion.corvyn.leftAtFive", d.condition(dialog, "has_left"))
    d.test.assertFalse(d.condition(dialog, "is_joined"))
    d.test.assertFalse(d.condition(dialog, "can_recruit"))
    d.select(dialog, "ENTRY", 3)
    d.select(dialog, "GONE", 0)
    d.saveAndReload("corvyn-departed")
    walk(d, actor)
    d.check("ninemarches.companion.corvyn.departurePersisted", d.condition(dialog, "has_left") and d.count(gift) == 1)


def gates(d):
    for color, cache, threshold, gate, chapter in GATES:
        walk(d, threshold)
        d.test.assertFalse(d.flag(color + "_gate_open"))
        d.test.assertIsNotNone(d.object(gate))
        walk(d, cache)
        d.test.assertEqual(1, d.count(color + "Key"))
        d.revisit(cache)
        d.test.assertEqual(1, d.count(color + "Key"))
        walk(d, threshold)
        d.check(
            f"ninemarches.gate.{color}.opensWithKey",
            d.flag(color + "_gate_open") and d.object(gate, required=False) is None,
        )
        d.test.assertGreaterEqual(d.number("chapter"), chapter)
        d.test.assertEqual(1, d.count(color + "Key"))
        d.revisit(threshold)
        d.test.assertTrue(d.flag(color + "_gate_open"))


def gateRoute(d):
    start(d)
    gates(d)
    d.saveAndReload("marches-three-open-gates")
    for color, _cache, _threshold, gate, _chapter in GATES:
        d.test.assertTrue(d.flag(color + "_gate_open"))
        d.test.assertIsNone(d.object(gate, required=False))
    d.check("ninemarches.gates.persisted", all(d.count(color + "Key") == 1 for color, *_ in GATES))


def sites(d):
    start(d)
    for name, flag, amount in (("learningStone", "shrine_used", 120), ("goldMine", "mine_claimed", 500)):
        target = d.object(name)
        if name == "goldMine":
            # The configured mine amount is authoritative; do not copy a balance constant.
            amount = d.call(target, "getNumericProperty", "value")
        walk(d, name, adjacent=True)
        d.test.assertFalse(d.flag(flag), "The first-claim witness must precede actual entry")
        origin = d.coords()
        gold = d.gold()
        destination = d.coords(target)
        d.step(destination)
        d.test.assertTrue(d.flag(flag))
        d.test.assertEqual(gold + amount, d.gold())
        claimed_gold = d.gold()
        d.step(origin)
        d.step(destination)
        d.test.assertEqual(claimed_gold, d.gold())
        d.check(f"ninemarches.site.{name}.once", d.flag(flag))
    d.test.assertTrue(d.flag("CAN_CRAFT_SCROLLS"))
    reputation = d.call(d.player, "getNumericProperty", "reputation")
    walk(d, "witchHut")
    d.test.assertEqual(reputation + 1, d.call(d.player, "getNumericProperty", "reputation"))
    d.revisit("witchHut")
    d.check("ninemarches.site.witchHut.once", d.call(d.player, "getNumericProperty", "reputation") == reputation + 1)
    for chest in ("chestFields", "chestFen", "chestBarrows", "chestAsh", "chestCoast", "chestCold"):
        handle = d.object(chest)
        walk(d, chest)
        d.test.assertTrue(d.call(handle, "getBoolProperty", "looted"))
        before = (d.gold(), {item["__handle__"] for item in d.call(d.player, "getItems")})
        d.revisit(chest)
        d.test.assertEqual(before, (d.gold(), {item["__handle__"] for item in d.call(d.player, "getItems")}))
        d.check(f"ninemarches.chest.{chest}.once", True)


def portals(d):
    start(d)
    for source, target in (
        ("monolithHub", "monolithCoast"),
        ("monolithCoast", "monolithHub"),
        ("monolithAsh", "monolithCold"),
        ("monolithCold", "monolithAsh"),
    ):
        afterCombat(d)
        destination = d.coords(d.object(target))
        if d.coords() == d.coords(d.object(source)):
            d.revisit(source)
        else:
            d.navigateTo(source, after_tick=lambda: afterCombat(d))
        d.check(f"ninemarches.portal.{source}", d.coords() == destination, destination=destination)
    afterCombat(d)


def reputationDialog(d, low=False):
    start(d)
    walk(d, "mayorHall")
    if low:
        d.test.assertTrue(d.condition("mayorDialog", "low_reputation"))
        d.select("mayorDialog", "ENTRY", 1)
        d.select("mayorDialog", "LOW", 0)
        d.check("ninemarches.mayor.low", not d.condition("mayorDialog", "high_reputation"))
        return
    d.test.assertTrue(d.condition("mayorDialog", "steady_reputation"))
    d.select("mayorDialog", "ENTRY", 2)
    d.select("mayorDialog", "STEADY", 0)
    d.check("ninemarches.mayor.steady", not d.condition("mayorDialog", "low_reputation"))
    d.select("mayorDialog", "ENTRY", 3)
    d.select("mayorDialog", "LORE", 0)
    walk(d, "gravewatchTavern")
    d.select("tavernDialog", "ENTRY", 0)
    d.select("tavernDialog", "RUMORS", 0)
    d.select("tavernDialog", "ENTRY", 1)
    d.select("tavernDialog", "HIRING", 0)
    recruit(d, "halda")
    walk(d, "witchHut")
    walk(d, "mayorHall")
    d.test.assertEqual(3, d.call(d.player, "getNumericProperty", "reputation"))
    d.select("mayorDialog", "ENTRY", 0)
    d.select("mayorDialog", "HIGH", 0)
    d.check("ninemarches.mayor.high", d.condition("mayorDialog", "high_reputation"))


def serviceRoute(d):
    start(d)
    verifyWaypointPublication(d)
    navigate = partial(walk, d)
    readSignpost(d, "gravewatchSign", navigate=navigate)
    marketAttempt(d, "gravewatchBarter", "ninemarches.market.insufficientGold", purchased=False, navigate=navigate)
    options = openStation(d, "gravewatchScribe", "ninemarches.crafting.gravewatchScribe.opened", navigate=navigate)
    d.test.assertEqual(
        {"craft_town_portal_scroll", "scribe_emergency_portal_scroll"}, {option["id"] for option in options}
    )
    d.test.assertTrue(all(option["enabled"] is False and "Locked" in option["detail"] for option in options))
    d.test.assertTrue(all("Study Gravewatch's learning stone" in option["detail"] for option in options))
    for recipe_id in ("craft_town_portal_scroll", "scribe_emergency_portal_scroll"):
        recipeAttempt(
            d,
            "gravewatchScribe",
            recipe_id,
            f"ninemarches.crafting.{recipe_id}.locked",
            outcome="locked",
            navigate=navigate,
        )
    walk(d, "learningStone")
    d.test.assertTrue(d.flag("CAN_CRAFT_SCROLLS"))
    options = openStation(d, "gravewatchScribe", navigate=navigate)
    d.test.assertTrue(all("Locked" not in option["detail"] for option in options))
    for recipe_id in ("craft_town_portal_scroll", "scribe_emergency_portal_scroll"):
        recipeAttempt(
            d,
            "gravewatchScribe",
            recipe_id,
            f"ninemarches.crafting.{recipe_id}.missingIngredients",
            outcome="missingIngredients",
            navigate=navigate,
        )
    _actor, _dialog, gift = recruit(d, "halda")
    if d._marches_retreat_scroll_name is not None:
        retreatWithOwnedScroll(d)
    else:
        d.test.assertIn(
            "ninemarches.scroll.retreat", d.branches, "The actual original scroll retreat witness is required"
        )
    earned = [item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == gift]
    d.test.assertEqual(1, len(earned))
    walk(d, "gravewatchBarter")
    d.sellAt("gravewatchBarter", earned[0])
    parchment = marketAttempt(
        d,
        "gravewatchBarter",
        "ninemarches.market.purchased",
        purchased=True,
        navigate=navigate,
    )
    d.test.assertEqual("Scroll", d.call(parchment, "getTypeId"))
    d.buyAt("gravewatchBarter", "ManaPotion")
    recipeAttempt(
        d,
        "gravewatchScribe",
        "craft_town_portal_scroll",
        "ninemarches.crafting.craft_town_portal_scroll.success",
        outcome="success",
        navigate=navigate,
    )


def finale(d, allies):
    start(d)
    walk(d, "digSite")
    d.test.assertFalse(d.flag("crown_taken"))
    d.check("ninemarches.dig.deniedWithoutSigils", d.count("ninefoldCrown") == 0)
    gates(d)
    if allies:
        for companion in COMPANIONS:
            recruit(d, companion)
    for index, name in enumerate(OBELISKS, 1):
        walk(d, name)
        d.test.assertEqual(index, d.number("obelisks_read"))
        d.revisit(name)
        d.test.assertEqual(index, d.number("obelisks_read"))
        d.check(f"ninemarches.obelisk.{name}.once", True)
        if index == 5:
            walk(d, "digSite")
            d.check("ninemarches.dig.deniedAtFive", not d.flag("crown_taken") and d.count("ninefoldCrown") == 0)
    walk(d, "digSite")
    d.check("ninemarches.dig.crownAndKing", d.count("ninefoldCrown") == 1 and d.flag("boss_woken"))
    d.test.assertNotIn("ninemarchesQuest", d.questNames(completed=True))
    verifyJournals(d)
    d.test.assertEqual(4, d.number("chapter"))
    d.saveAndReload("ninefold-crown-before-king")
    fight(d, "theNinefoldKingBoss")
    d.test.assertTrue(d.flag("boss_defeated"))
    d.test.assertIn("ninemarchesQuest", d.questNames(completed=True))
    verifyJournals(d)
    d.revisit("digSite")
    d.test.assertEqual(1, d.count("ninefoldCrown"))
    d.test.assertIsNone(d.object("theNinefoldKingBoss", required=False))
    branch = "ninemarches.finale.withAllies" if allies else "ninemarches.finale.solo"
    d.check(branch, d.flag("crown_taken") and d.flag("boss_defeated"))


def regionalCombat(d, *, start_new=True):
    if start_new:
        start(d)
    document = json.loads((Path(__file__).resolve().parents[1] / "res/maps/ninemarches/map.json").read_text())
    groups = {
        item["type"]: item["name"]
        for layer in document["layers"]
        if layer["type"] == "objectgroup"
        for item in layer["objects"]
        if item.get("name")
        and item["type"]
        in (
            "fieldsGuard",
            "fenGuard",
            "barrowsGuard",
            "ashGuard",
            "coastGuard",
            "coldGuard",
            "citadelDwelling",
            "wildEncounter",
        )
    }
    types = {
        "fieldsGuard": "fieldRaider",
        "fenGuard": "fenGhoul",
        "barrowsGuard": "barrowKnight",
        "ashGuard": "ashCultist",
        "coastGuard": "deepSpawn",
        "coldGuard": "coldHorror",
        "citadelDwelling": "citadelPriest",
        "wildEncounter": "fenGhoul",
    }
    for family, name in groups.items():
        center = d.coords(d.object(name))
        walk(d, name, adjacent=True)
        experience = d.call(d.player, "getNumericProperty", "exp")
        d.step(center)
        d.test.assertIsNone(d.object(name, required=False))
        enemies = [
            actor
            for actor in d.call(d.game_map, "getObjects")
            if d.call(actor, "getTypeId") == types[family]
            and sum(abs(a - b) for a, b in zip(d.coords(actor), center)) <= 12
        ]
        d.test.assertTrue(enemies, f"The authored {family} must actually summon opponents")
        for enemy in enemies:
            enemy_name = d.call(enemy, "getName")
            if d.object(enemy_name, required=False):
                fight(d, enemy_name)
        d.check(f"ninemarches.combat.{family}", d.call(d.player, "getNumericProperty", "exp") > experience)


def case(case_id, branches, run, **kwargs):
    return RouteCase(case_id, "ninemarches", ("ninemarches",), tuple(branches), run, sources=SOURCES, **kwargs)


GATE_BRANCHES = tuple(f"ninemarches.gate.{color}.opensWithKey" for color, *_ in GATES)
OBELISK_BRANCHES = tuple(f"ninemarches.obelisk.{name}.once" for name in OBELISKS)
CASES = (
    case(
        "ninemarches_services",
        (
            "ninemarches.market.insufficientGold",
            "ninemarches.market.purchased",
            "ninemarches.scroll.retreat",
            "ninemarches.signpost.read",
            "ninemarches.signpost.repeat",
            "ninemarches.waypoint.published",
            "ninemarches.cave.timedSpawn",
            "ninemarches.cave.exhausted",
            "ninemarches.crafting.gravewatchScribe.opened",
            "ninemarches.crafting.craft_town_portal_scroll.locked",
            "ninemarches.crafting.craft_town_portal_scroll.missingIngredients",
            "ninemarches.crafting.craft_town_portal_scroll.success",
            "ninemarches.crafting.scribe_emergency_portal_scroll.locked",
            "ninemarches.crafting.scribe_emergency_portal_scroll.missingIngredients",
        ),
        serviceRoute,
        duration_seconds=1200.0,
    ),
    *(
        case(
            f"ninemarches_{companion}_{order}",
            (
                f"ninemarches.companion.{companion}.loyal",
                f"ninemarches.companion.{companion}.{order}",
                f"ninemarches.companion.{companion}.persisted",
            ),
            partial(companionRoute, companion=companion, item_first=first),
        )
        for companion in COMPANIONS
        for order, first in (("questFirst", False), ("itemFirst", True))
    ),
    *(
        case(
            f"ninemarches_{companion}_{'leaves' if leaves else 'stays'}",
            (f"ninemarches.companion.{companion}.{'leftAtMinusFive' if leaves else 'loyalAtMinusFour'}",),
            partial(negativeReputationRoute, companion=companion, leaves=leaves),
            initial_reputation=-7 if leaves else -6,
        )
        for companion in ("halda", "morrigane")
        for leaves in (False, True)
    ),
    case(
        "ninemarches_corvyn_departure",
        (
            "ninemarches.companion.corvyn.loyalAtFour",
            "ninemarches.companion.corvyn.leftAtFive",
            "ninemarches.companion.corvyn.departurePersisted",
        ),
        corvynDeparture,
    ),
    case("ninemarches_three_gates", (*GATE_BRANCHES, "ninemarches.gates.persisted"), gateRoute),
    case(
        "ninemarches_sites",
        tuple(f"ninemarches.site.{name}.once" for name in ("learningStone", "goldMine", "witchHut"))
        + tuple(
            f"ninemarches.chest.{name}.once"
            for name in ("chestFields", "chestFen", "chestBarrows", "chestAsh", "chestCoast", "chestCold")
        ),
        sites,
    ),
    case(
        "ninemarches_portals",
        tuple(f"ninemarches.portal.{name}" for name in ("monolithHub", "monolithCoast", "monolithAsh", "monolithCold")),
        portals,
    ),
    case("ninemarches_mayor_earned", ("ninemarches.mayor.steady", "ninemarches.mayor.high"), reputationDialog),
    case(
        "ninemarches_mayor_low", ("ninemarches.mayor.low",), partial(reputationDialog, low=True), initial_reputation=-3
    ),
    *(
        case(
            f"ninemarches_finale_{'allies' if allies else 'solo'}",
            (
                *GATE_BRANCHES,
                *OBELISK_BRANCHES,
                "ninemarches.dig.deniedWithoutSigils",
                "ninemarches.dig.deniedAtFive",
                "ninemarches.dig.crownAndKing",
                "ninemarches.finale.withAllies" if allies else "ninemarches.finale.solo",
            ),
            partial(finale, allies=allies),
            duration_seconds=1200.0,
        )
        for allies in (False, True)
    ),
    case(
        "ninemarches_regional_combat",
        tuple(
            f"ninemarches.combat.{name}"
            for name in (
                "fieldsGuard",
                "fenGuard",
                "barrowsGuard",
                "ashGuard",
                "coastGuard",
                "coldGuard",
                "citadelDwelling",
                "wildEncounter",
            )
        ),
        regionalCombat,
        duration_seconds=1200.0,
    ),
)
