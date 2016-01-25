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
};

#define NEAR_COORDS(coords) {Coords(coords.x + 1,coords.y,coords.z),Coords(coords.x - 1,coords.y,coords.z ),Coords(coords.x,coords.y + 1, coords.z ),Coords(coords.x,coords.y - 1,coords.z )}