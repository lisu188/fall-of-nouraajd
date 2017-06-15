def load(self, context):
    from game import randint
    from game import CBuilding
    from game import Coords
    from game import register

    @register(context)
    class Teleporter(CBuilding):
        def onEnter(self, event):
            if self.getBoolProperty("enabled"):
                exit = self.getStringProperty("exit")
                loc = self.getMap().getLocationByName(exit)
                event.getCause().setCoords(loc)

    @register(context)
    class Market(CBuilding):
        def onEnter(self, event):
            self.getMap().getPlayer().trade(self.getObjectProperty("market"))

    @register(context)
    class Cave(CBuilding):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("enabled"):
                self.setBoolProperty("enabled", False);
                location = self.getCoords()
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        if j == 0 and i == 0 and not self.getMap().canStep(
                                Coords(location.x + i, location.y + j, location.z)):
                            continue;
                        mon = self.getObjectProperty('monster').clone()
                        self.getMap().addObject(mon)
                        mon.moveTo(location.x + i, location.y + j, location.z)
                self.getMap().removeObject(self.ptr());  # TODO: WHY

        def onTurn(self, event):
            chance = self.getNumericProperty("chance");
            monsters = self.getNumericProperty("monsters");
            enabled = self.getBoolProperty("enabled");
            if enabled and monsters > 0 and (randint(1, 100)) <= chance:
                location = self.getCoords()
                mon = self.getObjectProperty('monster').clone()
                self.getMap().addObject(mon)
                mon.moveTo(location.x, location.y, location.z)
                self.incProperty("monsters", -1);
