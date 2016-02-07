#pragma once

#include "CCreature.h"

class CMonster : public CCreature {
V_META(CMonster, CCreature, vstd::meta::empty())
public:
    CMonster();

    virtual ~CMonster();

    virtual void onTurn(std::shared_ptr<CGameEvent>) override;

    virtual void levelUp() override;

};


