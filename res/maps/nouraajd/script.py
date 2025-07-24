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
                self.getMap().getGame().getGuiHandler().showMessage(self.getStringProperty('text'))
                self.getMap().removeAll(lambda ob: ob.getStringProperty('type') == self.getStringProperty('type'))
                self.getMap().setBoolProperty('completed_rolf', False)
                self.getMap().setBoolProperty('completed_octobogz', False)
                self.getMap().setBoolProperty('AMULET_QUEST_STARTED', False)
                self.getMap().getPlayer().addQuest("rolfQuest")
                self.getMap().getPlayer().addItem("letterFromRolf")

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            self.getMap().getGame().changeMap("map2")

    @register(context)
    class MainQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty('completed_gooby')

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage(
                'Gooby has fallen. The townsfolk cheer your victory.'
            )

    @register(context)
    class RolfQuest(CQuest):

        def isCompleted(self):
            return self.getGame().getMap().getPlayer().hasItem(lambda it: it.getName() == 'skullOfRolf')

        def onComplete(self):
            pass

    @register(context)
    class DeliverLetterQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty('DELIVERED_LETTER')

        def onComplete(self):
            pass

    @register(context)
    class RetrieveRelicQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty('RELIC_RETURNED')

        def onComplete(self):
            pass

    @register(context)
    class CleanseCaveQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty('OCTOBOGZ_CLEARED')

        def onComplete(self):
            pass

    @register(context)
    class OctoBogzQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty('completed_octobogz')

        def onComplete(self):
            pass

    @register(context)
    class AmuletQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty('AMULET_RETURNED')

        def onComplete(self):
            pass

    @trigger(context, "onDestroy", "gooby1")
    class GoobyTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage("Gooby killed!!!")
            object.getGame().getMap().setBoolProperty('completed_gooby', True)

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
            game_map.setBoolProperty('completed_gooby', False)
            player.addQuest("mainQuest")
            player.addItem("skullOfRolf")
            game_map.setBoolProperty('completed_rolf', True)

    @trigger(context, "onDestroy", "catacombs")
    class CatacombsTrigger(CTrigger):
        def trigger(self, obj, event):
            game_map = obj.getGame().getMap()
            player = game_map.getPlayer()
            player.addItem('holyRelic')
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty('message'))

    @trigger(context, "onDestroy", "cave2")
    class OctoBogzCaveTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getGame().getMap()
            if game_map.getBoolProperty('RELIC_RETURNED'):
                object.getGame().getGuiHandler().showMessage(
                    object.getStringProperty('message')
                )
            else:
                object.getGame().getGuiHandler().showMessage('The OctoBogz are defeated!')
            game_map.setBoolProperty('OCTOBOGZ_CLEARED', True)
            game_map.setBoolProperty('completed_octobogz', True)

    @trigger(context, "onEnter", "market1")
    class MarketTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showTrade(object.getObjectProperty('market'))

    @trigger(context, "onEnter", "nouraajdDoor")
    class NouraajdDoorTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getBoolProperty('opened'):
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject('doorDialog'))

    @register(context)
    class DoorDialog(CDialog):
        def open_door(self):
            self.getGame().getMap().removeAll(lambda ob: ob.getName().startswith('nouraajdDoorTrigger'))
            self.getGame().getMap().getObjectByName('nouraajdDoor').setBoolProperty('opened', True)

    @trigger(context, "onEnter", "nouraajdTavern")
    class NouraajdTavernTrigger(CTrigger):
        def trigger(self, tavern, event):
            if tavern.getNumericProperty('visited') == 0 and tavern.getNumericProperty('time_visited') == 0:
                tavern.getGame().getGuiHandler().showDialog(tavern.getGame().createObject('tavernDialog1'))
                tavern.setNumericProperty('time_visited', tavern.getGame().getMap().getTurn())
                tavern.incProperty('visited', 1)
            elif tavern.getNumericProperty(
                    'visited') == 1 and tavern.getGame().getMap().getTurn() - tavern.getNumericProperty(
                'time_visited') > 50:
                tavern.getGame().getGuiHandler().showDialog(tavern.getGame().createObject('tavernDialog2'))
                tavern.incProperty('visited', 1)

    @register(context)
    class TavernDialog1(CDialog):
        def sell_beer(self):
            print("sell_beer")

        def asked_about_girl(self):
            self.getGame().getMap().setBoolProperty('ASKED_ABOUT_GIRL', True)

    @register(context)
    class TavernDialog2(CDialog):
        def asked_about_girl(self):
            return self.getGame().getMap().getBoolProperty('ASKED_ABOUT_GIRL')

        def talked_to_victor(self):
            self.getGame().getMap().setBoolProperty('TALKED_TO_VICTOR', True)

    @trigger(context, "onEnter", "nouraajdTownHall")
    class TownHallTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject('townHallDialog'))

    @register(context)
    class TownHallDialog(CDialog):
        def give_letter(self):
            player = self.getGame().getMap().getPlayer()
            if not player.hasItem(lambda it: it.getName() == 'letterToBeren'):
                player.addItem('letterToBeren')
                self.getGame().getGuiHandler().showMessage('You received a sealed letter.')
            quests = player.getQuests()
            if not any(q.getName() == 'deliverLetterQuest' for q in quests):
                player.addQuest('deliverLetterQuest')

        def has_letter_quest(self):
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == 'letterToBeren'):
                return True
            quests = player.getQuests()
            return any(q.getName() == 'deliverLetterQuest' for q in quests)

        def talked_to_victor(self):
            return self.getGame().getMap().getBoolProperty('TALKED_TO_VICTOR')

        def spawn_cultists(self):
            game = self.getGame()
            player = game.getMap().getPlayer()
            loc = player.getCoords()

            offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for i, j in offsets:
                coords = Coords(loc.x + i, loc.y + j, loc.z)
                if game.getMap().canStep(coords):
                    mon = game.createObject('Cultist')
                    game.getMap().addObject(mon)
                    mon.moveTo(coords.x, coords.y, coords.z)

            leader_pos = (1, 1)
            coords = Coords(loc.x + leader_pos[0], loc.y + leader_pos[1], loc.z)
            if game.getMap().canStep(coords):
                leader = game.createObject('CultLeader')
                leader.setStringProperty('name', 'cultLeaderQuest')
                game.getMap().addObject(leader)
                leader.moveTo(coords.x, coords.y, coords.z)

    @trigger(context, "onEnter", "nouraajdChapel")
    class ChapelTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject('berenDialog'))

    @register(context)
    class BerenDialog(CDialog):
        def deliver_letter(self):
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == 'letterToBeren'):
                player.removeItem(lambda it: it.getName() == 'letterToBeren', True)
                self.getGame().getMap().setBoolProperty('DELIVERED_LETTER', True)
                if player.hasItem(lambda it: it.getName() == 'holyRelic'):
                    self.return_relic()
                else:
                    player.addQuest('retrieveRelicQuest')

        def return_relic(self):
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == 'holyRelic'):
                player.removeItem(lambda it: it.getName() == 'holyRelic', True)
                self.getGame().getMap().setBoolProperty('RELIC_RETURNED', True)
                player.addQuest('cleanseCaveQuest')

        def finish_cleanse(self):
            if self.getGame().getMap().getBoolProperty('OCTOBOGZ_CLEARED'):
                self.getGame().getMap().setBoolProperty('CAVE_PURGED', True)
                self.getGame().getGuiHandler().showMessage('The town is safe once more.')
            else:
                self.getGame().getGuiHandler().showMessage('The cave still crawls with OctoBogz.')

    @register(context)
    class OctoBogzDialog(CDialog):
        def accept_quest(self):
            self.getGame().getMap().getPlayer().addQuest('octoBogzQuest')
            self.getGame().getMap().setBoolProperty('completed_octobogz', False)

    @trigger(context, "onEnter", "questGiver")
    class QuestGiverTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game.getGuiHandler().showDialog(game.createObject('dialog'))

    @trigger(context, "onDestroy", "cultLeaderQuest")
    class CultLeaderQuestTrigger(CTrigger):
        def trigger(self, leader, event):
            game = leader.getGame()
            player = game.getMap().getPlayer()
            player.addGold(500)
            player.healProc(100)
            game.getGuiHandler().showDialog(game.createObject('victorRewardDialog'))
            game.getGuiHandler().showTrade(game.createObject('victorMarket'))
            game.getMap().setBoolProperty('VICTOR_HELP', True)
            if event.getCause().isPlayer():
                # Display a completion dialog to the player
                game.getGuiHandler().showDialog(game.createObject('dialog'))

    @trigger(context, "onEnter", "oldWoman")
    class OldWomanTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game_map = game.getMap()
                if game_map.getBoolProperty('AMULET_RETURNED'):
                    return
                player = game_map.getPlayer()
                if player.hasItem(lambda it: it.getName() == 'preciousAmulet'):
                    game.getGuiHandler().showDialog(game.createObject('questReturnDialog'))
                elif not game_map.getBoolProperty('AMULET_QUEST_STARTED'):
                    game.getGuiHandler().showDialog(game.createObject('questDialog'))
                else:
                    game.getGuiHandler().showMessage('The goblin still has my amulet!')

    @register(context)
    class QuestDialog(CDialog):
        def start_amulet_quest(self):
            game = self.getGame()
            game_map = game.getMap()
            if game_map.getBoolProperty('AMULET_QUEST_STARTED'):
                return
            player = game_map.getPlayer()
            player.addQuest('amuletQuest')
            goblin = game.createObject('goblinThief')
            goblin.setStringProperty('name', 'amuletGoblin')
            game_map.addObject(goblin)
            # spawn near the old woman within map bounds
            goblin.moveTo(195, 8, 0)
            game_map.setBoolProperty('AMULET_QUEST_STARTED', True)

    @register(context)
    class QuestReturnDialog(CDialog):
        def complete_amulet_quest(self):
            game = self.getGame()
            player = game.getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == 'preciousAmulet'):
                player.removeItem(lambda it: it.getName() == 'preciousAmulet', True)
                player.addGold(50)
                game.getMap().setBoolProperty('AMULET_RETURNED', True)
                game.getGuiHandler().showMessage('The old woman gratefully rewards you with 50 gold.')
