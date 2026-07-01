def load(self, context):
    from game import CDialog
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import Coords
    from game import register
    from game import trigger

    GATE_SPAWN_OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    BOSS_SPAWN = (100, 33, 0)

    def ensure_quest(player, quest_name):
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def quest_flags_default(game_map):
        for flag in ("ascent_heard", "gate_opened", "throne_taken", "boss_woken"):
            if not hasattr(game_map, flag):
                game_map.setBoolProperty(flag, False)

    def spawn_walkable(game_map, base, offsets, unit):
        for dx, dy in offsets:
            coords = Coords(base.x + dx, base.y + dy, base.z)
            if game_map.canStep(coords):
                game_map.addObjectByName(unit, coords)

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
            ensure_quest(player, "kadathAscentQuest")

    @register(context)
    class DreamGate(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            if game_map.getBoolProperty("gate_opened"):
                game.getGuiHandler().showMessage(
                    "The standing stones are quiet now; the gate you opened does not open twice."
                )
                return
            game.getGuiHandler().showMessage(
                "You pass through the ring of stones and the dream deepens. Out of the drifting snow the "
                "Night-Gaunts descend on silent wings to test the dreamer who dares the climb."
            )
            spawn_walkable(game_map, self.getCoords(), GATE_SPAWN_OFFSETS, "nightGaunt")
            game_map.setBoolProperty("gate_opened", True)

    @register(context)
    class OnyxThrone(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            player = game_map.getPlayer()
            if game_map.getBoolProperty("throne_taken"):
                return
            player.addItem("onyxSignetOfNyarlathotep")
            game_map.setBoolProperty("throne_taken", True)
            game.getGuiHandler().showMessage(
                "The onyx throne is not empty. A tall, dark figure with a pleasant, ancient face rises smiling "
                "and sets the Onyx Signet upon your brow - a gift, he says, from the Crawling Chaos. Then the "
                "smile comes apart, and Nyarlathotep is only the last shape before the blind piping of the void."
            )
            if not game_map.getBoolProperty("boss_woken"):
                boss = game.createObject("theCrawlingChaos")
                boss.setStringProperty("name", "theCrawlingChaosBoss")
                controller = game.createObject("CTargetController")
                controller.setTarget("player")
                boss.setController(controller)
                game_map.addObject(boss)
                boss.moveTo(*BOSS_SPAWN)
                game_map.setBoolProperty("boss_woken", True)

    @register(context)
    class KadathAscentQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("throne_taken")

        def getObjective(self):
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty("throne_taken"):
                return "You wear the Onyx Signet of the Crawling Chaos. The dream will not release you unmarked."
            if game_map.getBoolProperty("ascent_heard"):
                return "Climb the basalt road to the onyx castle on the summit of Kadath."
            if game_map.getBoolProperty("gate_opened"):
                return "The dream has deepened past the standing stones; press on toward the summit."
            return "Find a dreamer in the southern camp who has survived the Cold Waste before."

        def getReward(self):
            return "The Onyx Signet of the Crawling Chaos - outer-void clarity bought against the wearer's own will."

        def getHint(self):
            return "The frozen dreamer's guide in the camp knows the road. The warmth on the basalt is bait."

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage(
                "You reached the throne of Kadath, and the throne was waiting for you. The Great Ones were never "
                "the danger. Their messenger was."
            )

    @register(context)
    class DreamerDialog(CDialog):
        def has_heard_ascent(self):
            return self.getGame().getMap().getBoolProperty("ascent_heard")

        def hear_the_ascent(self):
            game_map = self.getGame().getMap()
            game_map.setBoolProperty("ascent_heard", True)
            ensure_quest(game_map.getPlayer(), "kadathAscentQuest")

    @register(context)
    class LengPriestDialog(CDialog):
        pass

    @trigger(context, "onEnter", "dreamerGuide")
    class DreamerTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("dreamerDialog"))

    @trigger(context, "onEnter", "lengPriest")
    class LengPriestTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("lengPriestDialog"))

    @trigger(context, "onDestroy", "roostNightGaunt")
    class RoostNightGauntTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "warrenLeng")
    class WarrenLengTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "vaultElder")
    class VaultElderTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "theCrawlingChaosBoss")
    class CrawlingChaosTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(
                "The last shape sloughs away and the Crawling Chaos withdraws into the dark between dreams. You "
                "are still wearing his signet. Somewhere, in the ultimate void, an idiot flute keeps your time."
            )
