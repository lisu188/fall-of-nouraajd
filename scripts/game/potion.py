from game import CPotion


class LifePotion(CPotion):
    def onUse(self,creature):
        power=self.getNumericProperty('power')
        creature.healProc ( power * 20 );
        return True


class ManaPotion(CPotion):
    def onUse(self,creature):
        power=self.getNumericProperty('power')
        creature.addManaProc ( power * 20 );
        return True
