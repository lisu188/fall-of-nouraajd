def load(self, context):
    from game import CPotion
    from game import register

    @register(context)
    class LifePotion(CPotion):
        def onUse(self, event):
            power = self.getNumericProperty('power')
            event.getCause().healProc(power * 20);

    @register(context)
    class ManaPotion(CPotion):
        def onUse(self, event):
            power = self.getNumericProperty('power')
            event.getCause().addManaProc(power * 20);
