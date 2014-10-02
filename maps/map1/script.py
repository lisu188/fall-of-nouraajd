from game import CEvent

class StartEvent(CEvent):
    def onEnter(self):
        self.getMap().getGuiHandler().showMessage(self.getStringProperty('text'))
        self.getMap().removeAll(lambda ob: ob.getStringProperty('objectName')==self.getStringProperty('objectName'))



