# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025  Andrzej Lis
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
    from game import CScroll
    @register(context)
    class WayPoint(CBuilding):
        def onEnter(self, event):
            if self.getExit():
                event.getCause().setCoords(self.getExit())

        # merge with onEnter logic
        def onTurn(self, event):
            self.setBoolProperty('waypoint', True)
            exit = self.getExit()
            self.setNumericProperty('x', exit.x)
            self.setNumericProperty('y', exit.y)
            self.setNumericProperty('z', exit.z)

        def getExit(self):
            pass

    @register(context)
    class Teleporter(WayPoint):
        def getExit(self):
            if self.getBoolProperty("enabled"):
                exit = self.getStringProperty("exit")
                loc = self.getMap().getLocationByName(exit)
                return loc

    @register(context)
    class GroundHole(WayPoint):
        def getExit(self):
            loc = self.getCoords()
            return Coords(loc.x, loc.y, loc.z - 1)

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
                self.getMap().removeObjectByName(self.getName())

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

    @register(context)
    class TownPortalScroll(CScroll):
        def onUse(self, event):
            cur_map = event.getCause().getMap()
            event.getCause().moveTo(
                cur_map.getEntryX(), cur_map.getEntryY(), cur_map.getEntryZ()
            )

        def isDisposable(self):
            return True
