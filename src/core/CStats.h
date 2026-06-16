/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "object/CMapObject.h"

class CStats : public CGameObject {

    V_META(CStats, CGameObject, V_PROPERTY(CStats, int, strength, getStrength, setStrength),
           V_PROPERTY(CStats, int, agility, getAgility, setAgility),
           V_PROPERTY(CStats, int, stamina, getStamina, setStamina),
           V_PROPERTY(CStats, int, intelligence, getIntelligence, setIntelligence),
           V_PROPERTY(CStats, int, armor, getArmor, setArmor), V_PROPERTY(CStats, int, block, getBlock, setBlock),
           V_PROPERTY(CStats, int, dmgMin, getDmgMin, setDmgMin), V_PROPERTY(CStats, int, dmgMax, getDmgMax, setDmgMax),
           V_PROPERTY(CStats, int, attack, getAttack, setAttack), V_PROPERTY(CStats, int, hit, getHit, setHit),
           V_PROPERTY(CStats, int, crit, getCrit, setCrit),
           V_PROPERTY(CStats, int, fireResist, getFireResist, setFireResist),
           V_PROPERTY(CStats, int, frostResist, getFrostResist, setFrostResist),
           V_PROPERTY(CStats, int, normalResist, getNormalResist, setNormalResist),
           V_PROPERTY(CStats, int, thunderResist, getThunderResist, setThunderResist),
           V_PROPERTY(CStats, int, shadowResist, getShadowResist, setShadowResist),
           V_PROPERTY(CStats, int, damage, getDamage, setDamage),
           V_PROPERTY(CStats, std::string, mainStat, getMainStat, setMainStat))

    int attack = 0;
    int damage = 0;
    int shadowResist = 0;
    int thunderResist = 0;
    int normalResist = 0;
    int frostResist = 0;
    int fireResist = 0;
    int crit = 0;
    int hit = 0;
    int dmgMax = 0;
    int dmgMin = 0;
    int block = 0;
    int armor = 0;
    int intelligence = 0;
    int stamina = 0;
    int agility = 0;
    int strength = 0;

  public:
    CStats();

    void addBonus(std::shared_ptr<CStats> stats);

    void removeBonus(std::shared_ptr<CStats> stats);

    std::string getText(int level);

    int getAttack() const;

    void setAttack(int value);

    int getDamage() const;

    void setDamage(int value);

    int getShadowResist() const;

    void setShadowResist(int value);

    int getThunderResist() const;

    void setThunderResist(int value);

    int getNormalResist() const;

    void setNormalResist(int value);

    int getFrostResist() const;

    void setFrostResist(int value);

    int getFireResist() const;

    void setFireResist(int value);

    int getCrit() const;

    void setCrit(int value);

    int getHit() const;

    void setHit(int value);

    int getDmgMax() const;

    void setDmgMax(int value);

    int getDmgMin() const;

    void setDmgMin(int value);

    int getBlock() const;

    void setBlock(int value);

    int getArmor() const;

    void setArmor(int value);

    int getIntelligence() const;

    void setIntelligence(int value);

    int getStamina() const;

    void setStamina(int value);

    int getAgility() const;

    void setAgility(int value);

    int getStrength() const;

    void setStrength(int value);

    std::string getMainStat() const;

    void setMainStat(const std::string &value);

    int getMainValue();

  private:
    std::string mainStat;
};

class CDamage : public CGameObject {

    V_META(CDamage, CGameObject, V_PROPERTY(CDamage, int, fire, getFire, setFire),
           V_PROPERTY(CDamage, int, thunder, getThunder, setThunder),
           V_PROPERTY(CDamage, int, shadow, getShadow, setShadow), V_PROPERTY(CDamage, int, frost, getFrost, setFrost),
           V_PROPERTY(CDamage, int, normal, getNormal, setNormal))

    int fire = 0;
    int frost = 0;
    int thunder = 0;
    int shadow = 0;
    int normal = 0;

  public:
    CDamage();

    int getFire() const;

    void setFire(int value);

    int getFrost() const;

    void setFrost(int value);

    int getThunder() const;

    void setThunder(int value);

    int getShadow() const;

    void setShadow(int value);

    int getNormal() const;

    void setNormal(int value);
};
