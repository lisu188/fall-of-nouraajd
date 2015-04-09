from game import CPotion
from game import game_object

@game_object
class LifePotion(CPotion):
    def onUse(self,event):
        power=self.getNumericProperty('power')
        event.getCause().healProc ( power * 20 );

@game_object
class ManaPotion(CPotion):
    def onUse(self,event):
        power=self.getNumericProperty('power')
        event.getCause().addManaProc ( power * 20 );
