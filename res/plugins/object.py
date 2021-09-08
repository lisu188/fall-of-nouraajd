# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2019  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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
    class GroundHole(CBuilding):
        def onEnter(self, event):
            loc = self.getCoords()
            event.getCause().setCoords(Coords(loc.x, loc.y, loc.z - 1))

    @register(context)
    class Market(CBuilding):
        def onEnter(self, event):
            pass

    @register(context)
    class SignPost(CBuilding):
        def onEnter(self, event):
            self.getMap().getGame().getGuiHandler().showInfo(self.getStringProperty('text'), True)

    @register(context)
    class Chest(CBuilding):
        def onEnter(self, event):
            self.getMap().getGame().getLootHandler().addRandomLoot(self.getMap().getPlayer(),
                                                                   self.getNumericProperty('value'))

    @register(context)
    class Cave(CBuilding):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("enabled"):
                self.setBoolProperty("enabled", False)
                location = self.getCoords()
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        if not (j == 0 and i == 0):
                            if self.getMap().canStep(
                                    Coords(location.x + i, location.y + j, location.z)):
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
