from game import CEvent
from game import CTrigger

class StartEvent(CEvent):
    def onEnter(self,event):
        if event.getCause().isPlayer():
            self.getMap().getGuiHandler().showMessage(self.getStringProperty('text'))
            self.getMap().removeAll(lambda ob: ob.getStringProperty('objectType')==self.getStringProperty('objectType'))

class GoobyTrigger(CTrigger):
    def trigger(self,object,event):
        object.getMap().getGuiHandler().showMessage("Gooby killed!!!")
