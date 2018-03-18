def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import register, trigger

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if event.getCause().isPlayer():
                self.getMap().getGame().getGuiHandler().showMessage(self.getStringProperty('text'))
                self.getMap().removeAll(lambda ob: ob.getStringProperty('type') == self.getStringProperty('type'))
                self.getMap().setBoolProperty('completedRolf', False)
                self.getMap().getPlayer().addQuest("rolfQuest")

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
            return self.getGame().getMap().getBoolProperty('completedRolf')

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
            object.getGame().getGuiHandler().showMessage(  # TODO: externalize
                "You feel the ground shaking, and see the ratmen all around you!!! But the one part is missin g in this puzzle. Letter said about the ratmen who was much bigger than the other. These here are just ordinary pritschers.")
            gooby = object.getGame().createObject("Gooby")
            gooby.setStringProperty("name", "gooby1")
            object.getGame().getMap().addObject(gooby)
            gooby.moveTo(100, 100, 0)
            object.getGame().getMap().setBoolProperty('completedGooby', False)
            object.getGame().getMap().getPlayer().addQuest("mainQuest")
            # TODO: shorten this with player.hasItem
            object.getGame().getMap().getPlayer().addItem(object.getGame().createObject("skullOfRolf"))
            object.getGame().getMap().setBoolProperty('completedRolf', True)

    @trigger(context, "onEnter", "market1")
    class MarketTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showTrade(object.getObjectProperty('market'))
