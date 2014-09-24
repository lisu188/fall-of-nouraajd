import random
from game import CBuilding
from game import Coords

class Teleporter(CBuilding):
    def __init__(self):
        super(Teleporter,self).__init__()

    def onEnter(self):
        if self.getBoolProperty("enabled"):
            exit=self.getStringProperty("exit")
            loc=self.getMap().getLocationByName(exit)
            self.getMap().getPlayer().setCoords(loc)

class Cave(CBuilding):
    def __init__(self):
        super(Cave,self).__init__()

    def onEnter(self):
        if self.getBoolProperty("enabled"):
            self.setBoolProperty("enabled",False);
            location=self.getCoords()
            monster=self.getStringProperty("monster")
            for i in range(-1,2):
                for j in range(-1,2):
                    if j == 0 and i == 0:
                        continue;
                    self.getMap().addObjectByName(monster,Coords(location.x+i,location.y+j,location.z));
            self.getMap().removeObject(self);

    def onMove(self):
        chance=self.getNumericProperty("chance");
        monsters=self.getNumericProperty("monsters");
        monster=self.getStringProperty("monster");
        enabled=self.getBoolProperty("enabled");
        if enabled and monsters >0 and (random.randint(1,100)) <= chance:
            location=self.getCoords()
            self.getMap().addObjectByName(monster,Coords(location.x,location.y,location.z));
            self.incProperty("monsters",-1);
