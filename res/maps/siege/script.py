def load(self, context):
    from game import CTag
    from game import CCreature
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import register
    from game import trigger
    from game import randint
    from game import logger
    from game import claim_once

    # The plugin sandbox only allows importing the game and json modules;
    # game re-exports the campaign driver (res/campaign.py) as an attribute.
    from game import campaign

    # Scenario outcomes this map reports through campaign.complete_scenario;
    # campaign manifests route them (see docs/design/multilevel_campaign.md).
    # This is the final chapter of the shipped campaign, so there is no
    # standalone fallback map.
    CAMPAIGN_OUTCOMES = ("completed",)

    SPAWN_POINTS = ("spawnPoint1", "spawnPoint2", "spawnPoint3", "spawnPoint4")

    def destroyed_gate_count(game_map):
        count = 0
        for name in SPAWN_POINTS:
            gate = game_map.getObjectByName(name)
            if gate and gate.getBoolProperty("destroyed"):
                count += 1
        return count

    def ensure_siege_quest(player):
        for quest in player.getQuests():
            if quest.getName() == "defendSiegeQuest" or quest.getTypeId() == "defendSiegeQuest":
                return
        player.addQuest("defendSiegeQuest")

    @register(context)
    class SiegeStartEvent(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            if game_map.getBoolProperty("siege_initialized"):
                return
            game_map.setBoolProperty("siege_initialized", True)
            player = game_map.getPlayer()
            ensure_siege_quest(player)
            player.addItem("magicWand")
            game_map.getGame().getGuiHandler().showMessage(
                "The road ends at a besieged gatehouse. Seal each breach with mage-wands before the attackers "
                "overrun it."
            )

    @register(context)
    class DefendSiegeQuest(CQuest):
        def isCompleted(self):
            return destroyed_gate_count(self.getGame().getMap()) == len(SPAWN_POINTS)

        def getObjective(self):
            sealed = destroyed_gate_count(self.getGame().getMap())
            return f"Seal every siege gate with charged wands ({sealed}/{len(SPAWN_POINTS)} sealed)."

        def getReward(self):
            return "500 gold and final campaign completion."

        def getHint(self):
            return "Pritz mages carry extra wands; defeat them if you run out."

        def onComplete(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            # Claim-first: claim the campaign reward before granting gold or marking completion so a
            # repeated completion cannot pay the 500 gold twice.
            if not claim_once(game_map, "siege_reward_claimed"):
                return
            player.addGold(500)
            game_map.setBoolProperty("campaign_completed", True)
            self.getGame().getGuiHandler().showMessage("The last breach is sealed. Nouraajd survives the night.")
            campaign.complete_scenario(self.getGame(), "completed")

    @register(context)
    class SpawnPoint(CEvent):
        def onCreate(self, event):
            self.setStringProperty("animation", "images/misc/closed_door")
            self.setBoolProperty("enabled", False)
            self.setBoolProperty("destroyed", False)
            self.setBoolProperty("pendingSeal", False)

        def hasCreatureAtGate(self):
            game_map = self.getMap()
            for ob in game_map.getObjectsAtCoords(self.getCoords()):
                if not isinstance(ob, CCreature):
                    continue
                if not ob.isAlive():
                    continue
                if game_map.getObjectByName(ob.getName()) is None:
                    continue
                return True
            return False

        def completePendingSeal(self):
            if self.hasCreatureAtGate():
                return
            self.setBoolProperty("canStep", False)
            self.setBoolProperty("pendingSeal", False)

        def onTurn(self, event):
            if self.getBoolProperty("destroyed") and self.getBoolProperty("pendingSeal"):
                self.completePendingSeal()
                return
            if self.getBoolProperty("enabled") and not self.getBoolProperty("destroyed") and randint(1, 10) == 10:
                logger("Spawning new creature")
                if randint(1, 10) == 10:
                    logger("Spawning mage")
                    self.getMap().addObjectByName("siegePritzMage", self.getCoords())
                else:
                    logger("Spawning grunt")
                    self.getMap().addObjectByName("siegePritz", self.getCoords())

        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if (
                not self.getBoolProperty("enabled")
                or self.getBoolProperty("pendingSeal")
                or self.getBoolProperty("destroyed")
            ):
                return
            if self.getMap().getPlayer().hasItem(lambda it: it.hasTag(CTag.WAND)):
                if self.getMap().getGame().getGuiHandler().showQuestion("Do You want to seal the gate?"):
                    self.getMap().getPlayer().removeQuestItem(lambda it: it.hasTag(CTag.WAND))
                    self.setBoolProperty("enabled", False)
                    self.setBoolProperty("destroyed", True)
                    self.setBoolProperty("pendingSeal", True)
                    self.setStringProperty("animation", "images/misc/closed_door")
                    self.completePendingSeal()
            else:
                self.getMap().getGame().getGuiHandler().showInfo("You need a wand to seal the gate!")

    @trigger(context, "onTurn", "triggerAnchor")
    class TurnTrigger(CTrigger):
        def trigger(self, object, event):
            if randint(1, 25) == 25:
                event.cont = True

                def enableSpawn(spawnObject):
                    logger("Spawning gate")
                    spawnObject.getMap().replaceTile("SwampTile", spawnObject.getCoords())
                    spawnObject.setBoolProperty("enabled", True)
                    # TODO: autoexport set get property
                    spawnObject.setStringProperty("animation", "images/misc/open_door")
                    event.cont = False

                object.getMap().forObjects(
                    enableSpawn,
                    lambda ob: event.cont
                    and ob.getStringProperty("type") == "SpawnPoint"
                    and not ob.getBoolProperty("enabled")
                    and not ob.getBoolProperty("destroyed"),
                )
