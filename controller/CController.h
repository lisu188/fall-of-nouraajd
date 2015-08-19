#pragma once

#include "object/CObject.h"
#include "CPathFinder.h"

class CController : public CGameObject {
    Q_OBJECT
public:
    virtual std::shared_ptr<vstd::future<void>> control ( std::shared_ptr<CCreature> c ) =0;
};
GAME_PROPERTY ( CController )

