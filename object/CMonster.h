#pragma once

#include "CCreature.h"

class CMonster : public CCreature {
    Q_OBJECT
public:
    CMonster();
    virtual ~CMonster();
    virtual void onTurn ( std::shared_ptr<CGameEvent> ) override;
    virtual void levelUp() override;
    virtual Coords getNextMove();
};
