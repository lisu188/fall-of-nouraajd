from _Game import Building

class Teleporter(Building):
    def onEnter(self):
        if self.getBoolProperty("enabled"):
            exit=self.getStringProperty("exit")
            loc=self.getMap().getLocationByName(exit)
            self.getMap().getPlayer().setCoords(loc)
