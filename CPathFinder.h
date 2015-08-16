#pragma once
#include "CGlobal.h"
#include "CUtil.h"

class CCreature;

class CSmartPathFinder {
public:
    static Coords findNextStep ( const Coords &start, const Coords &goal,
                                 std::function<bool ( const Coords& ) > canStep );
    static std::list<Coords> findPath ( const Coords &start, const Coords &goal,
                                        std::function<bool ( const Coords& ) > canStep );
};
