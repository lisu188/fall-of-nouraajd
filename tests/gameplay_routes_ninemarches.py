# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored Nine Marches routes; combat, loot and reputation come from play."""

from functools import partial
import json
from pathlib import Path

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_branch_journals import verifyJournals

SOURCES = ("res/maps/ninemarches/script.py", "res/maps/ninemarches/config.json", "res/maps/ninemarches/dialog.json")
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


def start(d):
    d.startMap("ninemarches")
    if d.object("ninemarchesStart", required=False):
        if d.coords() == d.coords(d.object("ninemarchesStart")):
            d.revisit("ninemarchesStart")
        else:
            d.navigateTo("ninemarchesStart")
    d.test.assertIn("ninemarchesQuest", d.questNames())


def recruit(d, companion, *, item_first=False):
    actor, dialog, cache, item, gift = COMPANIONS[companion]
    if item_first:
        d.navigateTo(cache)
        d.test.assertEqual(1, d.count(item))
    d.navigateTo(actor)
    d.test.assertTrue(d.condition(dialog, "not_met"))
    # Leaving the authored offer does not silently accept the companion's quest.
    d.select(dialog, "ENTRY", 0)
    d.select(dialog, "OFFER", 1)
    d.test.assertFalse(d.flag(companion + "_started"))
    d.choose(dialog, "start")
    if not item_first:
        d.test.assertTrue(d.condition(dialog, "questInProgress"))
        d.select(dialog, "ENTRY", 4)
        d.navigateTo(cache)
        d.test.assertEqual(1, d.count(item))
        d.revisit(cache)
        d.test.assertEqual(1, d.count(item))
        d.navigateTo(actor)
    d.test.assertTrue(d.condition(dialog, "can_recruit"))
    before_rep = d.call(d.player, "getNumericProperty", "reputation")
    before_gift = d.count(gift)
    d.choose(dialog, "recruit", condition="can_recruit")
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
    d.check(f"ninemarches.companion.{companion}.loyal", d.condition(dialog, "is_joined"))
    d.check(f"ninemarches.companion.{companion}.{'itemFirst' if item_first else 'questFirst'}", d.count(gift) == 1)
    d.saveAndReload(f"{companion}-joined")
    d.navigateTo(actor)
    d.check(f"ninemarches.companion.{companion}.persisted", d.condition(dialog, "is_joined") and d.count(gift) == 1)


def negativeReputationRoute(d, companion, leaves):
    start(d)
    actor, dialog, gift = recruit(d, companion)
    reputation = d.call(d.player, "getNumericProperty", "reputation")
    d.test.assertEqual(-5 if leaves else -4, reputation)
    d.choose(dialog, "banter", condition="is_joined")
    d.check(
        f"ninemarches.companion.{companion}.{'leftAtMinusFive' if leaves else 'loyalAtMinusFour'}",
        d.condition(dialog, "has_left") == leaves and d.condition(dialog, "is_joined") != leaves,
        reputation=reputation,
    )
    d.test.assertFalse(d.condition(dialog, "can_recruit"))
    d.saveAndReload(f"{companion}-negative-reputation")
    d.navigateTo(actor)
    d.test.assertEqual(leaves, d.condition(dialog, "has_left"))
    d.test.assertEqual(1, d.count(gift))
    if leaves:
        d.select(dialog, "ENTRY", 3)


def corvynDeparture(d):
    start(d)
    actor, dialog, gift = recruit(d, "corvyn")
    recruit(d, "halda")
    d.navigateTo(actor)
    d.test.assertEqual(4, d.call(d.player, "getNumericProperty", "reputation"))
    d.choose(dialog, "banter", condition="is_joined")
    d.check("ninemarches.companion.corvyn.loyalAtFour", d.condition(dialog, "is_joined"))
    d.navigateTo("witchHut")
    d.test.assertEqual(5, d.call(d.player, "getNumericProperty", "reputation"))
    d.navigateTo(actor)
    d.choose(dialog, "banter", condition="is_joined")
    d.check("ninemarches.companion.corvyn.leftAtFive", d.condition(dialog, "has_left"))
    d.test.assertFalse(d.condition(dialog, "is_joined"))
    d.test.assertFalse(d.condition(dialog, "can_recruit"))
    d.select(dialog, "ENTRY", 3)
    d.saveAndReload("corvyn-departed")
    d.navigateTo(actor)
    d.check("ninemarches.companion.corvyn.departurePersisted", d.condition(dialog, "has_left") and d.count(gift) == 1)


def gates(d):
    for color, cache, threshold, gate, chapter in GATES:
        d.navigateTo(threshold)
        d.test.assertFalse(d.flag(color + "_gate_open"))
        d.test.assertIsNotNone(d.object(gate))
        d.navigateTo(cache)
        d.test.assertEqual(1, d.count(color + "Key"))
        d.revisit(cache)
        d.test.assertEqual(1, d.count(color + "Key"))
        d.navigateTo(threshold)
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
        if name == "goldMine":
            # The configured mine amount is authoritative; do not copy a balance constant.
            amount = d.call(d.object(name), "getNumericProperty", "value")
        gold = d.gold()
        d.navigateTo(name)
        d.test.assertTrue(d.flag(flag))
        d.test.assertGreaterEqual(d.gold(), gold + amount)
        claimed_gold = d.gold()
        d.revisit(name)
        d.test.assertEqual(claimed_gold, d.gold())
        d.check(f"ninemarches.site.{name}.once", d.flag(flag))
    d.test.assertTrue(d.flag("CAN_CRAFT_SCROLLS"))
    reputation = d.call(d.player, "getNumericProperty", "reputation")
    d.navigateTo("witchHut")
    d.test.assertEqual(reputation + 1, d.call(d.player, "getNumericProperty", "reputation"))
    d.revisit("witchHut")
    d.check("ninemarches.site.witchHut.once", d.call(d.player, "getNumericProperty", "reputation") == reputation + 1)
    for chest in ("chestFields", "chestFen", "chestBarrows", "chestAsh", "chestCoast", "chestCold"):
        handle = d.object(chest)
        d.navigateTo(chest)
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
        destination = d.coords(d.object(target))
        d.navigateTo(source)
        d.check(f"ninemarches.portal.{source}", d.coords() == destination, destination=destination)


def reputationDialog(d, low=False):
    start(d)
    d.navigateTo("mayorHall")
    if low:
        d.test.assertTrue(d.condition("mayorDialog", "low_reputation"))
        d.select("mayorDialog", "ENTRY", 1)
        d.check("ninemarches.mayor.low", not d.condition("mayorDialog", "high_reputation"))
        return
    d.test.assertTrue(d.condition("mayorDialog", "steady_reputation"))
    d.select("mayorDialog", "ENTRY", 2)
    d.check("ninemarches.mayor.steady", not d.condition("mayorDialog", "low_reputation"))
    d.select("mayorDialog", "ENTRY", 3)
    d.navigateTo("gravewatchTavern")
    d.select("tavernDialog", "ENTRY", 0)
    d.select("tavernDialog", "ENTRY", 1)
    recruit(d, "halda")
    d.navigateTo("witchHut")
    d.navigateTo("mayorHall")
    d.test.assertEqual(3, d.call(d.player, "getNumericProperty", "reputation"))
    d.select("mayorDialog", "ENTRY", 0)
    d.check("ninemarches.mayor.high", d.condition("mayorDialog", "high_reputation"))


def finale(d, allies):
    start(d)
    d.navigateTo("digSite")
    d.test.assertFalse(d.flag("crown_taken"))
    d.check("ninemarches.dig.deniedWithoutSigils", d.count("ninefoldCrown") == 0)
    gates(d)
    if allies:
        for companion in COMPANIONS:
            recruit(d, companion)
    for index, name in enumerate(OBELISKS, 1):
        d.navigateTo(name)
        d.test.assertEqual(index, d.number("obelisks_read"))
        d.revisit(name)
        d.test.assertEqual(index, d.number("obelisks_read"))
        d.check(f"ninemarches.obelisk.{name}.once", True)
        if index == 5:
            d.navigateTo("digSite")
            d.check("ninemarches.dig.deniedAtFive", not d.flag("crown_taken") and d.count("ninefoldCrown") == 0)
    d.navigateTo("digSite")
    d.check("ninemarches.dig.crownAndKing", d.count("ninefoldCrown") == 1 and d.flag("boss_woken"))
    d.test.assertNotIn("ninemarchesQuest", d.questNames(completed=True))
    verifyJournals(d)
    d.test.assertEqual(4, d.number("chapter"))
    d.saveAndReload("ninefold-crown-before-king")
    d.fight("theNinefoldKingBoss")
    d.test.assertTrue(d.flag("boss_defeated"))
    d.test.assertIn("ninemarchesQuest", d.questNames(completed=True))
    verifyJournals(d)
    d.revisit("digSite")
    d.test.assertEqual(1, d.count("ninefoldCrown"))
    d.test.assertIsNone(d.object("theNinefoldKingBoss", required=False))
    branch = "ninemarches.finale.withAllies" if allies else "ninemarches.finale.solo"
    d.check(branch, d.flag("crown_taken") and d.flag("boss_defeated"))


def regionalCombat(d):
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
        d.navigateTo(name, adjacent=True)
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
                d.fight(enemy_name)
        d.check(f"ninemarches.combat.{family}", d.call(d.player, "getNumericProperty", "exp") > experience)


def case(case_id, branches, run, **kwargs):
    return RouteCase(case_id, "ninemarches", ("ninemarches",), tuple(branches), run, sources=SOURCES, **kwargs)


GATE_BRANCHES = tuple(f"ninemarches.gate.{color}.opensWithKey" for color, *_ in GATES)
OBELISK_BRANCHES = tuple(f"ninemarches.obelisk.{name}.once" for name in OBELISKS)
CASES = (
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
