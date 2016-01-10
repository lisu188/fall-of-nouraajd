#pragma once

#include "CCreature.h"

class CMonster : public CCreature {

public:
    CMonster();

    virtual ~CMonster();

    virtual void onTurn(std::shared_ptr<CGameEvent>) override;

    virtual void levelUp() override;

    virtual Coords getNextMove();
};

GAME_PROPERTY (CMonster)
