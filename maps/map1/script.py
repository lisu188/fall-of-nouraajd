from game import CEvent

class StartEvent(CEvent):
    def onEnter(self,event):
        if event.getCause().isPlayer():
            self.getMap().getGuiHandler().showMessage(self.getStringProperty('text'))
            self.getMap().removeAll(lambda ob: ob.getStringProperty('objectType')==self.getStringProperty('objectType'))
