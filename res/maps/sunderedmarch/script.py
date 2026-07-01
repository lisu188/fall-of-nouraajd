def load(self, context):
    from game import CDialog
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import register
    from game import trigger

    BOSS_SPAWN = (106, 106, 0)
    SEER_REWARD_GOLD = 300

    def ensure_quest(player, quest_name):
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def has_item(player, item_name):
        return player.hasItem(lambda it: it.getName() == item_name)

    def quest_flags_default(game_map):
        for flag in ("gate_open", "crown_taken", "boss_woken", "shrine_used", "seer_started", "seer_done"):
            if not hasattr(game_map, flag):
                game_map.setBoolProperty(flag, False)
        if not hasattr(game_map, "sigils_found"):
            game_map.setNumericProperty("sigils_found", 0)

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            player = game_map.getPlayer()
            quest_flags_default(game_map)
            game.getGuiHandler().showMessage(self.getStringProperty("text"))
            game_map.removeAll(lambda ob: ob.getName() == self.getName())
            ensure_quest(player, "sunderedMarchQuest")

    @register(context)
    class LearningStone(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            if game_map.getBoolProperty("shrine_used"):
                game.getGuiHandler().showMessage(
                    "The learning stone has taught you all it will. Its lesson does not repeat."
                )
                return
            player = game_map.getPlayer()
            player.addGold(100)
            player.healProc(60)
            game_map.setBoolProperty("shrine_used", True)
            game.getGuiHandler().showMessage(
                "You study the learning stone's campaign-marks until the old drills settle into your hands. "
                "You feel steadier, and a forgotten pay-chit of 100 gold falls from its hollow base."
            )

    @register(context)
    class Obelisk(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("counted"):
                return
            self.setBoolProperty("counted", True)
            game_map = self.getMap()
            game_map.incProperty("sigils_found", 1)
            found = game_map.getNumericProperty("sigils_found")
            game = game_map.getGame()
            game.getGuiHandler().showInfo(self.getStringProperty("text"), True)
            game.getGuiHandler().showMessage(
                f"A barrow-sigil burns itself into your memory. ({found}/3 obelisks read.)"
            )

    @register(context)
    class KeymasterCache(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("looted"):
                return
            self.setBoolProperty("looted", True)
            player = self.getMap().getPlayer()
            player.addItem("ironKey")
            self.getGame().getGuiHandler().showMessage(
                "You prise the March Keeper's iron key from his cache. Somewhere north, a barred gate is now only waiting."
            )

    @register(context)
    class GateThreshold(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            if game_map.getBoolProperty("gate_open"):
                return
            if has_item(game_map.getPlayer(), "ironKey"):
                game_map.removeObjectByName("borderGate")
                game_map.setBoolProperty("gate_open", True)
                game.getGuiHandler().showMessage(
                    "The Keeper's iron key turns, and the barred gate grinds open onto the barrow road."
                )
            else:
                game.getGuiHandler().showMessage(
                    "A barred iron gate blocks the pass. It will open only to the March Keeper's key - find his cache in the vale."
                )

    @register(context)
    class BannerCache(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("looted"):
                return
            self.setBoolProperty("looted", True)
            self.getMap().getPlayer().addItem("warBanner")
            self.getGame().getGuiHandler().showMessage(
                "You wrench the rotted War-Banner from the drowned colonel's grip. The fen sighs as the names on its hem come up into the light."
            )

    @register(context)
    class ArtifactCache(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("looted"):
                return
            self.setBoolProperty("looted", True)
            self.getMap().getPlayer().addItem("reaverBlade")
            self.getGame().getGuiHandler().showMessage(
                "The ash-buried artifact cache yields the Reaver of the March - a century of killing edge, and no curse to pay for it."
            )

    @register(context)
    class DigSite(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            player = game_map.getPlayer()
            if game_map.getBoolProperty("crown_taken"):
                return
            if game_map.getNumericProperty("sigils_found") < 3:
                found = game_map.getNumericProperty("sigils_found")
                game.getGuiHandler().showMessage(
                    f"The barrow ground stays hard as iron. Read all three obelisks before you dig. ({found}/3 read.)"
                )
                return
            player.addItem("barrowCrown")
            game_map.setBoolProperty("crown_taken", True)
            game.getGuiHandler().showMessage(
                "The three sigils sing and the barrow gives up its dead king. You lift the Crown of the Barrow-Warlord "
                "from the grave - and the grave lifts its owner after it. The cult has its crowned king at last, and it "
                "is wearing your face."
            )
            if not game_map.getBoolProperty("boss_woken"):
                boss = game.createObject("theBarrowWarlord")
                boss.setStringProperty("name", "theBarrowWarlordBoss")
                controller = game.createObject("CTargetController")
                controller.setTarget("player")
                boss.setController(controller)
                game_map.addObject(boss)
                boss.moveTo(*BOSS_SPAWN)
                game_map.setBoolProperty("boss_woken", True)

    @register(context)
    class SunderedMarchQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("crown_taken")

        def getObjective(self):
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty("crown_taken"):
                return "You wear the Crown of the Barrow-Warlord. The March has its king; end what the cult began."
            found = game_map.getNumericProperty("sigils_found")
            if game_map.getBoolProperty("gate_open"):
                return f"Read the three barrow-obelisks, then dig beneath the central barrow. ({found}/3 sigils read.)"
            return "Take the Keeper's iron key from the vale, then open the barred pass to the barrow."

        def getReward(self):
            return "The Crown of the Barrow-Warlord - a warlord's mind and edge, worn at the cost of the wearer's own will."

        def getHint(self):
            return "Key first, then the gate. The three obelisks stand in the vale, the fen, and the pyre. Monoliths shorten the road."

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage(
                "The crown is dug up and the March is 'saved' the only way the cult ever meant it to be - with a new dead king on the throne."
            )

    @register(context)
    class SeerHuntQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("seer_done")

        def getObjective(self):
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty("seer_done"):
                return "The Seer of the Pyre-Waste has her banner, and you have her boon."
            return (
                "Recover the War-Banner from the drowned barrow in the fen and bring it to the Seer in the Pyre-Waste."
            )

        def getReward(self):
            return "300 gold and a Greater Life Potion from the Seer's stores."

        def getHint(self):
            return "The banner is in the fen, guarded by a drowned colonel. The Seer wanders the ash-waste east."

        def onComplete(self):
            pass

    @register(context)
    class SeerDialog(CDialog):
        def can_return_banner(self):
            game_map = self.getGame().getMap()
            return (
                game_map.getBoolProperty("seer_started")
                and not game_map.getBoolProperty("seer_done")
                and has_item(game_map.getPlayer(), "warBanner")
            )

        def not_yet_started(self):
            return not self.getGame().getMap().getBoolProperty("seer_started")

        def start_seer_hunt(self):
            game_map = self.getGame().getMap()
            game_map.setBoolProperty("seer_started", True)
            ensure_quest(game_map.getPlayer(), "seerHuntQuest")

        def finish_seer_hunt(self):
            game_map = self.getGame().getMap()
            if not self.can_return_banner():
                return
            player = game_map.getPlayer()
            player.addGold(SEER_REWARD_GOLD)
            player.addItem("GreaterLifePotion")
            game_map.setBoolProperty("seer_done", True)
            self.getGame().getGuiHandler().showMessage(
                "The Seer reads the drowned names off the banner's hem, pays you 300 gold and a Greater Life Potion, "
                "and tells you the thing you did not want to know: the crown is meant for your head."
            )

    @trigger(context, "onEnter", "seerHut")
    class SeerTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("seerDialog"))

    @trigger(context, "onDestroy", "valeGuard")
    class ValeGuardTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "fenGuard")
    class FenGuardTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "pyreGuard")
    class PyreGuardTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "barrowGuard")
    class BarrowGuardTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "theBarrowWarlordBoss")
    class BarrowWarlordTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(
                "The Crowned Barrow-Warlord falls a second and final time. The plague-crown cracks on the stones, "
                "and for the first time in a hundred years the Sundered March is only quiet - not waiting."
            )
