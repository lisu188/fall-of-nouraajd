/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once

#include "CMapObject.h"
#include "core/CStats.h"

class CEffect : public CGameObject {

V_META(CEffect, CGameObject,
       V_PROPERTY(CEffect, int, duration, getDuration, setDuration),
       V_PROPERTY(CEffect, bool, cumulative, getCumulative, setCumulative)
)

public:
    CEffect();

    virtual ~CEffect();

    int getTimeLeft();

    int getTimeTotal();

    void apply(std::shared_ptr<CCreature> creature);

    std::shared_ptr<Stats> getBonus();

    void setBonus(std::shared_ptr<Stats> value);

    int getDuration();

    void setDuration(int duration);

    virtual void onEffect();

    std::shared_ptr<CCreature> getCaster();

    void setCaster(std::shared_ptr<CCreature> value);

    std::shared_ptr<CCreature> getVictim();

    void setVictim(std::shared_ptr<CCreature> value);

    void setCumulative(bool value);

    bool getCumulative();

private:
    int timeLeft = 0;
    int timeTotal = 0;
    std::shared_ptr<Stats> bonus = std::make_shared<Stats>();
    std::shared_ptr<CCreature> caster;
    std::shared_ptr<CCreature> victim;
    int duration = 0;
    bool cumulative = false;
};


