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

class CaveTrigger(CTrigger):
    def trigger(self,object,event):
        object.getMap().getGuiHandler().showMessage("You feel the ground shaking, and see the ratmen all around you!!! But the one part is missing in this puzzle. Letter said about the ratmen who was much bigger than the other. These here are just ordinary pritschers.")
        gooby=object.getMap().getObjectHandler().createObject("Gooby")
        gooby.setStringProperty("objectName","gooby1")
        object.getMap().addObject(gooby)
        gooby.moveTo(100,100,0)