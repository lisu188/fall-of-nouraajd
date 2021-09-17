def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import register, trigger

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            self.getMap().getGame().changeMap("test")

    @trigger(context, "onEnter", "market1")
    class MarketTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showTrade(object.getObjectProperty('market'))

    # TODO: replace with onLoad event
    @trigger(context, "onTurn", "triggerAnchor")
    class TurnTrigger(CTrigger):
        def trigger(self, object, event):
            if object.getMap().getTurn() == 0:
                object.getMap().getGame().getRngHandler().addRandomEncounter(object.getMap(), 0, 1, 0, 5)
