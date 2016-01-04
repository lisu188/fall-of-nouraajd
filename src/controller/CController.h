#pragma once

#include "object/CObject.h"
#include "core/CPathFinder.h"

class CController : public CGameObject {
    
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control ( std::shared_ptr<CCreature> c ) = 0;
};

GAME_PROPERTY ( CController )

