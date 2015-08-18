#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "templates/future.h"

class CCreature;

class CSmartPathFinder {
public:
    static std::shared_ptr<vstd::future<Coords>> findNextStep ( Coords start, Coords goal,
            std::function<bool ( const Coords& ) > canStep );
    static std::list<Coords> findPath (  Coords start,  Coords goal,
                                         std::function<bool ( const Coords& ) > canStep );
};
