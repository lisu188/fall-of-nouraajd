# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Candlekeep prologue content; checks intentionally use the engine's native hero statistics."""

QUEST_ACTORS = ("firebead", "phlydia", "dreppin", "hull", "fuller", "reevor")
QUEST_ITEMS = {
    "firebead": "candlekeepIdentifyScroll",
    "phlydia": "candlekeepHistoryHalruaa",
    "dreppin": "candlekeepAntidote",
    "hull": "candlekeepHullSword",
    "fuller": "candlekeepBolts",
}
TRAINING_ALLIES = ("arkanis", "canderous", "deder", "mordaine", "osprey")
NPC_IDS = (
    QUEST_ACTORS
    + (
        "winthrop",
        "tethtoril",
        "gorion",
        "imoen",
        "gatewarden",
        "obe",
        "templePriest",
        "clinicPriest",
        "thurston",
        "lovey",
        "nessa",
        "keeper",
        "watcher",
        "parda",
        "karan",
        "jondalar",
        "erik",
        "chanter",
        "voiceNorth",
        "voiceSouth",
        "voiceEast",
        "voiceWest",
    )
    + tuple("tutor" + str(i) for i in range(1, 15))
)


def load(self, context):
    import json

    def decodeData(encoded):
        return json.loads(encoded.removeprefix("candlekeep-json:"))

    def encodeData(value):
        return "candlekeep-json:" + json.dumps(value)

    def firstMatch(values, default=None):
        for value in values:
            return value
        return default

    from game import CBuilding, CCreature, CDialog, CEvent, CQuest, CScroll, CTrigger, Coords
    from game import claim_once, flowGame, mapQuest, register, resumableHook, trigger, uiRequest

    def gameMap(obj):
        return obj.getGame().getMap()

    def playerFor(obj):
        return gameMap(obj).getPlayer()

    def stage(game_map, actor):
        return game_map.getStringProperty("candlekeep_" + actor + "Stage") or "notStarted"

    def setStage(game_map, actor, value):
        game_map.setStringProperty("candlekeep_" + actor + "Stage", value)

    def notify(obj, text):
        obj.getGame().getGuiHandler().notify(text)

    def hasItem(player, item_id):
        return player.countItems(item_id) > 0

    def consumeItem(player, item_id):
        for item in player.getItems():
            if item.getTypeId() == item_id:
                player.removeQuestItem(lambda candidate: candidate == item)
                return True
        return False

    def spawn(game_map, object_id, coords, name=None):
        actor = game_map.getGame().createObject(object_id)
        actor.setStringProperty("name", name or object_id)
        actor.setNumericProperty("posx", coords[0])
        actor.setNumericProperty("posy", coords[1])
        actor.setNumericProperty("posz", coords[2])
        game_map.addObject(actor)
        return actor

    def removeTraining(game_map):
        for name in TRAINING_ALLIES + tuple("trainingFoe" + str(i) for i in range(1, 7)):
            actor = game_map.getObjectByName(name)
            if actor:
                for slot, item in tuple(actor.getEquipped().items()):
                    if item and item.getBoolProperty("plugin_candlekeepTemporary"):
                        item.removeTag("cursed")
                        actor.equipItem(slot, None)
                for item in tuple(actor.getItems()):
                    if item.getBoolProperty("plugin_candlekeepTemporary"):
                        actor.removeItem(lambda candidate: candidate == item, False)
                game_map.removeObject(actor)

    def reclaimTrainingInventory(game_map):
        player = game_map.getPlayer()
        original_names = set(decodeData(player.getStringProperty("candlekeepTrainingInventoryNames") or "[]"))
        for owner in game_map.getObjects():
            if not isinstance(owner, CCreature) or owner == player:
                continue
            for item in tuple(owner.getItems()):
                if item.getName() not in original_names:
                    continue
                owner.removeQuestItem(lambda candidate: candidate == item)
                if item not in owner.getItems() and item not in player.getItems():
                    player.addItem(item)

    def restoreTraining(game_map, outcome):
        if stage(game_map, "training") != "active":
            return False
        player = game_map.getPlayer()
        reclaimTrainingInventory(game_map)
        for slot, item in tuple(player.getEquipped().items()):
            if item and item.getBoolProperty("plugin_candlekeepTemporary"):
                item.removeTag("cursed")
                player.equipItem(slot, None)
        for item in tuple(player.getItems()):
            if item.getBoolProperty("plugin_candlekeepTemporary"):
                player.removeItem(lambda candidate: candidate == item, False)
        original_equipment = decodeData(player.getStringProperty("candlekeepTrainingEquipment") or "{}")
        for slot, name in original_equipment.items():
            item = firstMatch((item for item in player.getItems() if item.getName() == name), None)
            if item:
                player.equipItem(slot, item)
        player.setStringProperty("affiliation", player.getStringProperty("candlekeepTrainingAffiliation"))
        player.setHp(max(1, player.getNumericProperty("candlekeepTrainingHp")))
        player.setMana(player.getNumericProperty("candlekeepTrainingMana"))
        game_map.setBoolProperty("candlekeepTrainingDefeatPending", False)
        setStage(game_map, "training", outcome)
        removeTraining(game_map)
        return True

    def summonWatch(obj, count=1):
        count = max(0, min(2, int(count)))
        if not count:
            return
        game_map, player = gameMap(obj), playerFor(obj)
        game_map.setBoolProperty("candlekeepGuardsAlerted", True)
        game_map.setNumericProperty("candlekeepStanding", game_map.getNumericProperty("candlekeepStanding") - 2)
        crimes = game_map.getNumericProperty("candlekeepCrimes") + 1
        game_map.setNumericProperty("candlekeepCrimes", crimes)
        loc = player.getCoords()
        spawned = game_map.getNumericProperty("candlekeepWatchersSpawned")
        remaining = count
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            coords = Coords(loc.x + dx, loc.y + dy, loc.z)
            if game_map.canStep(coords):
                spawned += 1
                spawn(game_map, "candlekeepWatch", (coords.x, coords.y, coords.z), "candlekeepWatch" + str(spawned))
                remaining -= 1
                if not remaining:
                    break
        game_map.setNumericProperty("candlekeepWatchersSpawned", spawned)
        notify(obj, "The Watch answers the alarm. Theft and violence have consequences inside these walls.")

    @register(context)
    @mapQuest("candlekeep")
    class CandlekeepQuest(CQuest):
        def questActor(self):
            return self.getStringProperty("questKey")

        def isCompleted(self):
            return stage(self.getGame().getMap(), self.questActor()) == "completed"

        def getObjective(self):
            if self.isCompleted():
                return self.getStringProperty("completedText")
            if self.questActor() == "reevor":
                return "Clear the storehouse: %s of five rats defeated." % self.getGame().getMap().getNumericProperty(
                    "candlekeepRatsSlain"
                )
            return self.getStringProperty("objective")

        def getReward(self):
            return self.getStringProperty("rewardText")

        def getHint(self):
            return self.getStringProperty("hint")

        def onComplete(self):
            pass

    @register(context)
    class CandlekeepStart(CEvent):
        @resumableHook
        def onEnter(self, event):
            player = event.getCause() if event else None
            if not player or not player.isPlayer() or not claim_once(self.getMap(), "candlekeepInitialized"):
                return
            for actor in QUEST_ACTORS:
                setStage(self.getMap(), actor, "notStarted")
            setStage(self.getMap(), "training", "idle")
            player.addGold(50)
            self.getMap().setNumericProperty("candlekeepStartingPurse", 50)
            yield uiRequest("showReader", flowGame(self.getGame()), "Candlekeep", self.getStringProperty("text"))

    @register(context)
    class CandlekeepPortal(CBuilding):
        def target(self):
            return Coords(
                self.getNumericProperty("targetX"),
                self.getNumericProperty("targetY"),
                self.getNumericProperty("targetZ"),
            )

        def publishEdge(self):
            game_map = self.getMap()
            if not game_map:
                return
            target = self.target()
            blocked = (
                game_map.getBoolProperty("candlekeepDeparted")
                or self.getBoolProperty("trainingDoor")
                and (
                    game_map.getBoolProperty("candlekeepTrainingClosed")
                    or not game_map.getBoolProperty("candlekeepTrainingAccepted")
                )
            )
            if blocked or not game_map.canStep(target):
                self.setBoolProperty("waypoint", False)
                game_map.unregisterNavigationEdgesForObject(self.getName())
                return
            self.setBoolProperty("waypoint", True)
            for name, value in (("x", target.x), ("y", target.y), ("z", target.z)):
                self.setNumericProperty(name, value)
            if not game_map.hasNavigationEdge(self.getCoords(), target, self.getName()):
                game_map.unregisterNavigationEdgesForObject(self.getName())
                game_map.registerNavigationEdge(self.getCoords(), target, True, False, 1, self.getName())

        def onCreate(self, event):
            self.publishEdge()

        def onTurn(self, event):
            self.publishEdge()

        def onDestroy(self, event):
            if self.getMap():
                self.getMap().unregisterNavigationEdgesForObject(self.getName())

        @resumableHook
        def onEnter(self, event):
            player = event.getCause() if event else None
            if not player or not player.isPlayer() or self.getMap().getBoolProperty("candlekeepDeparted"):
                return
            if player.getStringProperty("candlekeepPortalGuard") == self.getName():
                player.setStringProperty("candlekeepPortalGuard", "")
                return
            origin = player.getPendingMoveOrigin()
            paired = self.getMap().getObjectByName(self.getStringProperty("pairedPortal"))
            if (
                origin is not None
                and isinstance(paired, CandlekeepPortal)
                and paired.getCoords() == origin
                and paired.target() == self.getCoords()
                and player.getCoords() == self.getCoords()
                and self.getMap().hasNavigationEdge(origin, self.getCoords(), paired.getName())
            ):
                if paired.getName() == "trainingExit":
                    restoreTraining(self.getMap(), "abandoned")
                return
            if self.getBoolProperty("trainingDoor") and (
                self.getMap().getBoolProperty("candlekeepTrainingClosed")
                or not self.getMap().getBoolProperty("candlekeepTrainingAccepted")
            ):
                notify(self, "The practice cellar is closed. Ask the Gatewarden about training.")
                return
            player.setStringProperty("candlekeepPortalGuard", self.getStringProperty("pairedPortal"))
            if self.getName() == "trainingExit":
                restoreTraining(self.getMap(), "abandoned")
            target = self.target()
            yield uiRequest("gui.moveTo", player, target.x, target.y, target.z)

    @register(context)
    class CandlekeepSpellScroll(CScroll):
        def isDisposable(self):
            # Commit consumption only when this map-local use actually changes the hero.
            return False

        def onUse(self, event):
            player = event.getCause() if event else None
            if (
                not player
                or not player.isPlayer()
                or self not in player.getItems()
                or self.getGame().getMap().getBoolProperty("candlekeepDeparted")
            ):
                return False
            spell = self.getStringProperty("plugin_candlekeepSpell")
            if spell == "identify":
                target = firstMatch(
                    (
                        item
                        for item in player.getItems()
                        if item != self and item.getBoolProperty("plugin_candlekeepUnidentified")
                    ),
                    None,
                )
                if not target:
                    notify(self, "You have no unidentified possession for this scroll to reveal.")
                    return False
                target.setBoolProperty("plugin_candlekeepUnidentified", False)
                game_map = self.getGame().getMap()
                game_map.setNumericProperty(
                    "candlekeepIdentifications", game_map.getNumericProperty("candlekeepIdentifications") + 1
                )
                notify(self, "The identify scroll reveals the properties of " + target.getStringProperty("label") + ".")
            elif spell == "armor":
                effect = self.getGame().createObject("candlekeepArmorEffect")
                effect.setCaster(player)
                effect.setVictim(player)
                player.addEffect(effect)
                notify(self, "The armor scroll grants 20 native armor for 12 effect ticks.")
            elif spell == "infravision":
                notify(
                    self,
                    "The native map already shows its visible terrain without darkness or a vision range. "
                    "Infravision has no matching native rule; the scroll is kept.",
                )
                return False
            else:
                notify(self, self.getStringProperty("text"))
                return False
            player.removeQuestItem(lambda candidate: candidate == self)
            return True

    @register(context)
    class CandlekeepContainer(CBuilding):
        @resumableHook
        def onEnter(self, event):
            if (
                event
                and event.getCause()
                and event.getCause().isPlayer()
                and not self.getMap().getBoolProperty("candlekeepDeparted")
            ):
                yield uiRequest("gui.showDialog", self.getGame().createObject(self.getName() + "Dialog"))

    @register(context)
    class CandlekeepDialog(CDialog):
        def _progressAllowed(self):
            if self.getGame().getMap().getBoolProperty("candlekeepDeparted"):
                return False
            if self.actorId() in NPC_IDS + TRAINING_ALLIES:
                actor = self.actor()
                return bool(actor and actor.isAlive())
            return True

        def actorId(self):
            return self.getStringProperty("actorId")

        def actor(self):
            return self.getGame().getMap().getObjectByName(self.actorId())

        def socialScore(self):
            return playerFor(self).getStats().getNumericProperty(
                "intelligence"
            ) + self.getGame().getMap().getNumericProperty("candlekeepStanding")

        def highReaction(self):
            return self.socialScore() >= 12

        def lowReaction(self):
            return self.socialScore() < 7

        def canAcceptQuest(self):
            if not self.actor():
                return False
            if not self._progressAllowed():
                return False
            if (
                self.actorId() == "dreppin"
                and self.getGame().getMap().getNumericProperty("candlekeepDreppinConversations") < 2
            ):
                return False
            return self.actorId() in QUEST_ACTORS and stage(self.getGame().getMap(), self.actorId()) == "notStarted"

        def questActive(self):
            return stage(self.getGame().getMap(), self.actorId()) == "active"

        def questCompleted(self):
            return stage(self.getGame().getMap(), self.actorId()) == "completed"

        def canReturnQuest(self):
            if not self.actor():
                return False
            if not self._progressAllowed():
                return False
            if not self.questActive():
                return False
            if self.actorId() == "reevor":
                return self.getGame().getMap().getNumericProperty("candlekeepRatsSlain") >= 5
            return hasItem(playerFor(self), QUEST_ITEMS.get(self.actorId(), ""))

        def acceptQuest(self):
            if not self._progressAllowed():
                return False
            if not self.canAcceptQuest():
                return False
            setStage(self.getGame().getMap(), self.actorId(), "active")
            playerFor(self).addQuest(self.actorId() + "Quest")
            if self.actorId() == "dreppin":
                self.getGame().getMap().setBoolProperty("candlekeepDreppinBookHint", True)
            notify(self, self.getStringProperty("questOffer") or "Your journal records the request.")
            return True

        def returnQuest(self):
            if not self._progressAllowed():
                return False
            if not self.canReturnQuest():
                return False
            game_map, player, actor = self.getGame().getMap(), playerFor(self), self.actorId()
            if actor != "reevor" and not consumeItem(player, QUEST_ITEMS[actor]):
                return False
            setStage(game_map, actor, "completed")
            player.addExp(50)
            if actor == "firebead":
                player.addItem("candlekeepHealingPotion")
                effect = self.getGame().createObject("candlekeepProtectionEvil")
                effect.setCaster(player)
                effect.setVictim(player)
                player.addEffect(effect)
                game_map.setBoolProperty("candlekeepFirebeadProtected", True)
            elif actor == "phlydia" and not self.lowReaction():
                self.claimLynxEye()
            elif actor == "hull":
                player.addGold(20 if self.highReaction() else 10)
            elif actor == "fuller":
                if self.highReaction():
                    self.claimFullerDagger()
                else:
                    player.addGold(10)
            elif actor == "reevor":
                player.addGold(5)
            if actor == "dreppin":
                game_map.setBoolProperty("candlekeepNessaCured", True)
            player.checkQuests()
            notify(self, "The errand is complete: 50 experience. Your journal records the outcome.")
            return True

        def _transferOwnedItem(self, item_id):
            if not self._progressAllowed():
                return False
            actor = self.actor()
            if not actor:
                return False
            item = firstMatch((item for item in actor.getItems() if item.getTypeId() == item_id), None)
            if not item:
                return False
            actor.removeQuestItem(lambda candidate: candidate == item)
            if item in actor.getItems():
                return False
            playerFor(self).addItem(item)
            return True

        def claimFullerDagger(self):
            if not self._progressAllowed() or self.actorId() != "fuller":
                return False
            if self.getGame().getMap().getBoolProperty("candlekeepFullerDaggerClaimed"):
                return False
            if not self._transferOwnedItem("candlekeepDaggerPlusOne"):
                return False
            self.getGame().getMap().setBoolProperty("candlekeepFullerDaggerClaimed", True)
            return True

        def claimLynxEye(self):
            if not self._progressAllowed() or self.actorId() != "phlydia":
                return False
            if self.getGame().getMap().getBoolProperty("candlekeepPhlydiaLynxEyeClaimed"):
                return False
            if not self._transferOwnedItem("candlekeepLynxEyeGem"):
                return False
            self.getGame().getMap().setBoolProperty("candlekeepPhlydiaLynxEyeClaimed", True)
            return True

        def deliverScroll(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "tethtoril" or stage(self.getGame().getMap(), "firebead") != "active":
                return False
            if not claim_once(self.getGame().getMap(), "candlekeepTethtorilScrollGiven"):
                return False
            playerFor(self).addItem("candlekeepIdentifyScroll")
            return True

        def keepScroll(self):
            if not self._progressAllowed():
                return False
            if hasItem(playerFor(self), "candlekeepIdentifyScroll"):
                self.getGame().getMap().setBoolProperty("candlekeepScrollKept", True)

        def talk(self):
            if not self._progressAllowed():
                return False
            game_map, actor = self.getGame().getMap(), self.actorId()
            count = game_map.getNumericProperty("candlekeepTalks_" + actor) + 1
            game_map.setNumericProperty("candlekeepTalks_" + actor, count)
            game_map.setBoolProperty("candlekeepTalked_" + actor, True)
            if actor == "firebead":
                count = game_map.getNumericProperty("candlekeepFirebeadConversations")
                if count >= 30 and claim_once(game_map, "candlekeepFirebeadThirtyTalks"):
                    playerFor(self).addGold(300)
            if actor == "dreppin":
                game_map.setBoolProperty("candlekeepDreppinBookHint", True)
            if actor.startswith("tutor"):
                game_map.setBoolProperty("candlekeepTutor_" + self.getStringProperty("topic"), True)
            if actor in ("parda", "karan"):
                game_map.setBoolProperty(
                    "candlekeepAftermath_" + actor,
                    game_map.getBoolProperty("candlekeep_" + ("shank" if actor == "parda" else "carbos") + "Slain"),
                )
            if actor == "gorion":
                playerFor(self).heal(0)
                game_map.setBoolProperty("candlekeepGorionAdvice", True)
            notify(self, self.getStringProperty("talkText") or "The conversation is recorded.")

        def _availablePocketItems(self):
            actor = self.actor()
            if not actor or actor.getBoolProperty("plugin_candlekeepPocketsEmpty"):
                return []
            remaining = []
            for item_id in actor.getStringProperty("plugin_candlekeepPocketItems").split(","):
                if not item_id:
                    continue
                if item_id == "candlekeepDaggerPlusOne" and self.getGame().getMap().getBoolProperty(
                    "candlekeepFullerDaggerClaimed"
                ):
                    continue
                if item_id == "candlekeepLynxEyeGem" and self.getGame().getMap().getBoolProperty(
                    "candlekeepPhlydiaLynxEyeClaimed"
                ):
                    continue
                item = firstMatch(
                    (item for item in actor.getItems() if item.getTypeId() == item_id and item not in remaining), None
                )
                if item:
                    remaining.append(item)
            return remaining

        def canPickpocket(self):
            if not self._progressAllowed():
                return False
            return bool(self._availablePocketItems())

        def pickpocket(self):
            if not self._progressAllowed():
                return False
            remaining = self._availablePocketItems()
            if not remaining:
                return False
            actor, player = self.actor(), playerFor(self)
            threshold = actor.getNumericProperty("plugin_candlekeepTheftThreshold") or 16
            if player.getStats().getNumericProperty("agility") < threshold:
                summonWatch(self)
                return False
            for item in remaining:
                item_id = item.getTypeId()
                if item_id == "candlekeepDaggerPlusOne":
                    self.claimFullerDagger()
                elif item_id == "candlekeepLynxEyeGem":
                    self.claimLynxEye()
                else:
                    self._transferOwnedItem(item_id)
            actor.setBoolProperty("plugin_candlekeepPocketsEmpty", True)
            self.getGame().getMap().setBoolProperty("candlekeepStole_" + self.actorId(), True)
            return True

        def pickPocket(self):
            return self.pickpocket()

        def countConversation(self):
            return self.talk()

        def beginLesson(self):
            return self.practiceCombat()

        def attack(self):
            if not self._progressAllowed():
                return False
            actor = self.actor()
            if not actor:
                return False
            actor.setBoolProperty("npc", False)
            actor.setStringProperty("affiliation", "candlekeepHostile")
            controller = self.getGame().createObject("CTargetController")
            controller.setStringProperty("target", "player")
            actor.setController(controller)
            summonWatch(self)
            return True

        def authorizedContainer(self):
            actor = self.actor()
            if not actor:
                return False
            if self.actorId() == "hullChest":
                return (
                    stage(self.getGame().getMap(), "hull") == "active"
                    or stage(self.getGame().getMap(), "dreppin") == "active"
                )
            return not actor.getBoolProperty("owned") or actor.getBoolProperty("ownerPermission")

        def canOpen(self):
            if not self._progressAllowed():
                return False
            return bool(
                self.actor()
                and not self.actor().getBoolProperty("looted")
                and not self.actor().getBoolProperty("locked")
            )

        def canUnlock(self):
            if not self._progressAllowed():
                return False
            return bool(
                self.actor()
                and self.actor().getBoolProperty("locked")
                and playerFor(self).getStats().getNumericProperty("agility")
                >= self.actor().getNumericProperty("lockAgility")
            )

        def canForce(self):
            if not self._progressAllowed():
                return False
            return bool(
                self.actor()
                and self.actor().getBoolProperty("locked")
                and playerFor(self).getStats().getNumericProperty("strength")
                >= self.actor().getNumericProperty("forceStrength")
            )

        def unlockContainer(self):
            if not self._progressAllowed():
                return False
            if not self.canUnlock():
                return False
            self.actor().setBoolProperty("locked", False)
            self.actor().setBoolProperty("picked", True)
            return True

        def _reportContainerTheft(self):
            actor = self.actor()
            if not actor or actor.getBoolProperty("guardSummoned"):
                return
            count = actor.getNumericProperty("plugin_candlekeepGuardCount")
            if count:
                actor.setBoolProperty("guardSummoned", True)
                summonWatch(self, count)

        def forceContainer(self):
            if not self._progressAllowed():
                return False
            if not self.canForce():
                return False
            self.actor().setBoolProperty("locked", False)
            self.actor().setBoolProperty("forced", True)
            if self.actor().getBoolProperty("owned"):
                self._reportContainerTheft()
            return True

        def openContainer(self):
            if not self._progressAllowed():
                return False
            if not self.canOpen() or not self.authorizedContainer():
                return False
            return self.takeContents()

        def stealContainer(self):
            if not self._progressAllowed():
                return False
            if not self.canOpen():
                return False
            actor = self.actor()
            caught = actor.getBoolProperty("alwaysGuard") or playerFor(self).getStats().getNumericProperty(
                "agility"
            ) < (actor.getNumericProperty("plugin_candlekeepTheftThreshold") or 16)
            result = self.takeContents()
            if result:
                self.getGame().getMap().setBoolProperty("candlekeepStole_" + self.actorId(), True)
                if caught:
                    self._reportContainerTheft()
            return result

        def takeContents(self):
            if not self._progressAllowed():
                return False
            actor, player = self.actor(), playerFor(self)
            if not actor or not claim_once(actor, "looted"):
                return False
            for item_id in actor.getStringProperty("contents").split(","):
                if item_id:
                    player.addItem(item_id)
            player.addGold(actor.getNumericProperty("gold"))
            self.getGame().getMap().setBoolProperty("candlekeepLooted_" + self.actorId(), True)
            return True

        def _entries(self, property_name):
            try:
                rows = decodeData(self.getStringProperty(property_name) or "[]")
            except (ValueError, TypeError):
                return []
            return rows if isinstance(rows, list) else []

        def _purchase(self, row):
            if not self._progressAllowed():
                return False
            if self.actorId() not in ("winthrop", "templePriest"):
                return False
            item_id = row.get("itemId", "")
            cost, limit = int(row.get("price", -1)), int(row.get("limit", 0))
            stock_id = row.get("id", "")
            if not item_id or not stock_id or cost < 0 or limit < 0:
                return False
            game_map, player = self.getGame().getMap(), playerFor(self)
            stock_key = "candlekeepStockBought_" + self.actorId() + "_" + stock_id
            bought = game_map.getNumericProperty(stock_key)
            if player.getGold() < cost or (limit and bought >= limit):
                notify(self, "You cannot afford the purchase, or the stock is exhausted.")
                return False
            item = self.getGame().createObject(item_id)
            if not item:
                return False
            quantity = max(1, int(row.get("quantity", 1)))
            if quantity > 1:
                item.setNumericProperty("plugin_candlekeepQuantity", quantity)
            player.addGold(-cost)
            player.addItem(item)
            game_map.setNumericProperty(stock_key, bought + 1)
            return True

        def buyStock(self):
            if not self._progressAllowed():
                return False
            selected = self.getStringProperty("selectedStock")
            row = firstMatch((row for row in self._entries("shopEntries") if row.get("id") == selected), None)
            return self._purchase(row) if row else False

        @resumableHook
        def browseStock(self):
            if not self._progressAllowed():
                return False
            if self.actorId() not in ("winthrop", "templePriest"):
                return
            rows = []
            for entry in self._entries("shopEntries"):
                key = "candlekeepStockBought_" + self.actorId() + "_" + entry["id"]
                bought = self.getGame().getMap().getNumericProperty(key)
                limit = int(entry.get("limit", 0))
                rows.append(
                    {
                        "id": entry["id"],
                        "label": entry["label"],
                        "detail": str(entry["price"])
                        + " gold; "
                        + ("unlimited" if not limit else str(max(0, limit - bought)) + " left"),
                        "enabled": not limit or bought < limit,
                    }
                )
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Candlekeep wares", rows, "Buy")
            if selected:
                self.setStringProperty("selectedStock", selected)
                self.buyStock()

        def buy(self, item_id, cost, stock_key, limit=20):
            if not self._progressAllowed():
                return False
            if self.actorId() not in ("winthrop", "templePriest"):
                return False
            rows = self._entries("shopEntries")
            aliases = {
                "candlekeepBolts": "BOLT01",
                "candlekeepHealingPotion": "POTN08",
                "candlekeepDagger": "DAGG01",
                "candlekeepLongsword": "SW1H04",
                "LeatherArmor": "LEAT01",
                "PlateArmor": "PLAT01",
                "Staff": "STAF01",
                "candlekeepArrows": "AROW01",
                "candlekeepAntidote": "POTN20",
            }
            row = firstMatch(
                (
                    entry
                    for entry in rows
                    if entry.get("itemId") == item_id or entry.get("id", "").upper() == aliases.get(item_id, "")
                ),
                None,
            )
            if row:
                return self._purchase(row)
            if rows:
                return False
            game_map, player = self.getGame().getMap(), playerFor(self)
            bought = game_map.getNumericProperty(stock_key)
            if player.getGold() < cost or bought >= limit:
                return False
            player.addGold(-cost)
            player.addItem(item_id)
            game_map.setNumericProperty(stock_key, bought + 1)
            return True

        def buyBolts(self):
            return self.buy("candlekeepBolts", 1, "candlekeepBoltsBought", 5)

        def buyHealingPotion(self):
            return self.buy("candlekeepHealingPotion", 75, "candlekeepHealingPotionsBought", 5)

        def buyDagger(self):
            return self.buy("candlekeepDagger", 2, "candlekeepDaggersBought", 5)

        def buyLongsword(self):
            return self.buy("candlekeepLongsword", 15, "candlekeepLongswordsBought", 5)

        def buyLeatherArmor(self):
            return self.buy("LeatherArmor", 5, "candlekeepLeatherBought", 3)

        def buyPlateArmor(self):
            return self.buy("PlateArmor", 60, "candlekeepPlateBought", 1)

        def buyStaff(self):
            return self.buy("Staff", 1, "candlekeepStaffBought", 5)

        def buyAmmo(self):
            return self.buy("candlekeepArrows", 1, "candlekeepArrowsBought", 5)

        def buyAntidote(self):
            return self.buy("candlekeepAntidote", 100, "candlekeepAntidotesBought", 3)

        def _saleableItems(self):
            return sorted(
                (item for item in playerFor(self).getItems() if item.getBoolProperty("plugin_candlekeepTradeable")),
                key=lambda item: (item.getStringProperty("label"), item.getName()),
            )

        def sellSelectedItem(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "winthrop":
                return False
            selected = self.getStringProperty("selectedSale")
            item = firstMatch((item for item in self._saleableItems() if item.getName() == selected), None)
            if not item:
                return False
            player = playerFor(self)
            player.removeItem(lambda candidate: candidate == item, False)
            if item in player.getItems():
                return False
            player.addGold(max(0, item.getNumericProperty("plugin_candlekeepSellPrice")))
            return True

        @resumableHook
        def sellItem(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "winthrop":
                return
            rows = [
                {
                    "id": item.getName(),
                    "label": item.getStringProperty("label") or item.getTypeId(),
                    "detail": str(max(0, item.getNumericProperty("plugin_candlekeepSellPrice"))) + " gold",
                }
                for item in self._saleableItems()
            ]
            if not rows:
                notify(self, "There are no saleable items in your backpack.")
                return
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Sell one item", rows, "Sell")
            if selected:
                self.setStringProperty("selectedSale", selected)
                self.sellSelectedItem()

        def rest(self, cost, tier):
            if not self._progressAllowed():
                return False
            if self.actorId() != "winthrop":
                return False
            player = playerFor(self)
            if player.getGold() < cost:
                return False
            player.addGold(-cost)
            player.heal(0)
            player.addMana(0)
            self.getGame().getMap().setStringProperty("candlekeepLastRoom", tier)
            self.getGame().getMap().setNumericProperty(
                "candlekeepRestCount", self.getGame().getMap().getNumericProperty("candlekeepRestCount") + 1
            )
            notify(self, "Eight quiet hours pass. You wake rested in a " + tier + " room.")
            return True

        def restBasic(self):
            return self.rest(1, "peasant")

        def restMerchant(self):
            return self.rest(3, "merchant")

        def restNoble(self):
            return self.rest(5, "noble")

        def restRoyal(self):
            return self.rest(8, "royal")

        def drink(self, cost, kind):
            if not self._progressAllowed():
                return False
            if self.actorId() != "winthrop" or cost < 0 or playerFor(self).getGold() < cost:
                return False
            playerFor(self).addGold(-cost)
            game_map = self.getGame().getMap()
            game_map.setNumericProperty("candlekeepDrinks", game_map.getNumericProperty("candlekeepDrinks") + 1)
            game_map.setStringProperty("candlekeepLastDrink", kind)
            notify(self, "Over your " + kind + ", Winthrop shares talk of iron shortages and trouble on the roads.")
            return True

        def buyDrink(self):
            if not self._progressAllowed():
                return False
            selected = self.getStringProperty("selectedDrink")
            row = firstMatch((row for row in self._entries("drinkEntries") if row.get("id") == selected), None)
            if not row:
                return False
            result = self.drink(int(row["price"]), row["label"])
            if result:
                game_map = self.getGame().getMap()
                game_map.setNumericProperty(
                    "candlekeepIntoxication",
                    game_map.getNumericProperty("candlekeepIntoxication") + int(row.get("strength", 0)),
                )
            return result

        @resumableHook
        def browseDrinks(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "winthrop":
                return
            rows = [
                {"id": row["id"], "label": row["label"], "detail": str(row["price"]) + " gold"}
                for row in self._entries("drinkEntries")
            ]
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Drinks and rumors", rows, "Order")
            if selected:
                self.setStringProperty("selectedDrink", selected)
                self.buyDrink()

        def _quickDrink(self, source_id):
            row = firstMatch((row for row in self._entries("drinkEntries") if row.get("id") == source_id), None)
            if not row:
                return False
            self.setStringProperty("selectedDrink", source_id)
            return self.buyDrink()

        def drinkBeer(self):
            return self._quickDrink("FIREWINE")

        def drinkWine(self):
            return self._quickDrink("ARABELLAN_DRY_WINE")

        def drinkAle(self):
            return self._quickDrink("BITTER_BLACK_ALE")

        def donate(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "templePriest":
                return False
            if playerFor(self).getGold() < 10:
                return False
            playerFor(self).addGold(-10)
            self.getGame().getMap().setNumericProperty(
                "candlekeepDonatedGold", self.getGame().getMap().getNumericProperty("candlekeepDonatedGold") + 10
            )
            return True

        def buyService(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "templePriest":
                return False
            selected = self.getStringProperty("selectedService")
            row = firstMatch((row for row in self._entries("serviceEntries") if row.get("id") == selected), None)
            if not row:
                return False
            cost = int(row.get("price", -1))
            player = playerFor(self)
            if cost < 0 or player.getGold() < cost:
                return False
            operation = row.get("operation", "heal")
            if operation == "identify":
                return self._identifyFor(cost)
            if operation in ("resurrect", "raiseDead"):
                notify(self, "No dead companion is available to raise in this native single-hero prologue.")
                return False
            if operation == "removeCurse":
                cursed = [
                    item
                    for item in list(player.getItems()) + list(player.getEquipped().values())
                    if item and item.hasTag("cursed")
                ]
                if not cursed:
                    notify(self, "You carry no cursed item requiring this service.")
                    return False
                for item in cursed:
                    item.removeTag("cursed")
            elif operation in ("curePoison", "slowPoison", "cureDisease"):
                kind = "disease" if operation == "cureDisease" else "poison"
                matching = {
                    effect
                    for effect in player.getEffects()
                    if effect.getBoolProperty("plugin_candlekeep" + kind[:1].upper() + kind[1:])
                    or kind in effect.getTypeId().lower()
                }
                if not matching:
                    notify(self, "No matching native " + kind + " effect requires treatment.")
                    return False
                if operation == "slowPoison":
                    notify(
                        self,
                        "Slowing an active poison is not represented by the native status model; no gold is taken.",
                    )
                    return False
                player.setEffects(set(player.getEffects()) - matching)
            else:
                if player.getHp() >= player.getHpMax():
                    notify(self, "You are already in full health.")
                    return False
                player.heal(0)
            player.addGold(-cost)
            self.getGame().getMap().setStringProperty("candlekeepLastTempleService", selected)
            return True

        @resumableHook
        def browseServices(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "templePriest":
                return
            rows = [
                {"id": row["id"], "label": row["label"], "detail": str(row["price"]) + " gold"}
                for row in self._entries("serviceEntries")
            ]
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Temple services", rows, "Request")
            if selected:
                self.setStringProperty("selectedService", selected)
                self.buyService()

        def healAtTemple(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "templePriest":
                return False
            rows = self._entries("serviceEntries")
            row = firstMatch((entry for entry in rows if entry.get("operation") == "heal"), None)
            if row:
                self.setStringProperty("selectedService", row["id"])
                return self.buyService()
            if playerFor(self).getGold() < 112:
                return False
            playerFor(self).addGold(-112)
            playerFor(self).heal(0)
            return True

        def _identifyFor(self, cost):
            if not self._progressAllowed():
                return False
            player = playerFor(self)
            if cost < 0 or player.getGold() < cost:
                return False
            for item in player.getItems():
                if item.getBoolProperty("plugin_candlekeepUnidentified"):
                    player.addGold(-cost)
                    item.setBoolProperty("plugin_candlekeepUnidentified", False)
                    game_map = self.getGame().getMap()
                    game_map.setNumericProperty(
                        "candlekeepIdentifications", game_map.getNumericProperty("candlekeepIdentifications") + 1
                    )
                    return True
            return False

        def identifyItem(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "templePriest":
                return False
            row = firstMatch(
                (entry for entry in self._entries("serviceEntries") if entry.get("operation") == "identify"), None
            )
            return self._identifyFor(int(row["price"]) if row else 100)

        def acceptPotion(self):
            if not self._progressAllowed() or self.actorId() != "clinicPriest":
                return False
            if self.getGame().getMap().getBoolProperty("candlekeepClinicGiftClaimed"):
                return False
            if not self._transferOwnedItem("candlekeepHealingPotion"):
                return False
            self.getGame().getMap().setBoolProperty("candlekeepClinicGiftClaimed", True)
            self.getGame().getMap().setBoolProperty("candlekeepClinicGiftDeclined", False)
            return True

        def declinePotion(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "clinicPriest":
                return False
            self.getGame().getMap().setBoolProperty("candlekeepClinicGiftDeclined", True)

        def trainingAvailable(self):
            return not self.getGame().getMap().getBoolProperty("candlekeepTrainingClosed")

        def acceptTraining(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "gatewarden":
                return False
            if not self.trainingAvailable():
                return False
            self.getGame().getMap().setBoolProperty("candlekeepTrainingAccepted", True)
            self.getGame().getMap().getObjectByName("trainingEntrance").publishEdge()
            return True

        def declineTraining(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "gatewarden":
                return False
            if self.getGame().getMap().getBoolProperty("candlekeepTrainingAccepted"):
                return False
            game_map = self.getGame().getMap()
            count = game_map.getNumericProperty("candlekeepGatewardenDeclines") + 1
            game_map.setNumericProperty("candlekeepGatewardenDeclines", count)
            if count >= 2:
                self.closeTrainingGate()
            return True

        def canDeclineSecond(self):
            game_map = self.getGame().getMap()
            return (
                self.actorId() == "gatewarden"
                and self._progressAllowed()
                and game_map.getNumericProperty("candlekeepGatewardenDeclines") >= 1
                and not game_map.getBoolProperty("candlekeepTrainingAccepted")
                and not game_map.getBoolProperty("candlekeepTrainingClosed")
            )

        def closeTrainingGate(self):
            if not self._progressAllowed():
                return False
            if not self.canDeclineSecond():
                return False
            self.getGame().getMap().setNumericProperty("candlekeepGatewardenDeclines", 2)
            if self.actorId() != "gatewarden":
                return False
            self.getGame().getMap().setBoolProperty("candlekeepTrainingClosed", True)
            self.getGame().getMap().setBoolProperty("candlekeepTrainingAccepted", False)
            self.getGame().getMap().getObjectByName("trainingEntrance").publishEdge()

        def beginTraining(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "obe":
                return False
            game_map, player = self.getGame().getMap(), playerFor(self)
            if not game_map.getBoolProperty("candlekeepTrainingAccepted") or not self.trainingAvailable():
                return False
            if stage(game_map, "training") not in ("idle", "abandoned"):
                return False
            # This serialized observer records defeat; the next native map turn performs restoration.
            if not game_map.getBoolProperty("candlekeepTrainingDefeatHookRegistered"):
                hook = self.getGame().createObject("CandlekeepTrainingDefeatTrigger")
                hook.setStringProperty("object", "player")
                hook.setStringProperty("event", "onDestroy")
                game_map.getEventHandler().registerTrigger(hook)
                game_map.setBoolProperty("candlekeepTrainingDefeatHookRegistered", True)
            player.setStringProperty(
                "candlekeepTrainingInventoryNames",
                encodeData(
                    sorted(
                        {item.getName() for item in player.getItems()}
                        | {item.getName() for item in player.getEquipped().values() if item}
                    )
                ),
            )
            player.setStringProperty("candlekeepTrainingAffiliation", player.getStringProperty("affiliation"))
            player.setStringProperty(
                "candlekeepTrainingEquipment",
                encodeData({slot: item.getName() for slot, item in player.getEquipped().items() if item}),
            )
            player.setNumericProperty("candlekeepTrainingHp", player.getHp())
            player.setNumericProperty("candlekeepTrainingMana", player.getNumericProperty("mana"))
            player.setStringProperty("affiliation", "candlekeepTraining")
            setStage(game_map, "training", "active")
            game_map.setNumericProperty("candlekeepTrainingRound", 1)
            game_map.setNumericProperty("candlekeepTrainingTurns", 0)
            game_map.setNumericProperty("candlekeepTrainingTurnLimit", 120)
            self.spawnTrainingWave()
            return True

        def spawnTrainingWave(self):
            if not self._progressAllowed():
                return False
            game_map = self.getGame().getMap()
            for index in range(1, 7):
                spawn(game_map, "candlekeepTrainingFoe", (26 + index * 2, 48, 1), "trainingFoe" + str(index))
            for index, name in enumerate(TRAINING_ALLIES):
                ally = spawn(
                    game_map, "candlekeepTraining" + name[:1].upper() + name[1:], (30 + index * 2, 44, 1), name
                )
                ally.setStringProperty("label", name[:1].upper() + name[1:])
                controller = self.getGame().createObject("CTargetController")
                controller.setStringProperty("target", "trainingFoe" + str(index + 2))
                ally.setController(controller)
                game_map.setBoolProperty("candlekeepTrainingParticipated_" + name, True)

        def trainingRound(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "obe":
                return False
            game_map = self.getGame().getMap()
            if stage(game_map, "training") != "active":
                return False
            if any(game_map.getObjectByName("trainingFoe" + str(i)) for i in range(1, 7)):
                return False
            rounds = game_map.getNumericProperty("candlekeepTrainingRound")
            if rounds >= 2:
                return self.finishTraining()
            removeTraining(game_map)
            game_map.setNumericProperty("candlekeepTrainingRound", rounds + 1)
            self.spawnTrainingWave()
            return True

        def finishTraining(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "obe":
                return False
            if self.getGame().getMap().getNumericProperty("candlekeepTrainingRound") < 2:
                return False
            game_map = self.getGame().getMap()
            if stage(game_map, "training") != "active":
                return False
            if any(game_map.getObjectByName("trainingFoe" + str(i)) for i in range(1, 7)):
                return False
            restoreTraining(game_map, "completed")
            game_map.setBoolProperty("candlekeepTrainingCompleted", True)
            return True

        @resumableHook
        def forceExitTraining(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "obe":
                return
            restoreTraining(self.getGame().getMap(), "abandoned")
            playerFor(self).setStringProperty("candlekeepPortalGuard", "trainingEntrance")
            entrance = self.getGame().getMap().getObjectByName("trainingEntrance").getCoords()
            yield uiRequest("gui.moveTo", playerFor(self), entrance.x, entrance.y, entrance.z)
            self.getGame().getMap().setBoolProperty("candlekeepTrainingForcedExit", True)

        def practiceCombat(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "jondalar":
                return False
            if not claim_once(self.getGame().getMap(), "candlekeepJondalarStarted"):
                return False
            spawn(self.getGame().getMap(), "candlekeepPracticeFoe", (51, 21, 0), "jondalarPracticeFoe")
            notify(self, "Erik calls the start of the exercise. Defeat the practice opponent, then speak again.")
            return True

        @resumableHook
        def inspectCompanion(self):
            if self.actorId() not in TRAINING_ALLIES or not self.actor():
                return
            actor = self.actor()
            actions = sorted(
                action.getStringProperty("label") or action.getTypeId() for action in actor.getEffectiveInteractions()
            )
            equipment = sorted(item.getStringProperty("label") or item.getTypeId() for item in actor.getItems())
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                actor.getStringProperty("label"),
                "Temporary training companion. Native actions: "
                + ", ".join(actions)
                + ". Carried equipment: "
                + (", ".join(equipment) or "none")
                + ". All training equipment is returned when the exercise ends.",
            )

        def borrowSelectedEquipment(self):
            if not self._progressAllowed():
                return False
            if self.actorId() not in TRAINING_ALLIES or stage(self.getGame().getMap(), "training") != "active":
                return False
            actor = self.actor()
            if not actor:
                return False
            selected = self.getStringProperty("selectedBorrow")
            item = firstMatch((item for item in actor.getItems() if item.getName() == selected), None)
            if not item:
                return False
            actor.removeItem(lambda candidate: candidate == item, False)
            if item in actor.getItems():
                return False
            item.setBoolProperty("plugin_candlekeepTemporary", True)
            playerFor(self).addItem(item)
            return True

        @resumableHook
        def borrowEquipment(self):
            if not self._progressAllowed():
                return False
            if (
                self.actorId() not in TRAINING_ALLIES
                or stage(self.getGame().getMap(), "training") != "active"
                or not self.actor()
            ):
                return
            rows = [
                {"id": item.getName(), "label": item.getStringProperty("label") or item.getTypeId()}
                for item in self.actor().getItems()
            ]
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Borrow training equipment", rows, "Borrow")
            if selected:
                self.setStringProperty("selectedBorrow", selected)
                self.borrowSelectedEquipment()

        @resumableHook
        def reviewPreparations(self):
            if self.actorId() not in ("gorion", "tutor8"):
                return
            player = playerFor(self)
            status = {
                "Dreppin shared the book clue": self.getGame().getMap().getBoolProperty("candlekeepDreppinBookHint"),
                "Nessa is cured": self.getGame().getMap().getBoolProperty("candlekeepNessaCured"),
                "Firebead cast his protection": self.getGame().getMap().getBoolProperty("candlekeepFirebeadProtected"),
                "You chose to keep the scroll": self.getGame().getMap().getBoolProperty("candlekeepScrollKept"),
                "You declined the infirmary gift": self.getGame()
                .getMap()
                .getBoolProperty("candlekeepClinicGiftDeclined"),
                "The Watch has been alerted": self.getGame().getMap().getBoolProperty("candlekeepGuardsAlerted"),
                "Jondalar's lesson is completed": self.getGame()
                .getMap()
                .getBoolProperty("candlekeepJondalarCompleted"),
                "Obe's exercise is completed": self.getGame().getMap().getBoolProperty("candlekeepTrainingCompleted"),
                "Obe returned you outside": self.getGame().getMap().getBoolProperty("candlekeepTrainingForcedExit"),
                "The exercise reached its turn limit": self.getGame()
                .getMap()
                .getBoolProperty("candlekeepTrainingTimedOut"),
                "You were defeated during training": self.getGame()
                .getMap()
                .getBoolProperty("candlekeepTrainingDefeat"),
                "Gorion has shared his advice": self.getGame().getMap().getBoolProperty("candlekeepGorionAdvice"),
                "You postponed departure": self.getGame().getMap().getBoolProperty("candlekeepDepartureRefused"),
                "The departure epilogue has been shown": self.getGame()
                .getMap()
                .getBoolProperty("candlekeepEpilogueShown"),
            }
            lines = ["Gold: " + str(player.getGold())]
            lines.extend(
                actor[:1].upper() + actor[1:] + ": " + stage(self.getGame().getMap(), actor) for actor in QUEST_ACTORS
            )
            lines.extend(label + ": " + ("yes" if value else "no") for label, value in status.items())
            yield uiRequest("showReader", flowGame(self.getGame()), "Candlekeep preparations", "\n".join(lines))

        def refuseDeparture(self):
            if not self._progressAllowed():
                return False
            if self.actorId() != "gorion":
                return False
            self.getGame().getMap().setBoolProperty("candlekeepDepartureRefused", True)

        @resumableHook
        def leaveCandlekeep(self):
            if self.actorId() != "gorion" or not self._progressAllowed():
                return
            if self.getGame().getMap().getBoolProperty("candlekeepDeparted"):
                return
            self.getGame().getMap().setBoolProperty("candlekeepDeparted", True)
            restoreTraining(self.getGame().getMap(), "abandoned")
            playerFor(self).heal(0)
            self.getGame().getMap().setBoolProperty("candlekeepGorionAdvice", True)
            self.getGame().getMap().setBoolProperty("candlekeepEpilogueShown", True)
            creatures = (
                NPC_IDS + ("shank", "carbos", "jondalarPracticeFoe") + tuple("rat" + str(i) for i in range(1, 6))
            )
            creatures += tuple(
                "candlekeepWatch" + str(i)
                for i in range(
                    1,
                    max(
                        self.getGame().getMap().getNumericProperty("candlekeepCrimes"),
                        self.getGame().getMap().getNumericProperty("candlekeepWatchersSpawned"),
                    )
                    + 1,
                )
            )
            for name in creatures:
                actor = self.getGame().getMap().getObjectByName(name)
                if actor:
                    actor.setBoolProperty("npc", True)
                    actor.setController(self.getGame().createObject("CController"))
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                "Beyond Candlekeep",
                "Gorion leads you through the gate. He has named Khalid and Jaheira, waiting at the Friendly Arm Inn, "
                "should you become separated. Candlekeep ends here; the road and its ambush belong to another chapter.",
            )

    @register(context)
    class CandlekeepPersonTrigger(CTrigger):
        @resumableHook
        def trigger(self, actor, event):
            if event and event.getCause() and event.getCause().isPlayer():
                if actor.getGame().getMap().getBoolProperty("candlekeepDeparted"):
                    notify(actor, "This adventure has ended. You may review your completed journal.")
                    return
                dialog = actor.getGame().createObject(actor.getName() + "Dialog")
                game_map = actor.getMap()
                name = actor.getName()
                if name == "firebead":
                    count = game_map.getNumericProperty("candlekeepFirebeadConversations") + 1
                    game_map.setNumericProperty("candlekeepFirebeadConversations", count)
                    if count >= 30 and claim_once(game_map, "candlekeepFirebeadThirtyTalks"):
                        playerFor(actor).addGold(300)
                if name == "dreppin":
                    count = game_map.getNumericProperty("candlekeepDreppinConversations") + 1
                    game_map.setNumericProperty("candlekeepDreppinConversations", count)
                    game_map.setBoolProperty("candlekeepDreppinBookHint", True)
                    if count >= 2 and dialog.canAcceptQuest():
                        dialog.acceptQuest()
                elif name in ("firebead", "phlydia", "hull", "reevor") and dialog.canAcceptQuest():
                    dialog.acceptQuest()
                yield uiRequest("gui.showDialog", dialog)

    @register(context)
    class CandlekeepDeathTrigger(CTrigger):
        def trigger(self, actor, event):
            game_map, name = actor.getMap(), actor.getName()
            if not game_map or actor.isAlive() or game_map.getBoolProperty("candlekeepDeparted"):
                return
            if name.startswith("trainingFoe"):
                game_map.setNumericProperty(
                    "candlekeepTrainingFoesDefeated", game_map.getNumericProperty("candlekeepTrainingFoesDefeated") + 1
                )
                return
            if name in TRAINING_ALLIES:
                game_map.setBoolProperty("candlekeepTrainingDown_" + name, True)
                return
            if not claim_once(game_map, "candlekeep_" + name + "Slain"):
                return
            if name.startswith("rat"):
                game_map.setNumericProperty(
                    "candlekeepRatsSlain", game_map.getNumericProperty("candlekeepRatsSlain") + 1
                )
                game_map.setBoolProperty("candlekeepRat" + name[3:] + "Slain", True)
                game_map.getPlayer().addExp(1)
            elif name in ("shank", "carbos"):
                game_map.getPlayer().addExp(20)
                notify(actor, "An assassin lies dead. A worried tutor waits just outside.")
            elif name == "jondalarPracticeFoe":
                game_map.setBoolProperty("candlekeepJondalarCompleted", True)
            else:
                game_map.setNumericProperty("candlekeepStanding", game_map.getNumericProperty("candlekeepStanding") - 5)
                game_map.setBoolProperty("candlekeepMurder_" + name, True)

    @trigger(context, "onTurn", "obe")
    class CandlekeepTrainingTimerTrigger(CTrigger):
        @resumableHook
        def trigger(self, actor, event):
            game_map = actor.getMap()
            if not game_map or stage(game_map, "training") != "active":
                return
            if game_map.getBoolProperty("candlekeepTrainingDefeatPending"):
                restoreTraining(game_map, "abandoned")
                game_map.setBoolProperty("candlekeepTrainingForcedExit", True)
                entrance = game_map.getObjectByName("trainingEntrance").getCoords()
                player = game_map.getPlayer()
                player.setStringProperty("candlekeepPortalGuard", "trainingEntrance")
                yield uiRequest("gui.moveTo", player, entrance.x, entrance.y, entrance.z)
                notify(
                    actor, "The exercise ends after your defeat. Your original condition and equipment are restored."
                )
                return
            elapsed = game_map.getNumericProperty("candlekeepTrainingTurns") + 1
            game_map.setNumericProperty("candlekeepTrainingTurns", elapsed)
            limit = game_map.getNumericProperty("candlekeepTrainingTurnLimit") or 120
            if elapsed < limit:
                return
            restoreTraining(game_map, "abandoned")
            game_map.setBoolProperty("candlekeepTrainingForcedExit", True)
            game_map.setBoolProperty("candlekeepTrainingTimedOut", True)
            entrance = game_map.getObjectByName("trainingEntrance").getCoords()
            player = game_map.getPlayer()
            player.setStringProperty("candlekeepPortalGuard", "trainingEntrance")
            yield uiRequest("gui.moveTo", player, entrance.x, entrance.y, entrance.z)
            notify(actor, "Obe ends the bounded exercise after 120 map turns and returns you to the courtyard.")

    @register(context)
    class CandlekeepTrainingDefeatTrigger(CTrigger):
        def trigger(self, actor, event):
            game_map = actor.getMap()
            if game_map and stage(game_map, "training") == "active":
                reclaimTrainingInventory(game_map)
                game_map.setBoolProperty("candlekeepTrainingDefeatPending", True)
                game_map.setBoolProperty("candlekeepTrainingDefeat", True)

    for name in NPC_IDS + TRAINING_ALLIES:
        trigger(context, "onEnter", name)(CandlekeepPersonTrigger)
    for name in (
        NPC_IDS
        + ("shank", "carbos", "jondalarPracticeFoe")
        + tuple("rat" + str(i) for i in range(1, 6))
        + TRAINING_ALLIES
        + tuple("trainingFoe" + str(i) for i in range(1, 7))
    ):
        trigger(context, "onDestroy", name)(CandlekeepDeathTrigger)
