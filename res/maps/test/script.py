def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import register, trigger

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            pass  # self.getMap().getGame().changeMap("test")

    @register(context)
    class InitializationProbe(CEvent):
        def onCreate(self, event):
            coords = self.getCoords()
            self.setStringProperty("observedMarker", self.getStringProperty("marker"))
            self.setNumericProperty("observedX", coords.x)
            self.setNumericProperty("observedY", coords.y)
            self.setNumericProperty("observedZ", coords.z)

    # TODO: replace with onLoad event
    @trigger(context, "onTurn", "triggerAnchor")
    class TurnTrigger(CTrigger):
        def trigger(self, object, event):
            if object.getMap().getTurn() == 0:
                object.getMap().getGame().getRngHandler().addRandomEncounter(object.getMap(), 0, 1, 0, 5)
