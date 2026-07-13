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
    # Both outcomes complete the scenario: they are the two judgments the
    # Warden can pass on the traitor quartermaster.
    CAMPAIGN_OUTCOMES = ("spared", "executed")

    CAGE_COUNT = 3
    SPARE_GOLD_REWARD = 200
    EXECUTE_GOLD_REWARD = 100

    def ensure_quest(player, quest_name):
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def gravemoor_flags_default(game_map):
        for flag in ("gravemoor_intro", "voss_judged", "voss_spared", "judgment_reward_claimed"):
            if not game_map.getBoolProperty(flag):
                game_map.setBoolProperty(flag, False)
        if game_map.getNumericProperty("loyalists_freed") < 0:
            game_map.setNumericProperty("loyalists_freed", 0)

    def all_cages_open(game_map):
        return game_map.getNumericProperty("loyalists_freed") >= CAGE_COUNT

    @register(context)
    class GravemoorStart(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            gravemoor_flags_default(game_map)
            if game_map.getBoolProperty("gravemoor_intro"):
                return
            game_map.setBoolProperty("gravemoor_intro", True)
            game_map.getGame().getGuiHandler().showMessage(self.getStringProperty("text"))
            game_map.removeAll(lambda ob: ob.getName() == self.getName())
            ensure_quest(event.getCause(), "gravemoorQuest")

    @register(context)
    class LoyalistCage(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            gravemoor_flags_default(game_map)
            game_map.setNumericProperty("loyalists_freed", game_map.getNumericProperty("loyalists_freed") + 1)
            game_map.getGame().getGuiHandler().showMessage(self.getStringProperty("text"))
            if all_cages_open(game_map):
                game_map.getGame().getGuiHandler().showMessage(
                    "All three cages stand open. The freed loyalists gather at the crossroads, waiting on the "
                    "Warden's judgment of Quartermaster Voss."
                )
            game_map.removeAll(lambda ob: ob.getName() == self.getName())

    @register(context)
    class GravemoorQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("voss_judged")

        def getObjective(self):
            game_map = self.getGame().getMap()
            freed = game_map.getNumericProperty("loyalists_freed")
            if freed < CAGE_COUNT:
                return f"Free the caged loyalists from the barrow-crypts ({freed}/{CAGE_COUNT} freed)."
            if not game_map.getBoolProperty("voss_judged"):
                return "Pass judgment on Quartermaster Voss at the crossroads."
            if game_map.getBoolProperty("voss_spared"):
                return "Voss lives in the Warden's debt. The Usurper's Gate lies ahead."
            return "The moor keeps the traitor. The Usurper's Gate lies ahead."

        def getReward(self):
            return "The loyalists of the marches - and whatever a traitor's fate is worth."

        def getHint(self):
            return "The cages sit in the west, east, and north barrows; their wardens will not give them up freely."

        def onComplete(self):
            pass

    @register(context)
    class VossDialog(CDialog):
        def captives_missing(self):
            game_map = self.getGame().getMap()
            return not all_cages_open(game_map) and not game_map.getBoolProperty("voss_judged")

        def ready_to_judge(self):
            game_map = self.getGame().getMap()
            return all_cages_open(game_map) and not game_map.getBoolProperty("voss_judged")

        def already_judged(self):
            return self.getGame().getMap().getBoolProperty("voss_judged")

        def _pass_judgment(self, spared):
            game_map = self.getGame().getMap()
            if not self.ready_to_judge():
                return False
            game_map.setBoolProperty("voss_judged", True)
            game_map.setBoolProperty("voss_spared", spared)
            game_map.getPlayer().checkQuests()
            return True

        def spare_voss(self):
            game_map = self.getGame().getMap()
            if not self._pass_judgment(True):
                return
            if claim_once(game_map, "judgment_reward_claimed"):
                game_map.getPlayer().addGold(SPARE_GOLD_REWARD)
                self.getGame().getGuiHandler().showMessage(
                    "Voss chokes out where the occupation pay-chests are cached - "
                    f"{SPARE_GOLD_REWARD} gold - and swears his ledgers to the Warden's cause. "
                    "The loyalists watch you spare him, and remember."
                )
            campaign.complete_scenario(self.getGame(), "spared", fallback_map="usurpergate")

        def execute_voss(self):
            game_map = self.getGame().getMap()
            if not self._pass_judgment(False):
                return
            if claim_once(game_map, "judgment_reward_claimed"):
                game_map.getPlayer().addGold(EXECUTE_GOLD_REWARD)
                self.getGame().getGuiHandler().showMessage(
                    f"The moor takes the traitor. His purse - {EXECUTE_GOLD_REWARD} gold - goes to the freed. "
                    "The loyalists watch you do it, and remember that too."
                )
            campaign.complete_scenario(self.getGame(), "executed", fallback_map="usurpergate")

    @trigger(context, "onEnter", "quartermasterVoss")
    class VossTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("vossDialog"))
