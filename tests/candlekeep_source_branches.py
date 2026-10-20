# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reviewed callback-to-route obligations, not evidence that a route has passed."""

SOURCE = "res/maps/candlekeep/script.py:"
QUESTS = ("firebead", "phlydia", "dreppin", "hull", "fuller", "reevor")
CONTAINERS = (
    "hullChest",
    "phlydiaHay",
    "innOffice",
    "innSapphireDrawer",
    "innClarityDrawer",
    "innJewelryDrawer",
    "priestChest",
    "northwestBarrel",
    "bunkhouseBarrel",
    "clinicDesk",
    "barracksChest1",
    "barracksChest2",
    "barracksChest3",
    "barracksChest4",
    "innKitchen",
    "innSilverDrawer",
    "innCoinDrawer",
    "priestEmpty1",
    "priestTable",
    "priestCrates",
    "priestEmpty2",
    "barracksBarrel",
    "courtyardEmpty1",
    "courtyardEmpty2",
    "storehouseEmpty1",
    "storehouseEmpty2",
    "bunkhouseEmpty",
) + tuple("trainingChest" + str(index) for index in range(1, 11))
LOCKS = (
    "innOffice",
    "innSapphireDrawer",
    "innClarityDrawer",
    "innJewelryDrawer",
    "clinicDesk",
    "barracksChest1",
    "barracksChest2",
    "barracksChest3",
    "barracksChest4",
    "innSilverDrawer",
    "priestChest",
    "trainingChest5",
    "trainingChest8",
)
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
ACCEPT = tuple("candlekeep.quest." + actor + ".accept" for actor in QUESTS)
COMPLETE = tuple("candlekeep.quest." + actor + ".complete" for actor in QUESTS)
REPEAT = tuple("candlekeep.quest." + actor + ".repeat" for actor in QUESTS)
LOOT = tuple("candlekeep.containers." + actor for actor in CONTAINERS)
LOCKED = tuple("candlekeep.containers." + actor + ".locked" for actor in LOCKS)
THEFT = tuple("candlekeep.social." + actor + "Theft" for actor in ("fuller", "phlydia", "clinicPriest"))
TRAINING_END = ("candlekeep.training.complete", "candlekeep.training.abandon", "candlekeep.training.timedExit")
COMPANIONS = tuple(
    "candlekeep.training.companion." + actor for actor in ("arkanis", "canderous", "deder", "mordaine", "osprey")
)


SOURCE_BRANCHES = {
    SOURCE + "CandlekeepQuest.isCompleted": COMPLETE,
    SOURCE + "CandlekeepQuest.onComplete": COMPLETE,
    SOURCE + "CandlekeepStart.onEnter": ACCEPT,
    SOURCE + "CandlekeepPortal.onCreate": ("candlekeep.quest.reevor.complete", "candlekeep.social.thurston"),
    SOURCE + "CandlekeepPortal.onTurn": ("candlekeep.quest.reevor.complete", "candlekeep.social.thurston"),
    SOURCE + "CandlekeepPortal.onEnter": ("candlekeep.quest.reevor.complete", "candlekeep.social.thurston"),
    SOURCE + "CandlekeepContainer.onEnter": LOOT,
    SOURCE
    + "CandlekeepSpellScroll.onUse": tuple(
        "candlekeep.scroll." + outcome
        for outcome in ("identifyNoTarget", "identifyConsumed", "armorConsumed", "infravisionRetained")
    ),
    SOURCE + "CandlekeepPersonTrigger.trigger": ACCEPT + tuple("candlekeep.social." + actor for actor in SOCIAL),
    SOURCE
    + "CandlekeepDeathTrigger.trigger": (
        "candlekeep.assassins.shank",
        "candlekeep.assassins.carbos",
        "candlekeep.quest.reevor.complete",
        "candlekeep.social.jondalar",
        "candlekeep.training.complete",
        "candlekeep.crime.attack",
    ),
    SOURCE + "CandlekeepTrainingTimerTrigger.trigger": ("candlekeep.training.timedExit",),
}

# Dialog methods are listed individually so a newly authored callback requires a reviewed route obligation.
DIALOG_BRANCHES = {
    "canAcceptQuest": ACCEPT,
    "questActive": ACCEPT,
    "questCompleted": REPEAT,
    "canReturnQuest": COMPLETE,
    "acceptQuest": ACCEPT,
    "returnQuest": COMPLETE,
    "deliverScroll": ("candlekeep.quest.firebead.complete", "candlekeep.quest.firebead.keptScroll"),
    "keepScroll": ("candlekeep.quest.firebead.keptScroll",),
    "talk": REPEAT + tuple("candlekeep.social." + actor for actor in SOCIAL),
    "canPickpocket": THEFT + ("candlekeep.social.failedTheft",),
    "pickPocket": THEFT + ("candlekeep.social.failedTheft",),
    "countConversation": ("candlekeep.social.firebeadRepeatedTalk", "candlekeep.quest.dreppin.accept"),
    "beginLesson": ("candlekeep.social.jondalar",),
    "attack": ("candlekeep.crime.attack",),
    "authorizedContainer": LOOT,
    "canOpen": LOOT + LOCKED,
    "canUnlock": LOOT + LOCKED,
    "canForce": LOOT + LOCKED + ("candlekeep.containers.innSapphireDrawer.forced",),
    "unlockContainer": LOOT,
    "forceContainer": ("candlekeep.containers.innSapphireDrawer.forced",),
    "openContainer": ("candlekeep.containers.hullChest", "candlekeep.containers.phlydiaHay"),
    "stealContainer": LOOT,
    "browseStock": ("candlekeep.services.stockCancelled",),
    "browseDrinks": ("candlekeep.services.drinksCancelled",),
    "browseServices": ("candlekeep.services.servicesCancelled",),
    "sellItem": ("candlekeep.services.saleCancelled",),
    "buyBolts": ("candlekeep.services.buyBolts", "candlekeep.quest.fuller.itemBeforeAccept"),
    "buyHealingPotion": ("candlekeep.services.buyHealingPotion", "candlekeep.services.insufficientFunds"),
    "healAtTemple": ("candlekeep.services.healAtTemple", "candlekeep.services.healAtTemple.refused"),
    "restBasic": ("candlekeep.services.restBasic",),
    "restMerchant": ("candlekeep.services.restMerchant",),
    "restNoble": ("candlekeep.services.restNoble",),
    "restRoyal": ("candlekeep.services.restRoyal",),
    "drinkBeer": ("candlekeep.services.drinkBeer",),
    "drinkWine": ("candlekeep.services.drinkWine",),
    "drinkAle": ("candlekeep.services.drinkAle",),
    "donate": ("candlekeep.services.donate",),
    "identifyItem": ("candlekeep.services.identifyItem", "candlekeep.services.identifyItem.refused"),
    "acceptPotion": ("candlekeep.services.acceptPotion",),
    "declinePotion": ("candlekeep.services.declinePotion",),
    "trainingAvailable": ("candlekeep.training.accept", "candlekeep.training.declineOnce"),
    "acceptTraining": ("candlekeep.training.accept",),
    "declineTraining": ("candlekeep.training.declineOnce", "candlekeep.training.declineTwice"),
    "canDeclineSecond": ("candlekeep.training.declineOnce", "candlekeep.training.declineTwice"),
    "closeTrainingGate": ("candlekeep.training.declineTwice",),
    "beginTraining": ("candlekeep.training.accept",) + TRAINING_END,
    "trainingRound": ("candlekeep.training.complete",),
    "finishTraining": ("candlekeep.training.complete",),
    "forceExitTraining": ("candlekeep.training.complete", "candlekeep.training.abandon"),
    "inspectCompanion": COMPANIONS,
    "borrowEquipment": ("candlekeep.training.borrowCancelled",),
    "reviewPreparations": ("candlekeep.social.preparations",),
    "refuseDeparture": ("candlekeep.departure.refuse",),
    "leaveCandlekeep": ("candlekeep.departure.complete", "candlekeep.departure.early"),
}
SOURCE_BRANCHES.update(
    (SOURCE + "CandlekeepDialog." + method, branches) for method, branches in DIALOG_BRANCHES.items()
)
