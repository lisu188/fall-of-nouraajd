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
                self.getMap().setBoolProperty('completedRolf', False)
                self.getMap().setBoolProperty('completedOctoBogz', False)
                self.getMap().getPlayer().addQuest("rolfQuest")
                self.getMap().getPlayer().addItem("letterFromRolf")

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            self.getMap().getGame().changeMap("map2")

    @register(context)
    class MainQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty('completedGooby')

        def onComplete(self):
            pass

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
            return self.getGame().getMap().getPlayer().hasItem(lambda it: it.getName() == 'holyRelic')

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
            return self.getGame().getMap().getBoolProperty('completedOctoBogz')

        def onComplete(self):
            pass

    @register(context)
    class AmuletQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getPlayer().hasItem(lambda it: it.getName() == 'preciousAmulet')

        def onComplete(self):
            pass

    @trigger(context, "onDestroy", "gooby1")
    class GoobyTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage("Gooby killed!!!")
            object.getGame().getMap().setBoolProperty('completedGooby', True)

    @trigger(context, "onDestroy", "cave1")
    class CaveTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
            gooby = object.getGame().createObject("gooby")
            gooby.setStringProperty("name", "gooby1")
            object.getGame().getMap().addObject(gooby)
            gooby.moveTo(100, 100, 0)
            object.getGame().getMap().setBoolProperty('completedGooby', False)
            object.getGame().getMap().getPlayer().addQuest("mainQuest")
            object.getGame().getMap().getPlayer().addItem("skullOfRolf")
            object.getGame().getMap().getPlayer().addItem('holyRelic')

    @trigger(context, "onDestroy", "cave2")
    class OctoBogzCaveTrigger(CTrigger):
        def trigger(self, object, event):
            player = object.getGame().getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == 'holyRelic'):
                object.getGame().getGuiHandler().showMessage(object.getStringProperty('message'))
            else:
                object.getGame().getGuiHandler().showMessage('The OctoBogz are defeated!')
            object.getGame().getMap().setBoolProperty('OCTOBOGZ_CLEARED', True)
            object.getGame().getMap().setBoolProperty('completedOctoBogz', True)

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
        def openDoor(self):
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
        def sellBeer(self):
            print("sellBeer")

        def askedAboutGirl(self):
            self.getGame().getMap().setBoolProperty('ASKED_ABOUT_GIRL', True)

    @register(context)
    class TavernDialog2(CDialog):
        def askedAboutGirl(self):
            return self.getGame().getMap().getBoolProperty('ASKED_ABOUT_GIRL')

        def talkedToVictor(self):
            self.getGame().getMap().setBoolProperty('TALKED_TO_VICTOR', True)

    @trigger(context, "onEnter", "nouraajdTownHall")
    class TownHallTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject('townHallDialog'))

    @register(context)
    class TownHallDialog(CDialog):
        def giveLetter(self):
            player = self.getGame().getMap().getPlayer()
            player.addItem('letterToBeren')
            player.addQuest('deliverLetterQuest')
            self.getGame().getGuiHandler().showMessage('You received a sealed letter.')

        def talkedToVictor(self):
            return self.getGame().getMap().getBoolProperty('TALKED_TO_VICTOR')

        def spawnCultists(self):
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
        def deliverLetter(self):
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == 'letterToBeren'):
                player.removeItem(lambda it: it.getName() == 'letterToBeren', True)
                self.getGame().getMap().setBoolProperty('DELIVERED_LETTER', True)
                player.addQuest('retrieveRelicQuest')

        def returnRelic(self):
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(lambda it: it.getName() == 'holyRelic'):
                player.removeItem(lambda it: it.getName() == 'holyRelic', True)
                self.getGame().getMap().setBoolProperty('RELIC_RETURNED', True)
                player.addQuest('cleanseCaveQuest')

        def finishCleanse(self):
            if self.getGame().getMap().getBoolProperty('OCTOBOGZ_CLEARED'):
                self.getGame().getMap().setBoolProperty('CAVE_PURGED', True)
                self.getGame().getGuiHandler().showMessage('The town is safe once more.')
            else:
                self.getGame().getGuiHandler().showMessage('The cave still crawls with OctoBogz.')

    @register(context)
    class OctoBogzDialog(CDialog):
        def acceptQuest(self):
            self.getGame().getMap().getPlayer().addQuest('octoBogzQuest')
            self.getGame().getMap().setBoolProperty('completedOctoBogz', False)

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
                hall.getGame().getGuiHandler().showDialog(hall.getGame().createObject('dialog'))

    @trigger(context, "onEnter", "oldWoman")
    class OldWomanTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                obj.getGame().getGuiHandler().showDialog(obj.getGame().createObject('questDialog'))

    @register(context)
    class QuestDialog(CDialog):
        def startAmuletQuest(self):
            self.getGame().getMap().getPlayer().addQuest('amuletQuest')
