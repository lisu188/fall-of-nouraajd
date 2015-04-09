from game import CEvent
from game import CTrigger
from game import CQuest
from game import game_object,game_trigger

completed = False

@game_object
class StartEvent(CEvent):
    def onEnter(self,event):
        if event.getCause().isPlayer():

            self.getMap().removeAll(lambda ob: ob.getStringProperty('objectType')==self.getStringProperty('objectType'))

@game_trigger(event="onDestroy",object="gooby1")
class GoobyTrigger(CTrigger):
    def trigger(self,object,event):

        global completed
        completed=True

@game_trigger(event="onDestroy",object="cave1")
class CaveTrigger(CTrigger):
    def trigger(self,object,event):


        gooby.setStringProperty("objectName","gooby1")
        object.getMap().addObject(gooby)
        gooby.moveTo(100,100,0)
        object.getMap().getPlayer().addQuest("mainQuest")

@game_object
class MainQuest(CQuest):
    def isCompleted(self):
        return completed

    def onComplete(self):
        pass

def onStart(self):
    pass
