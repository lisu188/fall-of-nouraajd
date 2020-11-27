def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import CDialog
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
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showDialog(object.getGame().createObject('tavernDialog1'))

    @register(context)
    class TavernDialog1(CDialog):
        def sellBeer(self):
            print("sellBeer")

        def askedAboutGirl(self):
            print("askedAboutGirl")
