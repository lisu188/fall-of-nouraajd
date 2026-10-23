# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Candlekeep routes use native movement, authored choices and actual combat only."""

from functools import partial

from tests.gameplay_branch_types import RouteCase
from tests.candlekeep_source_branches import CONTAINERS, LOCKS as LOCKED_CONTAINERS, SOURCE_BRANCHES

QUESTS = ("firebead", "phlydia", "dreppin", "hull", "fuller", "reevor")
SOCIAL = (
    "parda",
    "karan",
    "imoen",
    "tethtoril",
    "thurston",
    "lovey",
    "nessa",
    "keeper",
    "watcher",
    "chanter",
    "voiceNorth",
    "voiceSouth",
    "voiceEast",
    "voiceWest",
) + tuple("tutor" + str(index) for index in range(1, 15))
SERVICES = (
    ("restBasic", 1, "peasant"),
    ("restMerchant", 3, "merchant"),
    ("restNoble", 5, "noble"),
    ("restRoyal", 8, "royal"),
    ("drinkBeer", 1, "Firewine"),
    ("drinkWine", 2, "Arabellan Dry Wine"),
    ("drinkAle", 1, "Bitter Black Ale"),
)
SOURCES = tuple("res/maps/candlekeep/" + name for name in ("script.py", "config.json", "dialog.json", "map.json"))


def visit(d, actor, action="talk"):
    d.navigateTo(actor)
    return d.choose(actor + "Dialog", action)


def resources(d):
    return (
        d.gold(),
        d.call(d.player, "getNumericProperty", "exp"),
        sorted(d.call(item, "getTypeId") for item in d.call(d.player, "getItems")),
    )


def clearWatch(d):
    guards = [
        d.call(actor, "getName")
        for actor in d.call(d.game_map, "getObjects")
        if d.call(actor, "getName").startswith("candlekeepWatch")
    ]
    for name in sorted(guards):
        if d.object(name, required=False):
            fightWithoutExperience(d, name)


def fightWithoutExperience(d, name):
    actor = d.object(name)
    d.assertNativeCombatOutcomes()
    before_seq = d._combat_trace_seq
    before = d.call(d.player, "getNumericProperty", "exp")
    d.navigateTo(name)
    d.test.assertIsNone(d.object(name, required=False), "The hostile must actually leave the map")
    d.test.assertFalse(d.call(actor, "isAlive"), "Despawning a living actor is not a native victory")
    d.test.assertEqual(before, d.call(d.player, "getNumericProperty", "exp"))
    d.assertNativeCombatOutcomes()
    victory = d.playerVictoryAgainst("candlekeep", name, after_seq=before_seq)
    d.test.assertIsNotNone(victory, "The zero-reward fight requires a new native player-victory receipt")
    participants = [victory.get("attacker", {}), *victory.get("opponents", ())]
    d.test.assertIn(name, [participant.get("name") for participant in participants])
    d.combats += 1


def accept(d, actor):
    d.navigateTo(actor)
    if actor == "dreppin" and d.string("candlekeep_dreppinStage") != "active":
        d.revisit(actor)
    if d.condition(actor + "Dialog", "canAcceptQuest"):
        d.choose(actor + "Dialog", "acceptQuest")
    d.check("candlekeep.quest." + actor + ".accept", actor + "Quest" in d.questNames())


def complete(d, actor):
    d.navigateTo(actor)
    before_gold, before_exp, _items = resources(d)
    high_reaction = actor in ("hull", "fuller") and d.condition(actor + "Dialog", "highReaction")
    d.choose(actor + "Dialog", "returnQuest")
    expected_gold = (
        (20 if high_reaction else 10)
        if actor == "hull"
        else 10 if actor == "fuller" and not high_reaction else 5 if actor == "reevor" else 0
    )
    d.test.assertEqual(before_gold + expected_gold, d.gold())
    d.test.assertEqual(before_exp + 50, d.call(d.player, "getNumericProperty", "exp"))
    d.check(
        "candlekeep.quest." + actor + ".complete",
        actor + "Quest" in d.questNames(completed=True) and actor + "Quest" not in d.questNames(),
    )
    before = resources(d)
    d.choose(actor + "Dialog", "talk", condition="questCompleted")
    d.check("candlekeep.quest." + actor + ".repeat", before == resources(d))


def container(d, actor, *, credit=True, force=False):
    d.navigateTo(actor)
    dialog = actor + "Dialog"
    if force:
        d.test.assertTrue(d.condition(dialog, "canForce"))
        d.choose(dialog, "forceContainer")
        clearWatch(d)
    elif d.condition(dialog, "canUnlock"):
        d.choose(dialog, "unlockContainer")
    elif d.condition(dialog, "canForce"):
        d.choose(dialog, "forceContainer")
        clearWatch(d)
    d.navigateTo(actor)
    before = resources(d)
    if d.condition(dialog, "canOpen"):
        contents = [item for item in d.call(d.object(actor), "getStringProperty", "contents").split(",") if item]
        counts = {item: d.count(item) for item in contents}
        before_gold = d.gold()
        expected_gold = d.call(d.object(actor), "getNumericProperty", "gold")
        permission = d.condition(dialog, "authorizedContainer")
        d.choose(dialog, "openContainer" if permission else "stealContainer")
        d.test.assertTrue(d.flag("candlekeepLooted_" + actor))
        d.test.assertEqual(before_gold + expected_gold, d.gold())
        for item in contents:
            d.test.assertEqual(counts[item] + contents.count(item), d.count(item))
        clearWatch(d)
    else:
        d.test.fail(("Successful container route still has a locked or empty container", actor))
    if credit:
        d.check(
            "candlekeep.containers." + actor,
            d.flag("candlekeepLooted_" + actor),
            before=before,
            after=resources(d),
        )


def prologue(d):
    d.startMap("candlekeep")
    for actor in QUESTS:
        accept(d, actor)
    visit(d, "tethtoril", "deliverScroll")
    container(d, "hullChest")
    container(d, "phlydiaHay")
    visit(d, "winthrop", "buyBolts")
    d.check("candlekeep.services.buyBolts", d.count("candlekeepBolts") == 1)
    for number in range(1, 6):
        if d.object("rat" + str(number), required=False):
            d.fight("rat" + str(number))
    for actor in QUESTS:
        complete(d, actor)
    d.saveAndReload("candlekeep-all-six-errands")
    for actor in ("shank", "carbos"):
        d.fight(actor)
        d.check("candlekeep.assassins." + actor, d.flag("candlekeep_" + actor + "Slain"))
    for actor in SOCIAL:
        visit(d, actor)
        d.check("candlekeep.social." + actor, d.flag("candlekeepTalked_" + actor))
    d.navigateTo("firebead")
    while d.number("candlekeepFirebeadConversations") < 30:
        d.revisit("firebead")
    d.check("candlekeep.social.firebeadRepeatedTalk", d.flag("candlekeepFirebeadThirtyTalks"))
    for action, cost, label in SERVICES:
        before = d.gold()
        visit(d, "winthrop", action)
        d.test.assertEqual(before - cost, d.gold())
        key = "candlekeepLastRoom" if action.startswith("rest") else "candlekeepLastDrink"
        d.check("candlekeep.services." + action, d.string(key) == label)
    before = d.count("candlekeepHealingPotion")
    visit(d, "clinicPriest", "declinePotion")
    d.check(
        "candlekeep.services.declinePotion",
        d.flag("candlekeepClinicGiftDeclined") and before == d.count("candlekeepHealingPotion"),
    )
    visit(d, "clinicPriest", "acceptPotion")
    d.check("candlekeep.services.acceptPotion", before + 1 == d.count("candlekeepHealingPotion"))
    before = d.count("candlekeepHealingPotion")
    visit(d, "templePriest", "buyHealingPotion")
    d.check("candlekeep.services.buyHealingPotion", before + 1 == d.count("candlekeepHealingPotion"))
    for action, cost in (("donate", 10),):
        before = d.gold()
        visit(d, "templePriest", action)
        d.check("candlekeep.services." + action, d.gold() == before - cost)
    before = resources(d)
    visit(d, "templePriest", "healAtTemple")
    d.check("candlekeep.services.healAtTemple.refused", before == resources(d))
    for actor, action, branch in (
        ("winthrop", "browseStock", "stockCancelled"),
        ("winthrop", "browseDrinks", "drinksCancelled"),
        ("templePriest", "browseServices", "servicesCancelled"),
        ("winthrop", "sellItem", "saleCancelled"),
    ):
        before = resources(d)
        visit(d, actor, action)
        d.check("candlekeep.services." + branch, before == resources(d))
    before_gold, before_count = d.gold(), d.number("candlekeepIdentifications")
    visit(d, "templePriest", "identifyItem")
    if "candlekeep.services.identifyItem" in d.case.branches:
        d.check(
            "candlekeep.services.identifyItem",
            d.number("candlekeepIdentifications") == before_count + 1 and d.gold() == before_gold - 100,
        )
    else:
        d.check(
            "candlekeep.services.identifyItem.refused",
            d.number("candlekeepIdentifications") == before_count and d.gold() == before_gold,
        )
    visit(d, "jondalar", "beginLesson")
    d.fight("jondalarPracticeFoe")
    d.check("candlekeep.social.jondalar", d.flag("candlekeepJondalarCompleted"))
    training(d, abandon=False, start=False)
    before = resources(d)
    visit(d, "gorion", "reviewPreparations")
    d.check(
        "candlekeep.social.preparations",
        before == resources(d) and all(actor + "Quest" in d.questNames(completed=True) for actor in QUESTS),
    )
    visit(d, "gorion", "refuseDeparture")
    d.check("candlekeep.departure.refuse", d.flag("candlekeepDepartureRefused") and not d.flag("candlekeepDeparted"))
    d.saveAndReload("candlekeep-before-departure")
    visit(d, "gorion", "leaveCandlekeep")
    d.check(
        "candlekeep.departure.complete",
        d.flag("candlekeepDeparted") and d.flag("candlekeepEpilogueShown") and d.map_name == "candlekeep",
    )


def training(d, abandon, start=True):
    if start:
        d.startMap("candlekeep")
    visit(d, "gatewarden", "acceptTraining")
    if "candlekeep.training.accept" in d.case.branches:
        d.check("candlekeep.training.accept", d.flag("candlekeepTrainingAccepted"))
    visit(d, "obe", "beginTraining")
    d.test.assertEqual("active", d.string("candlekeep_trainingStage"))
    if abandon:
        d.saveAndReload("candlekeep-training-active")
        visit(d, "obe", "forceExitTraining")
        d.check(
            "candlekeep.training.abandon",
            d.string("candlekeep_trainingStage") == "abandoned" and d.flag("candlekeepTrainingForcedExit"),
        )
        return
    for actor in ("arkanis", "canderous", "deder", "mordaine", "osprey"):
        visit(d, actor, "inspectCompanion")
        d.check("candlekeep.training.companion." + actor, d.flag("candlekeepTrainingParticipated_" + actor))
    before = resources(d)
    d.choose("ospreyDialog", "borrowEquipment")
    d.check("candlekeep.training.borrowCancelled", before == resources(d))
    for _round in range(2):
        if d.object("trainingFoe1", required=False):
            d.fight("trainingFoe1")
        d.waitTurns(
            80, lambda: all(d.object("trainingFoe" + str(number), required=False) is None for number in range(2, 7))
        )
        visit(d, "obe", "trainingRound")
    d.check(
        "candlekeep.training.complete",
        d.flag("candlekeepTrainingCompleted") and d.string("candlekeep_trainingStage") == "completed",
    )
    visit(d, "obe", "forceExitTraining")


def declines(d):
    d.startMap("candlekeep")
    visit(d, "gatewarden", "declineTraining")
    d.check(
        "candlekeep.training.declineOnce",
        d.number("candlekeepGatewardenDeclines") == 1 and not d.flag("candlekeepTrainingClosed"),
    )
    visit(d, "gatewarden", "closeTrainingGate")
    d.check(
        "candlekeep.training.declineTwice",
        d.number("candlekeepGatewardenDeclines") == 2 and d.flag("candlekeepTrainingClosed"),
    )
    d.saveAndReload("candlekeep-training-refused")
    d.test.assertTrue(d.flag("candlekeepTrainingClosed"))


def skilledTheft(d):
    d.startMap("candlekeep")
    visit(d, "gatewarden", "acceptTraining")
    d.navigateTo("hull")
    for actor in ("fuller", "phlydia", "clinicPriest"):
        d.navigateTo(actor)
        before_crimes = d.number("candlekeepCrimes")
        d.choose(actor + "Dialog", "pickPocket")
        d.check(
            "candlekeep.social." + actor + "Theft",
            d.flag("candlekeepStole_" + actor) and d.number("candlekeepCrimes") == before_crimes,
        )
        d.test.assertFalse(d.condition(actor + "Dialog", "canPickpocket"))
    d.test.assertEqual(1, d.count("candlekeepDaggerPlusOne"))
    for actor in CONTAINERS:
        container(d, actor)
    d.navigateTo("firebead")
    while d.number("candlekeepFirebeadConversations") < 30:
        d.revisit("firebead")
    before, count = d.gold(), d.number("candlekeepIdentifications")
    visit(d, "templePriest", "identifyItem")
    d.check(
        "candlekeep.services.identifyItem",
        d.gold() == before - 100 and d.number("candlekeepIdentifications") == count + 1,
    )
    d.saveAndReload("candlekeep-stolen-unique-items")
    d.test.assertEqual(1, d.count("candlekeepDaggerPlusOne"))


def forceSapphire(d):
    d.startMap("candlekeep")
    container(d, "innSapphireDrawer", credit=False, force=True)
    d.check(
        "candlekeep.containers.innSapphireDrawer.forced",
        d.call(d.object("innSapphireDrawer"), "getBoolProperty", "forced") and d.count("candlekeepStarSapphire") == 1,
    )


def lockedRefusals(d):
    d.startMap("candlekeep")
    visit(d, "gatewarden", "acceptTraining")
    for actor in LOCKED_CONTAINERS:
        d.navigateTo(actor)
        before = resources(d)
        d.test.assertFalse(d.condition(actor + "Dialog", "canUnlock"))
        d.test.assertFalse(d.condition(actor + "Dialog", "canForce"))
        d.check(
            "candlekeep.containers." + actor + ".locked",
            d.call(d.object(actor), "getBoolProperty", "locked") and before == resources(d),
        )


def optionalErrands(d):
    d.startMap("candlekeep")
    visit(d, "winthrop", "buyBolts")
    d.test.assertEqual(1, d.count("candlekeepBolts"))
    d.navigateTo("fuller")
    d.test.assertNotIn("fullerQuest", d.questNames())
    d.choose("fullerDialog", "acceptQuest")
    d.check(
        "candlekeep.quest.fuller.itemBeforeAccept", d.count("candlekeepBolts") == 1 and "fullerQuest" in d.questNames()
    )
    d.navigateTo("firebead")
    visit(d, "tethtoril", "deliverScroll")
    d.choose("tethtorilDialog", "keepScroll")
    d.check(
        "candlekeep.quest.firebead.keptScroll",
        d.count("candlekeepIdentifyScroll") == 1
        and "firebeadQuest" in d.questNames()
        and d.flag("candlekeepScrollKept"),
    )
    d.saveAndReload("candlekeep-optional-errands")
    visit(d, "gorion", "leaveCandlekeep")
    d.check(
        "candlekeep.departure.early",
        d.flag("candlekeepDeparted")
        and "firebeadQuest" in d.questNames()
        and "fullerQuest" in d.questNames()
        and not d.questNames(completed=True),
    )


def timedTraining(d):
    d.startMap("candlekeep")
    visit(d, "gatewarden", "acceptTraining")
    visit(d, "obe", "beginTraining")
    d.choose("obeDialog", "talk")
    d.saveAndReload("candlekeep-saved-training-timer")
    d.waitTurns(121, lambda: d.flag("candlekeepTrainingTimedOut"))
    d.check(
        "candlekeep.training.timedExit",
        d.flag("candlekeepTrainingTimedOut")
        and d.flag("candlekeepTrainingForcedExit")
        and d.string("candlekeep_trainingStage") == "abandoned",
    )


def crime(d):
    d.startMap("candlekeep")
    visit(d, "watcher", "attack")
    fightWithoutExperience(d, "watcher")
    d.check("candlekeep.crime.attack", d.flag("candlekeepGuardsAlerted") and d.flag("candlekeepMurder_watcher"))
    clearWatch(d)


def paidHealing(d):
    d.startMap("candlekeep")
    d.navigateTo("priestChest")
    d.test.assertTrue(d.condition("priestChestDialog", "canForce"))
    d.choose("priestChestDialog", "forceContainer")
    d.test.assertTrue(d.flag("candlekeepGuardsAlerted"))
    equipped = d.call(d.player, "getEquipped")
    weapon = equipped.get("0")
    armor = equipped.get("3")
    d.call(d.player, "equipItem", "0", None)
    d.call(d.player, "equipItem", "3", None)
    clearWatch(d)
    d.navigateTo("templePriest")
    before_hp = d.call(d.player, "getHp")
    maximum = d.call(d.player, "getHpMax")
    d.test.assertLess(before_hp, maximum, "The successful healing witness requires a real retained combat injury")
    before_gold = d.gold()
    d.choose("templePriestDialog", "healAtTemple")
    d.check(
        "candlekeep.services.healAtTemple",
        d.gold() == before_gold - 50 and d.call(d.player, "getHp") == maximum,
        beforeHp=before_hp,
    )
    if weapon is not None:
        d.call(d.player, "equipItem", "0", weapon)
    if armor is not None:
        d.call(d.player, "equipItem", "3", armor)


def refusedPurchaseAndTheft(d):
    d.startMap("candlekeep")
    before = resources(d)
    visit(d, "templePriest", "buyHealingPotion")
    d.check(
        "candlekeep.services.insufficientFunds",
        before == resources(d) and d.number("candlekeepStockBought_templePriest_POTN08") == 0,
    )
    d.navigateTo("fuller")
    before_crimes, before_daggers = d.number("candlekeepCrimes"), d.count("candlekeepDaggerPlusOne")
    d.choose("fullerDialog", "pickPocket")
    d.check(
        "candlekeep.social.failedTheft",
        d.number("candlekeepCrimes") == before_crimes + 1
        and d.flag("candlekeepGuardsAlerted")
        and d.count("candlekeepDaggerPlusOne") == before_daggers
        and not d.flag("candlekeepFullerDaggerClaimed"),
    )
    clearWatch(d)


def useOwned(d, item_id):
    items = [item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == item_id]
    d.test.assertEqual(1, len(items), item_id)
    d.call(d.player, "useItem", items[0])
    d.pump()


def scrolls(d):
    d.startMap("candlekeep")
    d.navigateTo("firebead")
    visit(d, "tethtoril", "deliverScroll")
    before = resources(d)
    useOwned(d, "candlekeepIdentifyScroll")
    d.check("candlekeep.scroll.identifyNoTarget", before == resources(d))
    visit(d, "fuller", "pickPocket")
    useOwned(d, "candlekeepIdentifyScroll")
    dagger = next(
        item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == "candlekeepDaggerPlusOne"
    )
    d.check(
        "candlekeep.scroll.identifyConsumed",
        d.count("candlekeepIdentifyScroll") == 0
        and not d.call(dagger, "getBoolProperty", "plugin_candlekeepUnidentified")
        and "firebeadQuest" in d.questNames(),
    )
    container(d, "innOffice", credit=False)
    useOwned(d, "candlekeepArmorScroll")
    effects = d.call(d.player, "getEffects")
    d.check(
        "candlekeep.scroll.armorConsumed",
        d.count("candlekeepArmorScroll") == 0
        and any(d.call(effect, "getTypeId") == "candlekeepArmorEffect" for effect in effects),
    )
    before = resources(d)
    useOwned(d, "candlekeepInfravisionScroll")
    d.check(
        "candlekeep.scroll.infravisionRetained", before == resources(d) and d.count("candlekeepInfravisionScroll") == 1
    )


CORE_BRANCHES = tuple(
    "candlekeep.quest." + actor + "." + outcome for actor in QUESTS for outcome in ("accept", "complete", "repeat")
)
CORE_BRANCHES += tuple("candlekeep.containers." + actor for actor in ("hullChest", "phlydiaHay"))
CORE_BRANCHES += tuple("candlekeep.social." + actor for actor in SOCIAL)
CORE_BRANCHES += tuple("candlekeep.services." + action for action, *_rest in SERVICES)
CORE_BRANCHES += tuple(
    "candlekeep.services." + action
    for action in ("buyBolts", "buyHealingPotion", "donate", "healAtTemple.refused", "acceptPotion", "declinePotion")
)
CORE_BRANCHES += tuple(
    "candlekeep.services." + action
    for action in ("stockCancelled", "drinksCancelled", "servicesCancelled", "saleCancelled")
)
CORE_BRANCHES += tuple(
    "candlekeep.training.companion." + actor for actor in ("arkanis", "canderous", "deder", "mordaine", "osprey")
)
CORE_BRANCHES += ("candlekeep.training.borrowCancelled",)
CORE_BRANCHES += ("candlekeep.social.preparations",)
CORE_BRANCHES += (
    "candlekeep.social.firebeadRepeatedTalk",
    "candlekeep.social.jondalar",
    "candlekeep.assassins.shank",
    "candlekeep.assassins.carbos",
    "candlekeep.training.accept",
    "candlekeep.training.complete",
    "candlekeep.departure.refuse",
    "candlekeep.departure.complete",
)

CASES = (
    RouteCase(
        "candlekeep-prologue",
        "candlekeep",
        ("candlekeep",),
        CORE_BRANCHES + ("candlekeep.services.identifyItem.refused",),
        prologue,
        classes=("Warrior", "Assasin", "Wayfarer"),
        sources=SOURCES,
        duration_seconds=480,
    ),
    RouteCase(
        "candlekeep-prologue-high-reaction",
        "candlekeep",
        ("candlekeep",),
        CORE_BRANCHES + ("candlekeep.services.identifyItem",),
        prologue,
        classes=("Sorcerer", "Inquisitor"),
        sources=SOURCES,
        duration_seconds=480,
    ),
    RouteCase(
        "candlekeep-training-declined",
        "candlekeep",
        ("candlekeep",),
        ("candlekeep.training.declineOnce", "candlekeep.training.declineTwice"),
        declines,
        classes=("Warrior",),
        sources=SOURCES,
        duration_seconds=30,
    ),
    RouteCase(
        "candlekeep-training-abandoned",
        "candlekeep",
        ("candlekeep",),
        ("candlekeep.training.accept", "candlekeep.training.abandon"),
        partial(training, abandon=True),
        classes=("Sorcerer",),
        sources=SOURCES,
        duration_seconds=60,
    ),
    RouteCase(
        "candlekeep-skilled-theft",
        "candlekeep",
        ("candlekeep",),
        tuple("candlekeep.containers." + actor for actor in CONTAINERS)
        + tuple("candlekeep.social." + actor + "Theft" for actor in ("fuller", "phlydia", "clinicPriest"))
        + ("candlekeep.services.identifyItem",),
        skilledTheft,
        classes=("Assasin",),
        race="wandererRace",
        sources=SOURCES,
        duration_seconds=300,
    ),
    RouteCase(
        "candlekeep-forced-sapphire",
        "candlekeep",
        ("candlekeep",),
        ("candlekeep.containers.innSapphireDrawer.forced",),
        forceSapphire,
        classes=("Warrior",),
        race="highlanderRace",
        sources=SOURCES,
        duration_seconds=60,
    ),
    RouteCase(
        "candlekeep-locked-refusals",
        "candlekeep",
        ("candlekeep",),
        tuple("candlekeep.containers." + actor + ".locked" for actor in LOCKED_CONTAINERS),
        lockedRefusals,
        classes=("Sorcerer",),
        sources=SOURCES,
        duration_seconds=90,
    ),
    RouteCase(
        "candlekeep-optional-errands",
        "candlekeep",
        ("candlekeep",),
        (
            "candlekeep.quest.fuller.itemBeforeAccept",
            "candlekeep.quest.firebead.keptScroll",
            "candlekeep.departure.early",
        ),
        optionalErrands,
        classes=("Wayfarer",),
        sources=SOURCES,
        duration_seconds=90,
    ),
    RouteCase(
        "candlekeep-training-timed-out",
        "candlekeep",
        ("candlekeep",),
        ("candlekeep.training.timedExit",),
        timedTraining,
        classes=("Inquisitor",),
        sources=SOURCES,
        duration_seconds=120,
    ),
    RouteCase(
        "candlekeep-crime",
        "candlekeep",
        ("candlekeep",),
        ("candlekeep.crime.attack",),
        crime,
        classes=("Warrior",),
        sources=SOURCES,
        duration_seconds=90,
    ),
    RouteCase(
        "candlekeep-paid-healing",
        "candlekeep",
        ("candlekeep",),
        ("candlekeep.services.healAtTemple",),
        paidHealing,
        classes=("Warrior",),
        sources=SOURCES,
        duration_seconds=90,
    ),
    RouteCase(
        "candlekeep-refused-actions",
        "candlekeep",
        ("candlekeep",),
        ("candlekeep.services.insufficientFunds", "candlekeep.social.failedTheft"),
        refusedPurchaseAndTheft,
        classes=("Sorcerer",),
        sources=SOURCES,
        duration_seconds=90,
    ),
    RouteCase(
        "candlekeep-scrolls",
        "candlekeep",
        ("candlekeep",),
        tuple(
            "candlekeep.scroll." + outcome
            for outcome in ("identifyNoTarget", "identifyConsumed", "armorConsumed", "infravisionRetained")
        ),
        scrolls,
        classes=("Assasin",),
        race="wandererRace",
        sources=SOURCES,
        duration_seconds=120,
    ),
)

DEFENSIVE_SOURCE_BRANCHES = {
    "res/maps/candlekeep/script.py:CandlekeepPortal.onDestroy": (
        "Removing a connector during teardown is a source/model ownership contract; native destruction proof is pending."
    ),
    "res/maps/candlekeep/script.py:CandlekeepTrainingDefeatTrigger.trigger": (
        "Hero death ends the restricted surviving-player route. Cleanup has a named source/model regression; "
        "a qualifying native defeat session is pending."
    ),
}

PENDING_GAMEPLAY_OBLIGATIONS = {
    "candlekeep.services.stockSelected": {
        "map": "candlekeep",
        "callback": "res/maps/candlekeep/script.py:CandlekeepDialog.browseStock",
        "reason": "Exact source stock rows have source/model purchase checks; the restricted headless driver cannot answer the native choice dialog. Selected GUI purchases remain pending.",
    },
    "candlekeep.services.drinkSelected": {
        "map": "candlekeep",
        "callback": "res/maps/candlekeep/script.py:CandlekeepDialog.browseDrinks",
        "reason": "All source drinks are selectable in the game UI; a native receipt for every selected drink row is pending.",
    },
    "candlekeep.services.serviceSelected": {
        "map": "candlekeep",
        "callback": "res/maps/candlekeep/script.py:CandlekeepDialog.browseServices",
        "reason": "All source temple services have model checks; selected GUI-service native receipts are pending.",
    },
    "candlekeep.services.saleSelected": {
        "map": "candlekeep",
        "callback": "res/maps/candlekeep/script.py:CandlekeepDialog.sellItem",
        "reason": "Native item selection for a successful sale remains pending outside the restricted headless choice surface; cancellation is separately witnessed.",
    },
    "candlekeep.training.borrowSelected": {
        "map": "candlekeep",
        "callback": "res/maps/candlekeep/script.py:CandlekeepDialog.borrowEquipment",
        "reason": "Temporary-loan cleanup is source/model tested; selecting actual companion equipment through the native GUI remains pending.",
    },
}
