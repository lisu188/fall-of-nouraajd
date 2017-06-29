def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import register, trigger

    context.setBoolProperty('completed', False)

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if event.getCause().isPlayer():
                self.getMap().getGame().getGuiHandler().showMessage(self.getStringProperty('text'))
                self.getMap().removeAll(lambda ob: ob.getStringProperty('type') == self.getStringProperty('type'))

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            self.getMap().getGame().changeMap("map2")

    @register(context)
    class MainQuest(CQuest):
        def isCompleted(self):
            return context.getBoolProperty('completed')

        def onComplete(self):
            pass

    @trigger(context, "onDestroy", "gooby1")
    class GoobyTrigger(CTrigger):
        def trigger(self, object, event):
            object.getMap().getGame().getGuiHandler().showMessage("Gooby killed!!!")
            context.setBoolProperty('completed', True)

    @trigger(context, "onDestroy", "cave1")
    class CaveTrigger(CTrigger):
        def trigger(self, object, event):
            object.getMap().getGame().getGuiHandler().showMessage(
                "You feel the ground shaking, and see the ratmen all around you!!! But the one part is missing in this puzzle. Letter said about the ratmen who was much bigger than the other. These here are just ordinary pritschers.")
            gooby = object.getMap().createObject("Gooby")
            gooby.setStringProperty("objectName", "gooby1")
            object.getMap().addObject(gooby)
            gooby.moveTo(100, 100, 0)
            object.getMap().getPlayer().addQuest("mainQuest")

    @trigger(context, "onEnter", "market1")
    class MarketTrigger(CTrigger):
        def trigger(self, object, event):
            object.getMap().getGame().getGuiHandler().showTrade(object.getObjectProperty('market'))
