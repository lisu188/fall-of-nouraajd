def load(self, context):
    from game import CDialog
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import Coords
    from game import register
    from game import trigger

    BELL_SPAWN_OFFSETS = [(-1, 0), (1, 0), (0, -1)]
    BOSS_SPAWN = (28, 7, 0)

    def ensure_quest(player, quest_name):
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def quest_system_flags_default(game_map):
        for flag in ("tithe_heard", "bell_tolled", "tithe_taken", "boss_woken"):
            if not hasattr(game_map, flag):
                game_map.setBoolProperty(flag, False)

    def spawn_walkable(game_map, base, offsets, unit):
        placed = 0
        for dx, dy in offsets:
            coords = Coords(base.x + dx, base.y + dy, base.z)
            if game_map.canStep(coords):
                game_map.addObjectByName(unit, coords)
                placed += 1
        return placed

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            player = game_map.getPlayer()
            quest_system_flags_default(game_map)
            game.getGuiHandler().showMessage(self.getStringProperty("text"))
            game_map.removeAll(lambda ob: ob.getName() == self.getName())
            ensure_quest(player, "drownedTitheQuest")

    @register(context)
    class TideBell(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            if game_map.getBoolProperty("bell_tolled"):
                game.getGuiHandler().showMessage(
                    "The bell's iron note still hangs over the tarn. It has been answered once; the deep does "
                    "not need asking twice."
                )
                return
            game.getGuiHandler().showMessage(
                "You toll the drowned bell. The note goes out flat across the tarn, and the tarn answers: "
                "the water bulges, and Deep-Spawn rise dripping onto the causeway."
            )
            spawn_walkable(game_map, self.getCoords(), BELL_SPAWN_OFFSETS, "deepSpawn")
            game_map.setBoolProperty("bell_tolled", True)

    @register(context)
    class AltarThreshold(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            game = game_map.getGame()
            player = game_map.getPlayer()
            if game_map.getBoolProperty("tithe_taken"):
                return
            player.addItem("tiaraOfTheDrownedTithe")
            game_map.setBoolProperty("tithe_taken", True)
            game.getGuiHandler().showMessage(
                "The offered gold is a tiara of the Order, and it is already warm. You lift the Tiara of the "
                "Drowned Tithe from the altar - and far below, in Y'ha-nthlei, something that has dreamed of this "
                "for a thousand tides opens an eye. Tekeli-li! Tekeli-li!"
            )
            if not game_map.getBoolProperty("boss_woken"):
                boss = game.createObject("theNameless")
                boss.setStringProperty("name", "theNamelessBoss")
                controller = game.createObject("CTargetController")
                controller.setTarget("player")
                boss.setController(controller)
                game_map.addObject(boss)
                boss.moveTo(*BOSS_SPAWN)
                game_map.setBoolProperty("boss_woken", True)

    @register(context)
    class DrownedTitheQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("tithe_taken")

        def getObjective(self):
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty("tithe_taken"):
                return "You carry the Tiara of the Drowned Tithe. The deep knows your name now."
            if game_map.getBoolProperty("tithe_heard"):
                return "Cross the pilgrim causeway to the cyclopean altar at the tarn's heart."
            return "Find someone in Vhul'Marn who still remembers what the town owed the deep."

        def getReward(self):
            return "The Tiara of the Drowned Tithe - gilded knowing bought with the wearer's flesh."

        def getHint(self):
            return "The old tollman by the gate will talk. The causeway bell is best left silent."

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage(
                "The tithe is uncovered, and it was never a debt that could be paid off - only carried."
            )

    @register(context)
    class TollmanDialog(CDialog):
        def has_heard_tithe(self):
            return self.getGame().getMap().getBoolProperty("tithe_heard")

        def hear_the_tithe(self):
            game_map = self.getGame().getMap()
            game_map.setBoolProperty("tithe_heard", True)
            ensure_quest(game_map.getPlayer(), "drownedTitheQuest")

    @register(context)
    class WidowDialog(CDialog):
        pass

    @trigger(context, "onEnter", "oldTollman")
    class TollmanTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("tollmanDialog"))

    @trigger(context, "onEnter", "markedWidow")
    class WidowTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject("widowDialog"))

    @trigger(context, "onDestroy", "caveTarnMouth")
    class TarnMouthTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "caveSunkenWharf")
    class SunkenWharfTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "caveHybridWarren")
    class HybridWarrenTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "theNamelessBoss")
    class NamelessTrigger(CTrigger):
        def trigger(self, obj, event):
            obj.getGame().getGuiHandler().showMessage(
                "The Nameless folds back into the tarn, and for one held breath the drowned bell will not ring. "
                "It is not death. The deep is patient, and the stars will come right again."
            )
