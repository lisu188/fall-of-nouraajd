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
    CAMPAIGN_OUTCOMES = ("completed",)

    VICTORY_GOLD_REWARD = 150

    def ensure_quest(player, quest_name):
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def hearthfall_flags_default(game_map):
        for flag in ("hearthfall_intro", "captain_defeated", "victory_reported", "victory_reward_claimed"):
            if not game_map.getBoolProperty(flag):
                game_map.setBoolProperty(flag, False)

    @register(context)
    class HearthfallStart(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            hearthfall_flags_default(game_map)
            if game_map.getBoolProperty("hearthfall_intro"):
                return
            game_map.setBoolProperty("hearthfall_intro", True)
            game_map.getGame().getGuiHandler().showMessage(self.getStringProperty("text"))
            game_map.removeAll(lambda ob: ob.getName() == self.getName())
            ensure_quest(event.getCause(), "hearthfallQuest")

    @register(context)
    class HearthfallQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("captain_defeated")

        def getObjective(self):
            game_map = self.getGame().getMap()
            if not game_map.getBoolProperty("captain_defeated"):
                return "Defeat Watch-Captain Osric and break the occupation of Hearthfall."
            if not game_map.getBoolProperty("victory_reported"):
                return "Bring word of the captain's fall to Elder Maren."
            return "Hearthfall is free. The road leads north into the Gravemoor."

        def getReward(self):
            return f"{VICTORY_GOLD_REWARD} gold from the village's hidden purse, and the road north."

        def getHint(self):
            return "The watch-captain holds the walled square at the village's heart."

        def onComplete(self):
            pass

    @register(context)
    class ElderDialog(CDialog):
        def still_occupied(self):
            return not self.getGame().getMap().getBoolProperty("captain_defeated")

        def captain_down(self):
            game_map = self.getGame().getMap()
            return game_map.getBoolProperty("captain_defeated") and not game_map.getBoolProperty("victory_reported")

        def victory_reported(self):
            return self.getGame().getMap().getBoolProperty("victory_reported")

        def report_victory(self):
            game_map = self.getGame().getMap()
            if not self.captain_down():
                return
            game_map.setBoolProperty("victory_reported", True)
            if claim_once(game_map, "victory_reward_claimed"):
                player = game_map.getPlayer()
                player.addGold(VICTORY_GOLD_REWARD)
                player.checkQuests()
                self.getGame().getGuiHandler().showMessage(
                    "Maren presses the village's hidden purse into your hands. 'The Gravemoor holds our people. "
                    "Bring them home, Warden.'"
                )
            campaign.complete_scenario(self.getGame(), "completed", fallback_map="gravemoor")

    @trigger(context, "onEnter", "elderMaren")
    class ElderTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("elderDialog"))

    @trigger(context, "onDestroy", "watchCaptain")
    class CaptainTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getMap()
            if game_map.getBoolProperty("captain_defeated"):
                return
            game_map.setBoolProperty("captain_defeated", True)
            object.getGame().getGuiHandler().showMessage(
                "Osric drops with the occupation banner still in his fist. The square is yours - "
                "bring Elder Maren the news."
            )

    @trigger(context, "onDestroy", "occupierGate")
    class GateSentryTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage("The gate sentry falls. The road into Hearthfall stands open.")
