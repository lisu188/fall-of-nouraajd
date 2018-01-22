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