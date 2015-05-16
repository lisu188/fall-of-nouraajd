#pragma once

#include "CCreature.h"

class CMonster : public CCreature {
    Q_OBJECT
public:
    CMonster();
    virtual ~CMonster();
    virtual void onTurn ( CGameEvent * ) override;
    virtual void levelUp() override;
    virtual Coords getNextMove();
};
