from game import CPotion


class LifePotion(CPotion):
    def onUse(self,event):
        power=self.getNumericProperty('power')
        event.getCause().healProc ( power * 20 );


class ManaPotion(CPotion):
    def onUse(self,event):
        power=self.getNumericProperty('power')
        event.getCause().addManaProc ( power * 20 );
