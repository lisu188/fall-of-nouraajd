#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "object/CMapObject.h"

class Stats : public CGameObject {

V_META(Stats, CGameObject,
       V_PROPERTY(Stats, int, strength, getStrength, setStrength),
       V_PROPERTY(Stats, int, agility, getAgility, setAgility),
       V_PROPERTY(Stats, int, stamina, getStamina, setStamina),
       V_PROPERTY(Stats, int, intelligence, getIntelligence, setIntelligence),
       V_PROPERTY(Stats, int, armor, getArmor, setArmor),
       V_PROPERTY(Stats, int, block, getBlock, setBlock),
       V_PROPERTY(Stats, int, dmgMin, getDmgMin, setDmgMin),
       V_PROPERTY(Stats, int, dmgMax, getDmgMax, setDmgMax),
       V_PROPERTY(Stats, int, hit, getHit, setHit),
       V_PROPERTY(Stats, int, crit, getCrit, setCrit),
       V_PROPERTY(Stats, int, fireResist, getFireResist, setFireResist),
       V_PROPERTY(Stats, int, frostResist, getFrostResist, setFrostResist),
       V_PROPERTY(Stats, int, normalResist, getNormalResist, setNormalResist),
       V_PROPERTY(Stats, int, thunderResist, getThunderResist, setThunderResist),
       V_PROPERTY(Stats, int, shadowResist, getShadowResist, setShadowResist),
       V_PROPERTY(Stats, int, damage, getDamage, setDamage),
       V_PROPERTY(Stats, std::string, mainStat, getMainStat, setMainStat)
)

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
    Stats();

    void addBonus(std::shared_ptr<Stats> stats);

    void removeBonus(std::shared_ptr<Stats> stats);

    const char *getText(int level);

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


class Damage : public CGameObject {

V_META(Damage, CGameObject,
       V_PROPERTY(Damage, int, fire, getFire, setFire),
       V_PROPERTY(Damage, int, thunder, getThunder, setThunder),
       V_PROPERTY(Damage, int, shadow, getShadow, setShadow),
       V_PROPERTY(Damage, int, frost, getFrost, setFrost),
       V_PROPERTY(Damage, int, normal, getNormal, setNormal)
)

    int fire = 0;
    int frost = 0;
    int thunder = 0;
    int shadow = 0;
    int normal = 0;
public:
    Damage();

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


