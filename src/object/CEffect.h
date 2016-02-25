#pragma once

#include "CMapObject.h"
#include "core/CStats.h"

class CEffect : public CGameObject {

V_META(CEffect, CGameObject,
       V_PROPERTY(CEffect, int, duration, getDuration, setDuration)
)

public:
    CEffect();

    virtual ~CEffect();

    int getTimeLeft();

    int getTimeTotal();

    bool apply(CCreature *creature);

    std::shared_ptr<Stats> getBonus();

    void setBonus(std::shared_ptr<Stats> value);

    int getDuration();

    void setDuration(int duration);

    virtual bool onEffect();

    std::shared_ptr<CCreature> getCaster();

    void setCaster(std::shared_ptr<CCreature> value);

    std::shared_ptr<CCreature> getVictim();

    void setVictim(std::shared_ptr<CCreature> value);

private:
    int timeLeft = 0;
    int timeTotal = 0;
    std::shared_ptr<Stats> bonus = std::make_shared<Stats>();
    std::shared_ptr<CCreature> caster;
    std::shared_ptr<CCreature> victim;
    int duration = 0;
    bool buff = false;
};


