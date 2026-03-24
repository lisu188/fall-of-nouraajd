def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import CDialog
    from game import Coords
    from game import register, trigger

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if event.getCause().isPlayer():
                game_map = self.getMap()
                game = game_map.getGame()
                player = game_map.getPlayer()
                game.getGuiHandler().showMessage(self.getStringProperty("text"))
                game_map.removeAll(lambda ob: ob.getStringProperty("type") == self.getStringProperty("type"))
                game_map.setBoolProperty("completed_gooby", False)
                game_map.setBoolProperty("completed_rolf", False)
                game_map.setBoolProperty("completed_octobogz", False)
                game_map.setBoolProperty("DELIVERED_LETTER", False)
                game_map.setBoolProperty("RELIC_RETURNED", False)
                game_map.setBoolProperty("OCTOBOGZ_SLAIN", False)
                game_map.setBoolProperty("OCTOBOGZ_CLEARED", False)
                game_map.setBoolProperty("CAVE_PURGED", False)
                game_map.setBoolProperty("AMULET_QUEST_STARTED", False)
                game_map.setBoolProperty("AMULET_RETURNED", False)
                game_map.setBoolProperty("ASKED_ABOUT_GIRL", False)
                game_map.setBoolProperty("TALKED_TO_VICTOR", False)
                game_map.setBoolProperty("VICTOR_QUEST_STARTED", False)
                game_map.setBoolProperty("VICTOR_COURTYARD_FOUND", False)
                game_map.setBoolProperty("VICTOR_CULTISTS_SPAWNED", False)
                game_map.setBoolProperty("VICTOR_GOOD_END", False)
                game_map.setBoolProperty("VICTOR_BAD_END", False)
                game_map.setBoolProperty("VICTOR_REWARD_CLAIMED", False)
                game_map.setBoolProperty("VICTOR_HELP", False)
                game_map.setNumericProperty("VICTOR_COURTYARD_TURN", 0)
                player.setNumericProperty("inquisitor_clues", 0)
                player.setNumericProperty("wayfarer_routes", 0)
                player.setBoolProperty("inspected_stained_glass", False)
                player.setBoolProperty("charted_smuggler_route", False)
                player.addQuest("rolfQuest")
                player.addItem("letterFromRolf")

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            self.getMap().getGame().changeMap("map2")

    @register(context)
    class MainQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("completed_gooby")

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage("Gooby has fallen. The townsfolk cheer your victory.")

    @register(context)
    class RolfQuest(CQuest):

        def isCompleted(self):
            return self.getGame().getMap().getPlayer().hasItem(lambda it: it.getName() == "skullOfRolf")

        def onComplete(self):
            pass

    @register(context)
    class DeliverLetterQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("DELIVERED_LETTER")

        def onComplete(self):
            pass

    @register(context)
    class RetrieveRelicQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("RELIC_RETURNED")

        def onComplete(self):
            pass

    @register(context)
    class CleanseCaveQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("OCTOBOGZ_CLEARED")

        def onComplete(self):
            pass

    @register(context)
    class VictorQuest(CQuest):
        def isCompleted(self):
            game_map = self.getGame().getMap()
            return game_map.getBoolProperty("VICTOR_GOOD_END") or game_map.getBoolProperty("VICTOR_BAD_END")

        def onComplete(self):
            pass

    @register(context)
    class OctoBogzQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("completed_octobogz")

        def onComplete(self):
            game = self.getGame()
            player = game.getMap().getPlayer()
            player.addGold(1000)
            player.addItem("ShadowBlade")
            game.getGuiHandler().showMessage("The travelers reward you with 1000 gold and the Shadow Blade.")

    @register(context)
    class AmuletQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("AMULET_RETURNED")

        def onComplete(self):
            pass

    @trigger(context, "onDestroy", "gooby1")
    class GoobyTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage("Gooby killed!!!")
            object.getGame().getMap().setBoolProperty("completed_gooby", True)

    @trigger(context, "onDestroy", "cave1")
    class CaveTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
            game_map = object.getGame().getMap()
            player = game_map.getPlayer()
            gooby = object.getGame().createObject("gooby")
            gooby.setStringProperty("name", "gooby1")
            game_map.addObject(gooby)
            gooby.moveTo(100, 100, 0)
            game_map.setBoolProperty("completed_gooby", False)
            player.addQuest("mainQuest")
            player.addItem("skullOfRolf")
            game_map.setBoolProperty("completed_rolf", True)

    @trigger(context, "onDestroy", "catacombs")
    class CatacombsTrigger(CTrigger):
        def trigger(self, obj, event):
            game_map = obj.getGame().getMap()
            player = game_map.getPlayer()
            player.addItem("holyRelic")
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "cave2")
    class OctoBogzCaveTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getGame().getMap()
            game_map.setBoolProperty("OCTOBOGZ_SLAIN", True)
            if game_map.getBoolProperty("RELIC_RETURNED"):
                object.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
                game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)
            else:
                object.getGame().getGuiHandler().showMessage("The OctoBogz are defeated!")
            game_map.setBoolProperty("completed_octobogz", True)

    @trigger(context, "onEnter", "market1")
    class MarketTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showTrade(object.getObjectProperty("market"))

    @trigger(context, "onEnter", "nouraajdDoor")
    class NouraajdDoorTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getBoolProperty("opened"):
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("doorDialog"))

    @register(context)
    class DoorDialog(CDialog):
        def open_door(self):
            self.getGame().getMap().removeAll(lambda ob: ob.getName().startswith("nouraajdDoorTrigger"))
            self.getGame().getMap().getObjectByName("nouraajdDoor").setBoolProperty("opened", True)

    @trigger(context, "onEnter", "nouraajdTavern")
    class NouraajdTavernTrigger(CTrigger):
        def trigger(self, tavern, event):
            if tavern.getNumericProperty("visited") == 0 and tavern.getNumericProperty("time_visited") == 0:
                tavern.getGame().getGuiHandler().showDialog(tavern.getGame().createObject("tavernDialog1"))
                tavern.setNumericProperty("time_visited", tavern.getGame().getMap().getTurn())
                tavern.incProperty("visited", 1)
            elif (
                tavern.getNumericProperty("visited") == 1
                and tavern.getGame().getMap().getTurn() - tavern.getNumericProperty("time_visited") > 50
            ):
                tavern.getGame().getGuiHandler().showDialog(tavern.getGame().createObject("tavernDialog2"))
                tavern.incProperty("visited", 1)

    @register(context)
    class TavernDialog1(CDialog):
        def sell_beer(self):
            print("sell_beer")

        def asked_about_girl(self):
            self.getGame().getMap().setBoolProperty("ASKED_ABOUT_GIRL", True)

    @register(context)
    class TavernDialog2(CDialog):
        def _ensure_victor_quest(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            if not game_map.getBoolProperty("VICTOR_QUEST_STARTED"):
                game_map.setBoolProperty("VICTOR_QUEST_STARTED", True)
            for quest in player.getQuests():
                if quest.getName() == "victorQuest":
                    return
            player.addQuest("victorQuest")

        def asked_about_girl(self):
            return self.getGame().getMap().getBoolProperty("ASKED_ABOUT_GIRL")

        def talked_to_victor(self):
            self._ensure_victor_quest()
            self.getGame().getMap().setBoolProperty("TALKED_TO_VICTOR", True)

    @trigger(context, "onEnter", "nouraajdTownHall")
    class TownHallTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("townHallDialog"))

    @register(context)
    class TownHallDialog(CDialog):
        COURTYARD_SPAWNS = [(44, 100, 0), (46, 100, 0), (45, 99, 0), (45, 101, 0)]
        COURTYARD_LEADER_SPAWN = (45, 100, 0)
        COURTYARD_TIMEOUT_TURNS = 75

        def _ensure_quest(self, quest_name):
            player = self.getGame().getMap().getPlayer()
            for quest in player.getQuests():
                if quest.getName() == quest_name:
                    return
            player.addQuest(quest_name)

        def can_chart_wayfarer_route(self):
            player = self.getGame().getMap().getPlayer()
            return player.getType() == "Wayfarer" and not player.getBoolProperty("charted_smuggler_route")

        def chart_wayfarer_route(self):
            player = self.getGame().getMap().getPlayer()
            if not self.can_chart_wayfarer_route():
                return
            player.incProperty("wayfarer_routes", 1)
            player.setBoolProperty("charted_smuggler_route", True)
            player.addExp(750)
            self.getGame().getGuiHandler().showMessage(
                "You trace old courier alleys through Nouraajd. Your footing sharpens whenever a route turns unclear."
            )

        def give_letter(self):
            game_map = self.getGame().getMap()
            player = self.getGame().getMap().getPlayer()
            if game_map.getBoolProperty("DELIVERED_LETTER"):
                return
            if not player.hasItem(lambda it: it.getName() == "letterToBeren"):
                player.addItem("letterToBeren")
                self.getGame().getGuiHandler().showMessage("You received a sealed letter.")
            self._ensure_quest("deliverLetterQuest")

        def has_letter_quest(self):
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty("DELIVERED_LETTER"):
                return False
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == "letterToBeren"):
                return True
            quests = player.getQuests()
            for q in quests:
                if q.getName() == "deliverLetterQuest":
                    return True
            return False

        def talked_to_victor(self):
            return self.getGame().getMap().getBoolProperty("TALKED_TO_VICTOR")

        def start_victor_quest(self):
            game_map = self.getGame().getMap()
            game_map.setBoolProperty("VICTOR_QUEST_STARTED", True)
            self._ensure_quest("victorQuest")

        def _expire_victor_search(self, game_map):
            if not game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"):
                return False
            if game_map.getBoolProperty("VICTOR_GOOD_END") or game_map.getBoolProperty("VICTOR_BAD_END"):
                return False
            spawn_turn = game_map.getNumericProperty("VICTOR_COURTYARD_TURN")
            if spawn_turn and game_map.getTurn() - spawn_turn >= self.COURTYARD_TIMEOUT_TURNS:
                game_map.setBoolProperty("VICTOR_BAD_END", True)
                game_map.setBoolProperty("VICTOR_HELP", False)
                self.getGame().getGuiHandler().showMessage(
                    "You return to an empty courtyard. Victor's daughter has vanished with the cult."
                )
                game_map.removeAll(lambda ob: ob.getName() == "cultLeaderQuest")
                return True
            return False

        def spawn_cultists(self):
            game = self.getGame()
            game_map = game.getMap()
            self.start_victor_quest()
            game_map.setBoolProperty("VICTOR_COURTYARD_FOUND", True)
            if game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"):
                self._expire_victor_search(game_map)
                return
            game_map.setNumericProperty("VICTOR_COURTYARD_TURN", game_map.getTurn())

            for x, y, z in self.COURTYARD_SPAWNS:
                coords = Coords(x, y, z)
                if game_map.canStep(coords):
                    mon = game.createObject("Cultist")
                    target_ctrl = game.createObject("CTargetController")
                    target_ctrl.setTarget("player")
                    mon.setController(target_ctrl)
                    game_map.addObject(mon)
                    mon.moveTo(coords.x, coords.y, coords.z)

            coords = Coords(*self.COURTYARD_LEADER_SPAWN)
            if game_map.canStep(coords):
                leader = game.createObject("CultLeader")
                leader.setStringProperty("name", "cultLeaderQuest")
                target_ctrl = game.createObject("CTargetController")
                target_ctrl.setTarget("player")
                leader.setController(target_ctrl)
                game_map.addObject(leader)
                leader.moveTo(coords.x, coords.y, coords.z)
                game_map.setBoolProperty("VICTOR_CULTISTS_SPAWNED", True)

    @trigger(context, "onEnter", "nouraajdChapel")
    class ChapelTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("berenDialog"))

    @register(context)
    class BerenDialog(CDialog):
        def _ensure_quest(self, quest_name):
            player = self.getGame().getMap().getPlayer()
            for quest in player.getQuests():
                if quest.getName() == quest_name:
                    return
            player.addQuest(quest_name)

        def can_inspect_stained_glass(self):
            player = self.getGame().getMap().getPlayer()
            return player.getType() == "Inquisitor" and not player.getBoolProperty("inspected_stained_glass")

        def inspect_stained_glass(self):
            player = self.getGame().getMap().getPlayer()
            if not self.can_inspect_stained_glass():
                return
            player.incProperty("inquisitor_clues", 1)
            player.setBoolProperty("inspected_stained_glass", True)
            player.addExp(750)
            self.getGame().getGuiHandler().showMessage(
                "The stained glass hides a Marumi Baso seal. Your zeal hardens as you memorize the cult's cipher."
            )

        def can_deliver_letter(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            return player.hasItem(lambda it: it.getName() == "letterToBeren") and not game_map.getBoolProperty(
                "DELIVERED_LETTER"
            )

        def can_return_relic(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            return (
                game_map.getBoolProperty("DELIVERED_LETTER")
                and player.hasItem(lambda it: it.getName() == "holyRelic")
                and not game_map.getBoolProperty("RELIC_RETURNED")
            )

        def can_finish_cleanse(self):
            game_map = self.getGame().getMap()
            return (
                game_map.getBoolProperty("RELIC_RETURNED")
                and game_map.getBoolProperty("OCTOBOGZ_CLEARED")
                and not game_map.getBoolProperty("CAVE_PURGED")
            )

        def deliver_letter(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            if self.can_deliver_letter():
                player.removeItem(lambda it: it.getName() == "letterToBeren", True)
                game_map.setBoolProperty("DELIVERED_LETTER", True)
                if not game_map.getBoolProperty("RELIC_RETURNED"):
                    self._ensure_quest("retrieveRelicQuest")

        def return_relic(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            if self.can_return_relic():
                player.removeItem(lambda it: it.getName() == "holyRelic", True)
                game_map.setBoolProperty("RELIC_RETURNED", True)
                if game_map.getBoolProperty("OCTOBOGZ_SLAIN"):
                    game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)
                if not game_map.getBoolProperty("CAVE_PURGED"):
                    self._ensure_quest("cleanseCaveQuest")

        def finish_cleanse(self):
            game_map = self.getGame().getMap()
            if self.can_finish_cleanse():
                game_map.setBoolProperty("CAVE_PURGED", True)
                self.getGame().getGuiHandler().showMessage("The town is safe once more.")
            else:
                self.getGame().getGuiHandler().showMessage("The cave still crawls with OctoBogz.")

    @register(context)
    class OctoBogzDialog(CDialog):
        def accept_quest(self):
            game_map = self.getGame().getMap()
            game_map.getPlayer().addQuest("octoBogzQuest")
            if not game_map.getBoolProperty("OCTOBOGZ_SLAIN"):
                game_map.setBoolProperty("completed_octobogz", False)

    @trigger(context, "onEnter", "questGiver")
    class QuestGiverTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game.getGuiHandler().showDialog(game.createObject("dialog"))

    @trigger(context, "onDestroy", "cultLeaderQuest")
    class CultLeaderQuestTrigger(CTrigger):
        def trigger(self, leader, event):
            game = leader.getGame()
            game_map = game.getMap()
            if not game_map.getBoolProperty("VICTOR_QUEST_STARTED"):
                return
            if not game_map.getBoolProperty("VICTOR_COURTYARD_FOUND"):
                return
            if game_map.getBoolProperty("VICTOR_BAD_END") or game_map.getBoolProperty("VICTOR_GOOD_END"):
                return
            if game_map.getBoolProperty("VICTOR_REWARD_CLAIMED"):
                return
            player = game.getMap().getPlayer()
            player.addGold(500)
            player.healProc(100)
            game.getGuiHandler().showDialog(game.createObject("victorRewardDialog"))
            game.getGuiHandler().showTrade(game.createObject("victorMarket"))
            game_map.setBoolProperty("VICTOR_HELP", True)
            game_map.setBoolProperty("VICTOR_GOOD_END", True)
            game_map.setBoolProperty("VICTOR_BAD_END", False)
            game_map.setBoolProperty("VICTOR_REWARD_CLAIMED", True)

    @trigger(context, "onEnter", "oldWoman")
    class OldWomanTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game_map = game.getMap()
                if game_map.getBoolProperty("AMULET_RETURNED"):
                    game_map.removeObject(obj)
                    return
                player = game_map.getPlayer()
                if player.hasItem(lambda it: it.getName() == "preciousAmulet"):
                    game.getGuiHandler().showDialog(game.createObject("questReturnDialog"))
                elif not game_map.getBoolProperty("AMULET_QUEST_STARTED"):
                    game.getGuiHandler().showDialog(game.createObject("questDialog"))
                else:
                    game.getGuiHandler().showMessage("The goblin still has my amulet!")

    @register(context)
    class QuestDialog(CDialog):
        def start_amulet_quest(self):
            game = self.getGame()
            game_map = game.getMap()
            if game_map.getBoolProperty("AMULET_QUEST_STARTED"):
                return
            player = game_map.getPlayer()
            player.addQuest("amuletQuest")
            goblin = game.createObject("goblinThief")
            goblin.setStringProperty("name", "amuletGoblin")
            game_map.addObject(goblin)
            # spawn near the old woman within map bounds
            goblin.moveTo(195, 8, 0)
            game_map.setBoolProperty("AMULET_QUEST_STARTED", True)

    @register(context)
    class QuestReturnDialog(CDialog):
        def complete_amulet_quest(self):
            game = self.getGame()
            game_map = game.getMap()
            player = game_map.getPlayer()
            if player.hasItem(lambda it: it.getName() == "preciousAmulet"):
                player.removeItem(lambda it: it.getName() == "preciousAmulet", True)
                player.addGold(50)
                game_map.setBoolProperty("AMULET_RETURNED", True)
                game_map.setBoolProperty("AMULET_QUEST_STARTED", False)
                amulet_goblin = game_map.getObjectByName("amuletGoblin")
                if amulet_goblin:
                    game_map.removeObject(amulet_goblin)
                old_woman = game_map.getObjectByName("oldWoman")
                if old_woman:
                    game_map.removeObject(old_woman)
                game.getGuiHandler().showMessage("The old woman gratefully rewards you with 50 gold.")
