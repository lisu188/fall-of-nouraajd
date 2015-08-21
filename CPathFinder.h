#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "templates/future.h"

class CCreature;

class CSmartPathFinder {
public:
    //TODO change naming
    static std::shared_ptr<vstd::future<std::function<Coords() >>> findNextStep ( Coords start, Coords goal,
            std::function<bool ( const Coords& ) > canStep );
    static std::list<Coords> findPath (  Coords start,  Coords goal,
                                         std::function<bool ( const Coords& ) > canStep );
};
