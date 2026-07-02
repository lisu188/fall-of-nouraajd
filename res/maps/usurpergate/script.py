def load(self, context):
    from game import CDialog
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import claim_once
    from game import register
    from game import trigger

    # The plugin sandbox only allows importing the game and json modules;
    # game re-exports the campaign driver (res/campaign.py) as an attribute.
    from game import campaign

    # Scenario outcomes this map reports through campaign.complete_scenario;
    # campaign manifests route them (see docs/design/multilevel_campaign.md).
    # This is the final chapter of the Warden's Road campaign, so both routed
    # scenario nodes that use this map are terminal.
    CAMPAIGN_OUTCOMES = ("completed",)

    THRONE_GOLD_REWARD = 500

    def ensure_quest(player, quest_name):
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def usurpergate_flags_default(game_map):
        for flag in ("usurpergate_intro", "usurper_defeated", "throne_taken", "throne_reward_claimed"):
            if not game_map.getBoolProperty(flag):
                game_map.setBoolProperty(flag, False)

    @register(context)
    class UsurpergateStart(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            usurpergate_flags_default(game_map)
            if game_map.getBoolProperty("usurpergate_intro"):
                return
            game_map.setBoolProperty("usurpergate_intro", True)
            game_map.getGame().getGuiHandler().showMessage(self.getStringProperty("text"))
            game_map.removeAll(lambda ob: ob.getName() == self.getName())
            ensure_quest(event.getCause(), "usurpergateQuest")

    @register(context)
    class ObsidianThrone(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            usurpergate_flags_default(game_map)
            if game_map.getBoolProperty("throne_taken"):
                return
            if not game_map.getBoolProperty("usurper_defeated"):
                game_map.getGame().getGuiHandler().showMessage(
                    "The obsidian throne is cold and near - but the Usurper still commands the court behind you. "
                    "No one sits while he stands."
                )
                return
            game_map.setBoolProperty("throne_taken", True)
            if claim_once(game_map, "throne_reward_claimed"):
                player = game_map.getPlayer()
                player.addGold(THRONE_GOLD_REWARD)
                player.checkQuests()
                game_map.getGame().getGuiHandler().showMessage(
                    "You take the obsidian throne of the Wardenskeep. The treasury the Usurper hoarded - "
                    f"{THRONE_GOLD_REWARD} gold - returns to the marches, and the marches return to their Warden."
                )
            campaign.complete_scenario(self.getGame(), "completed")

    @register(context)
    class UsurpergateQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("throne_taken")

        def getObjective(self):
            game_map = self.getGame().getMap()
            if not game_map.getBoolProperty("usurper_defeated"):
                return "Breach the curtain wall and defeat the Usurper of the Marches."
            if not game_map.getBoolProperty("throne_taken"):
                return "Take your seat on the obsidian throne."
            return "The Wardenskeep is yours. The marches have their Warden again."

        def getReward(self):
            return f"The Wardenskeep, its {THRONE_GOLD_REWARD}-gold treasury, and the end of the Usurper's line."

        def getHint(self):
            return "The breach in the curtain wall is held by housecarls; the Usurper waits in the inner court."

        def onComplete(self):
            pass

    @register(context)
    class BanneretDialog(CDialog):
        def usurper_stands(self):
            return not self.getGame().getMap().getBoolProperty("usurper_defeated")

        def throne_waits(self):
            game_map = self.getGame().getMap()
            return game_map.getBoolProperty("usurper_defeated") and not game_map.getBoolProperty("throne_taken")

        def keep_retaken(self):
            return self.getGame().getMap().getBoolProperty("throne_taken")

    @trigger(context, "onEnter", "banneretHild")
    class BanneretTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("banneretDialog"))

    @trigger(context, "onDestroy", "theUsurper")
    class UsurperTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getMap()
            if game_map.getBoolProperty("usurper_defeated"):
                return
            game_map.setBoolProperty("usurper_defeated", True)
            object.getGame().getGuiHandler().showMessage(
                "The Usurper falls at the foot of the dais, crown rolling from his hand. "
                "The obsidian throne stands empty. Go and sit."
            )

    @trigger(context, "onDestroy", "housecarlEast")
    class BreachGuardTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage(
                "The breach guard falls. The inner court lies open."
            )
