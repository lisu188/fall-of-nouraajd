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
    from game import CScroll
    from game import register

    @register(context)
    class TownPortalScroll(CScroll):
        def onUse(self, event):
            # Teleport the event cause (usually the player) to the starting
            # location on the current map
            cur_map = event.getCause().getMap()
            event.getCause().moveTo(
                cur_map.getEntryX(), cur_map.getEntryY(), cur_map.getEntryZ()
            )

        def isDisposable(self):
            return True
