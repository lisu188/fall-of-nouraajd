/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"

class CCreature;

class CPathFinder {
public:
    //TODO change naming
    static std::shared_ptr<vstd::future<Coords, void> > findNextStep(Coords start, Coords goal,
                                                                     std::function<bool(const Coords &)> canStep);

    static std::list<Coords> findPath(Coords start, Coords goal,
                                      std::function<bool(const Coords &)> canStep);

    static void saveMap(Coords start, std::function<bool(const Coords &)> canStep, std::string path);
};

#define NEAR_COORDS(coords) {Coords(coords.x + 1,coords.y,coords.z),Coords(coords.x - 1,coords.y,coords.z ),Coords(coords.x,coords.y + 1, coords.z ),Coords(coords.x,coords.y - 1,coords.z )}
#define NEAR_COORDS_WITH(coords) {Coords(coords.x,coords.y,coords.z),Coords(coords.x + 1,coords.y,coords.z),Coords(coords.x - 1,coords.y,coords.z ),Coords(coords.x,coords.y + 1, coords.z ),Coords(coords.x,coords.y - 1,coords.z )}