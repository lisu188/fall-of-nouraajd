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

    @register(context)
    class TownHallDialog(CDialog):
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

    @trigger(context, "onEnter", "nouraajdTownHall")
    class NouraajdTownHallTrigger(CTrigger):
        def trigger(self, hall, event):
            if event.getCause().isPlayer() and hall.getGame().getMap().getBoolProperty('TALKED_TO_VICTOR'):
                hall.getGame().getGuiHandler().showDialog(hall.getGame().createObject('townHallDialog'))

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
