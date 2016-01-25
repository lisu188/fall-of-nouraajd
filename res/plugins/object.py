def load(self,context):
    from game import randint
    from game import CBuilding
    from game import Coords
    from game import register

    @register(context)
    class Teleporter(CBuilding):
        def onEnter(self,event):
            if self.getBoolProperty("enabled"):
                exit=self.getStringProperty("exit")
                loc=self.getMap().getLocationByName(exit)
                event.getCause().setCoords(loc)

    @register(context)
    class Market(CBuilding):
        def onEnter(self,event):
            self.getMap().getPlayer().trade(self.getObjectProperty("market"))

    #TODO: make monster a prototype and clone it
    @register(context)
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
                mon=self.getMap().createObject(monster)
                controller=self.getMap().createObject('CRangeController')
                controller.setObjectProperty('target',self.ptr())
                mon.setObjectProperty('controller',controller)
                self.getMap().addObject(mon)
                mon.moveTo(location.x,location.y,location.z)
                self.incProperty("monsters",-1);
