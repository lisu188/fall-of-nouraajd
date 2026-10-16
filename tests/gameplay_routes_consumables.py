# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite quest-funded potion routes retain actual combat and item-use evidence."""

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_routes_maps import clearHostiles
from tests.gameplay_routes_nouraajd import SOURCES as NOURAAJD_SOURCES, prepareRolf, start, victorRoute
from tests.gameplay_routes_ninemarches import (
    SOURCES as MARCHES_SOURCES,
    prepareRegionalSupplies,
    regionalCombat,
    start as startMarches,
)
from tests.gameplay_routes_potions import preparePotionStock, requirePotionConsumptions

POTION_SOURCES = (
    "res/plugins/potion.py",
    "res/config/potions.json",
    "res/plugins/object.py",
    "src/object/CCreature.cpp",
)
VICTOR_BRANCHES = (
    "nouraajd.victor.countdownPersisted",
    "nouraajd.victor.approach.deescalated",
    "nouraajd.victor.entry.records",
    "nouraajd.victor.rescued",
    "nouraajd.victor.endingPersisted",
)
MARCHES_COMBAT_FAMILIES = (
    "fieldsGuard",
    "fenGuard",
    "barrowsGuard",
    "ashGuard",
    "coastGuard",
    "coldGuard",
    "citadelDwelling",
    "wildEncounter",
)


def nouraajdPotions(d):
    start(d, deed=False)
    prepareRolf(d)
    d.hunt("finishOriginalMainQuest")
    victorRoute(d, approach="deescalated", direct=False, saved=True, start_new=False, ask_girl=True)
    scrolls = [item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == "TownPortalScroll"]
    d.test.assertTrue(
        scrolls, "The actually collected nearby scroll can fund the remaining 100 gold after both quest rewards"
    )
    preparePotionStock(d, "market1", {scrolls[0]["__handle__"]})
    # Rolf preparation deliberately leaves this fixed original encounter unentered.
    d.test.assertIsNotNone(d.object("catacombs", required=False))
    d.navigateTo("catacombs")
    d.test.assertIsNone(d.object("catacombs", required=False))
    clearHostiles(d)
    requirePotionConsumptions(d)


def marchesPotions(d):
    startMarches(d)
    prepareRegionalSupplies(d, include_mana=True)
    regionalCombat(d, start_new=False)
    requirePotionConsumptions(d)


CASES = (
    RouteCase(
        "nouraajd_owned_potions",
        "nouraajd",
        ("nouraajd",),
        VICTOR_BRANCHES + ("nouraajd.potion.life.used", "nouraajd.potion.mana.used"),
        nouraajdPotions,
        campaign="fallOfNouraajd",
        sources=NOURAAJD_SOURCES + POTION_SOURCES,
        duration_seconds=1200.0,
    ),
    RouteCase(
        "ninemarches_owned_potions",
        "ninemarches",
        ("ninemarches",),
        tuple("ninemarches.combat." + family for family in MARCHES_COMBAT_FAMILIES)
        + ("ninemarches.potion.life.used", "ninemarches.potion.mana.used"),
        marchesPotions,
        sources=MARCHES_SOURCES + POTION_SOURCES,
        duration_seconds=1200.0,
    ),
)
