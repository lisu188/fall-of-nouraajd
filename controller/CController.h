#pragma once

#include "object/CObject.h"
#include "CPathFinder.h"

class CController : public CGameObject{
    Q_OBJECT
public:
    virtual void control(std::shared_ptr<CCreature> c)=0;
};
GAME_PROPERTY(CController)
