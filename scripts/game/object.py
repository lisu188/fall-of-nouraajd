from game import randint
from game import CBuilding
from game import Coords

class Teleporter(CBuilding):
    def onEnter(self,event):
        if self.getBoolProperty("enabled"):
            exit=self.getStringProperty("exit")
            loc=self.getMap().getLocationByName(exit)
            event.getCause().setCoords(loc)

class Market(CBuilding):
    market=None
    def onEnter(self,event):
        if not self.market:
            self.market=self.getMap().getObjectHandler().createObject(self.getStringProperty('market'))
        self.getMap().getPlayer().trade(self.market)

class Cave(CBuilding):
    def onEnter(self,event):
        if not event.getCause().isPlayer():
            return
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

    def onTurn(self,event):
        chance=self.getNumericProperty("chance");
        monsters=self.getNumericProperty("monsters");
        monster=self.getStringProperty("monster");
        enabled=self.getBoolProperty("enabled");
        if enabled and monsters >0 and (randint(1,100)) <= chance:
            location=self.getCoords()
            self.getMap().addObjectByName(monster,Coords(location.x,location.y,location.z));
            self.incProperty("monsters",-1);
