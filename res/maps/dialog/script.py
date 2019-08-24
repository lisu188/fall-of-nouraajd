def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import register, trigger
    from game import Coords

    @register(context)
    class DialogEvent(CEvent):
        def onEnter(self, event):
            self.getGame().getGuiHandler().showDialog("dupa")

    context.getMap().addObjectByName("DialogEvent", Coords(0, 0, 0))
