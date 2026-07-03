def load(self, context):
    from game import CDialog
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import register
    from game import trigger

    BOSS_SPAWN = (500, 466, 0)

    # ---- helpers ----
    def ensure_quest(player, quest_name):
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def has_item(player, item_name):
        return player.hasItem(lambda it: it.getName() == item_name)

    def reputation(game_map):
        return game_map.getPlayer().getNumericProperty("reputation")

    def adjust_reputation(game_map, delta):
        player = game_map.getPlayer()
        player.setNumericProperty("reputation", player.getNumericProperty("reputation") + delta)

    def bump_chapter(game_map, chapter):
        if game_map.getNumericProperty("chapter") < chapter:
            game_map.setNumericProperty("chapter", chapter)

    MAP_BOOLS = (
        "iron_gate_open",
        "bone_gate_open",
        "brass_gate_open",
        "crown_taken",
        "boss_woken",
        "shrine_used",
        "witch_used",
        "mine_claimed",
        "halda_started",
        "halda_joined",
        "halda_left",
        "morrigane_started",
        "morrigane_joined",
        "morrigane_left",
        "corvyn_started",
        "corvyn_joined",
        "corvyn_left",
    )

    def quest_flags_default(game_map):
        for flag in MAP_BOOLS:
            if not hasattr(game_map, flag):
                game_map.setBoolProperty(flag, False)
        if not hasattr(game_map, "obelisks_read"):
            game_map.setNumericProperty("obelisks_read", 0)
        if not hasattr(game_map, "chapter"):
            game_map.setNumericProperty("chapter", 1)
        player = game_map.getPlayer()
        if not hasattr(player, "reputation"):
            player.setNumericProperty("reputation", 0)

    # ---- arrival ----
    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            quest_flags_default(game_map)
            game.getGuiHandler().showMessage(self.getStringProperty("text"))
            game_map.removeAll(lambda ob: ob.getName() == self.getName())
            ensure_quest(game_map.getPlayer(), "ninemarchesQuest")

    # ---- Heroes-3 structures ----
    @register(context)
    class LearningStone(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            if game_map.getBoolProperty("shrine_used"):
                game.getGuiHandler().showMessage("The learning stone has taught you all it will.")
                return
            player = game_map.getPlayer()
            player.addGold(120)
            player.healProc(80)
            game_map.setBoolProperty("shrine_used", True)
            # Gravewatch's scroll-crafting unlock: the crafting plugin reads this
            # map flag through the scribe recipes' unlockFlag configuration.
            game_map.setBoolProperty("CAN_CRAFT_SCROLLS", True)
            game.getGuiHandler().showMessage(
                "You study Gravewatch's learning stone until the old drill-marks settle into your hands. You feel "
                "steadier, and 120 gold in forgotten muster-pay falls from its hollow base. Among the drill-marks "
                "you learn the scribe's copying-craft - Gravewatch's scribe desk will serve you now."
            )

    @register(context)
    class WitchHut(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            if game_map.getBoolProperty("witch_used"):
                game.getGuiHandler().showMessage("The witch-hut's cauldron has gone cold; its boon is already spent.")
                return
            player = game_map.getPlayer()
            player.healProc(150)
            adjust_reputation(game_map, 1)
            game_map.setBoolProperty("witch_used", True)
            game.getGuiHandler().showMessage(
                "The fen witch-hut's cauldron reads your marches-luck and mends you head to heel. The marches note "
                "the courtesy of asking first."
            )

    @register(context)
    class GoldMine(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            if game_map.getBoolProperty("mine_claimed"):
                game.getGuiHandler().showMessage("The grave-gold mine is already yours; its guards are already dead.")
                return
            game_map.getPlayer().addGold(int(self.getNumericProperty("value")))
            game_map.setBoolProperty("mine_claimed", True)
            game.getGuiHandler().showMessage(
                "You take the Ashmarch grave-gold mine from the cult that worked it. Its takings are yours - blood-gold, "
                "but spendable."
            )

    @register(context)
    class KeymasterCache(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("looted"):
                return
            self.setBoolProperty("looted", True)
            self.getMap().getPlayer().addItem(self.getStringProperty("grants"))
            self.getGame().getGuiHandler().showMessage(
                f"You prise the {self.getStringProperty('color')} march-key from the Keeper's cache. One more gate "
                "in the marches is now only waiting."
            )

    @register(context)
    class GateThreshold(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            flag = self.getStringProperty("flag")
            if game_map.getBoolProperty(flag):
                return
            if has_item(game_map.getPlayer(), self.getStringProperty("key")):
                game_map.removeObjectByName(self.getStringProperty("gate"))
                game_map.setBoolProperty(flag, True)
                bump_chapter(game_map, int(self.getNumericProperty("chapter")))
                game.getGuiHandler().showMessage(
                    "The march-key turns, and the barred gate grinds open onto the deeper marches."
                )
            else:
                game.getGuiHandler().showMessage(
                    "A barred march-gate blocks the road. It opens only to the Keeper's key of the matching make - "
                    "find its cache."
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
            game_map.incProperty("obelisks_read", 1)
            read = game_map.getNumericProperty("obelisks_read")
            game = game_map.getGame()
            game.getGuiHandler().showInfo(self.getStringProperty("text"), True)
            game.getGuiHandler().showMessage(f"A march-sigil burns into your memory. ({read}/6 obelisks read.)")

    @register(context)
    class ItemCache(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("looted"):
                return
            self.setBoolProperty("looted", True)
            self.getMap().getPlayer().addItem(self.getStringProperty("grants"))
            self.getGame().getGuiHandler().showMessage(
                "You recover something a companion in the marches has been waiting for."
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
            if game_map.getNumericProperty("obelisks_read") < 6:
                read = game_map.getNumericProperty("obelisks_read")
                game.getGuiHandler().showMessage(
                    f"The Citadel ground stays hard as a god's jaw. Read all six march-obelisks before you dig. ({read}/6 read.)"
                )
                return
            player.addItem("ninefoldCrown")
            game_map.setBoolProperty("crown_taken", True)
            bump_chapter(game_map, 4)
            game.getGuiHandler().showMessage(
                "The six sigils sing as one and the Cyclopean Citadel gives up its god. You lift the Ninefold Crown "
                "from the grave - and the grave lifts its owner after it. The cult has its crowned king at last, and "
                "it is wearing your face."
            )
            if not game_map.getBoolProperty("boss_woken"):
                boss = game.createObject("theNinefoldKing")
                boss.setStringProperty("name", "theNinefoldKingBoss")
                controller = game.createObject("CTargetController")
                controller.setTarget("player")
                boss.setController(controller)
                game_map.addObject(boss)
                boss.moveTo(*BOSS_SPAWN)
                game_map.setBoolProperty("boss_woken", True)

    # ---- Quests ----
    @register(context)
    class NineMarchesQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("crown_taken")

        def getObjective(self):
            game_map = self.getGame().getMap()
            chapter = int(game_map.getNumericProperty("chapter"))
            read = int(game_map.getNumericProperty("obelisks_read"))
            if game_map.getBoolProperty("crown_taken"):
                return "Chapter IV. You wear the Ninefold Crown. End what the Ninefold Crowning began."
            if read >= 6:
                return "Chapter IV. All six obelisks are read. Dig the grave-crown at the Cyclopean Citadel."
            if chapter >= 2:
                return f"Chapter {max(2, chapter)}. Read the six march-obelisks and win the keys to the deeper marches. ({read}/6 read.)"
            return "Chapter I. Take the iron march-key in the Reaved Fields and open the inner pass toward the Citadel."

        def getReward(self):
            game_map = self.getGame().getMap()
            allies = [
                n
                for n, f in (
                    ("Ser Halda", "halda_joined"),
                    ("Morrigane", "morrigane_joined"),
                    ("Corvyn", "corvyn_joined"),
                )
                if game_map.getBoolProperty(f)
            ]
            allies_text = (" Allies at your side: " + ", ".join(allies) + ".") if allies else ""
            return "The Ninefold Crown - a god's cold mind, worn at the cost of your own will." + allies_text

        def getHint(self):
            return "Keys open the roads; obelisks open the grave. Recruit the marches' lost - a knight, a witch, a turncoat - before the Citadel."

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage(
                "The crown is dug up and the Nine Marches are 'saved' the only way the cult ever meant - with a new "
                "dead god on the throne of the world, and your name the last it answered to."
            )

    class CompanionQuest(CQuest):
        JOINED_FLAG = None
        STARTED_FLAG = None
        ITEM = None
        WHO = None
        WHERE = None

        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty(self.JOINED_FLAG)

        def getObjective(self):
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty(self.JOINED_FLAG):
                return f"{self.WHO} has joined your cause."
            if has_item(game_map.getPlayer(), self.ITEM):
                return f"Return to {self.WHO} in the {self.WHERE} with what you recovered."
            return f"Recover what {self.WHO} asks for in the {self.WHERE}."

        def getReward(self):
            return f"{self.WHO} joins your cause and gives you a war-gift."

        def getHint(self):
            return f"The cache lies near {self.WHO}'s post in the {self.WHERE}."

        def onComplete(self):
            pass

    @register(context)
    class HaldaQuest(CompanionQuest):
        JOINED_FLAG = "halda_joined"
        STARTED_FLAG = "halda_started"
        ITEM = "banditLedger"
        WHO = "Ser Halda"
        WHERE = "Reaved Fields"

    @register(context)
    class MorriganeQuest(CompanionQuest):
        JOINED_FLAG = "morrigane_joined"
        STARTED_FLAG = "morrigane_started"
        ITEM = "fenRelic"
        WHO = "Morrigane"
        WHERE = "Plague-Fen"

    @register(context)
    class CorvynQuest(CompanionQuest):
        JOINED_FLAG = "corvyn_joined"
        STARTED_FLAG = "corvyn_started"
        ITEM = "ashRelic"
        WHO = "Corvyn"
        WHERE = "Ashmarch"

    # ---- Dialogs ----
    @register(context)
    class MayorDialog(CDialog):
        def high_reputation(self):
            return reputation(self.getGame().getMap()) >= 3

        def low_reputation(self):
            return reputation(self.getGame().getMap()) <= -3

        def steady_reputation(self):
            return -3 < reputation(self.getGame().getMap()) < 3

    @register(context)
    class TavernDialog(CDialog):
        pass

    class CompanionDialog(CDialog):
        JOINED_FLAG = None
        STARTED_FLAG = None
        LEFT_FLAG = None
        QUEST = None
        ITEM = None
        BOON = None
        LEAVE_AT = -5
        # Direction of the reputation break: most companions leave when your standing
        # sinks to/below LEAVE_AT; a turncoat leaves when it rises to/above it instead.
        LEAVE_WHEN_ABOVE = False
        LEAVE_MESSAGE = (
            "Your reputation in the marches has sunk past what your companion can stomach. They take their "
            "leave - the war-gift stays, but their sword does not."
        )

        def not_met(self):
            game_map = self.getGame().getMap()
            return not game_map.getBoolProperty(self.STARTED_FLAG) and not game_map.getBoolProperty(self.JOINED_FLAG)

        def can_recruit(self):
            game_map = self.getGame().getMap()
            return (
                game_map.getBoolProperty(self.STARTED_FLAG)
                and not game_map.getBoolProperty(self.JOINED_FLAG)
                and has_item(game_map.getPlayer(), self.ITEM)
            )

        def is_joined(self):
            game_map = self.getGame().getMap()
            return game_map.getBoolProperty(self.JOINED_FLAG) and not game_map.getBoolProperty(self.LEFT_FLAG)

        def has_left(self):
            return self.getGame().getMap().getBoolProperty(self.LEFT_FLAG)

        def start(self):
            game_map = self.getGame().getMap()
            game_map.setBoolProperty(self.STARTED_FLAG, True)
            ensure_quest(game_map.getPlayer(), self.QUEST)

        def recruit(self):
            game_map = self.getGame().getMap()
            if not self.can_recruit():
                return
            game_map.setBoolProperty(self.JOINED_FLAG, True)
            adjust_reputation(game_map, 2)
            game_map.getPlayer().addItem(self.BOON)
            game_map.getPlayer().checkQuests()

        def banter(self):
            # Baldur's-Gate-style reputation reactivity: a companion may leave if your
            # standing drifts past what they can stomach. Most break when it sinks too low
            # (LEAVE_WHEN_ABOVE is False); a turncoat breaks when you grow too righteous.
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty(self.JOINED_FLAG) and not game_map.getBoolProperty(self.LEFT_FLAG):
                rep = reputation(game_map)
                left = rep >= self.LEAVE_AT if self.LEAVE_WHEN_ABOVE else rep <= self.LEAVE_AT
                if left:
                    game_map.setBoolProperty(self.LEFT_FLAG, True)
                    self.getGame().getGuiHandler().showMessage(self.LEAVE_MESSAGE)

    # Dialog action/condition callbacks are resolved on the exact registered class, so each
    # companion dialog re-declares the shared callbacks as thin delegates to the base logic.
    @register(context)
    class KnightDialog(CompanionDialog):
        JOINED_FLAG = "halda_joined"
        STARTED_FLAG = "halda_started"
        LEFT_FLAG = "halda_left"
        QUEST = "haldaQuest"
        ITEM = "banditLedger"
        BOON = "aegisOfHalda"

        def not_met(self):
            return CompanionDialog.not_met(self)

        def can_recruit(self):
            return CompanionDialog.can_recruit(self)

        def is_joined(self):
            return CompanionDialog.is_joined(self)

        def has_left(self):
            return CompanionDialog.has_left(self)

        def start(self):
            return CompanionDialog.start(self)

        def recruit(self):
            return CompanionDialog.recruit(self)

        def banter(self):
            return CompanionDialog.banter(self)

    @register(context)
    class WitchDialog(CompanionDialog):
        JOINED_FLAG = "morrigane_joined"
        STARTED_FLAG = "morrigane_started"
        LEFT_FLAG = "morrigane_left"
        QUEST = "morriganeQuest"
        ITEM = "fenRelic"
        BOON = "morriganesCharm"

        def not_met(self):
            return CompanionDialog.not_met(self)

        def can_recruit(self):
            return CompanionDialog.can_recruit(self)

        def is_joined(self):
            return CompanionDialog.is_joined(self)

        def has_left(self):
            return CompanionDialog.has_left(self)

        def start(self):
            return CompanionDialog.start(self)

        def recruit(self):
            return CompanionDialog.recruit(self)

        def banter(self):
            return CompanionDialog.banter(self)

    @register(context)
    class SellswordDialog(CompanionDialog):
        JOINED_FLAG = "corvyn_joined"
        STARTED_FLAG = "corvyn_started"
        LEFT_FLAG = "corvyn_left"
        QUEST = "corvynQuest"
        ITEM = "ashRelic"
        BOON = "corvynsBlade"
        # The turncoat leaves if you get too righteous for his taste: break upward, not downward.
        LEAVE_AT = 5
        LEAVE_WHEN_ABOVE = True
        LEAVE_MESSAGE = (
            "You have grown too clean and beloved for the turncoat's taste. Corvyn remembers he works for "
            "coin, not causes, and takes his leave - the war-gift stays, but his sword does not."
        )

        def not_met(self):
            return CompanionDialog.not_met(self)

        def can_recruit(self):
            return CompanionDialog.can_recruit(self)

        def is_joined(self):
            return CompanionDialog.is_joined(self)

        def has_left(self):
            return CompanionDialog.has_left(self)

        def start(self):
            return CompanionDialog.start(self)

        def recruit(self):
            return CompanionDialog.recruit(self)

        def banter(self):
            return CompanionDialog.banter(self)

    # ---- Triggers ----
    @trigger(context, "onEnter", "mayorHall")
    class MayorTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("mayorDialog"))

    @trigger(context, "onEnter", "gravewatchTavern")
    class TavernTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("tavernDialog"))

    @trigger(context, "onEnter", "companionKnight")
    class KnightTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("knightDialog"))

    @trigger(context, "onEnter", "companionWitch")
    class WitchTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("witchDialog"))

    @trigger(context, "onEnter", "companionSellsword")
    class SellswordTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("sellswordDialog"))

    @trigger(context, "onDestroy", "theNinefoldKingBoss")
    class NinefoldKingTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(
                "The Crowned God falls, and nine circlets of black iron crack apart on the Citadel stones. For the "
                "first time in nine hundred years the Nine Marches are only quiet - not waiting. You still wear a "
                "shard of its crown; the marches will remember that, too."
            )
