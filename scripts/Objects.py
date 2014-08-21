from _Game import Building

class Teleporter(Building):
    def __init__(self):
        super(Teleporter,self).__init__()

    def onEnter(self):
        if self.getBoolProperty("enabled"):
            exit=self.getStringProperty("exit")
            loc=self.getMap().getLocationByName(exit)
            self.getMap().getPlayer().setCoords(loc)

class Cave(Building):
    def __init__(self):
        super(Cave,self).__init__()
