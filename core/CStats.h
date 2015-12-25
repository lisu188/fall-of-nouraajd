#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "object/CMapObject.h"

class Stats : public CGameObject {
Q_OBJECT
    Q_PROPERTY(int strength
                       READ
                               getStrength
                       WRITE
                       setStrength USER

                       true)

    Q_PROPERTY(int agility
                       READ
                               getAgility
                       WRITE
                       setAgility USER

                       true)

    Q_PROPERTY(int stamina
                       READ
                               getStamina
                       WRITE
                       setStamina USER

                       true)

    Q_PROPERTY(int intelligence
                       READ
                               getIntelligence
                       WRITE
                       setIntelligence USER

                       true)

    Q_PROPERTY(int armor
                       READ
                               getArmor
                       WRITE
                       setArmor USER

                       true)

    Q_PROPERTY(int block
                       READ
                               getBlock
                       WRITE
                       setBlock USER

                       true)

    Q_PROPERTY(int dmgMin
                       READ
                               getDmgMin
                       WRITE
                       setDmgMin USER

                       true)

    Q_PROPERTY(int dmgMax
                       READ
                               getDmgMax
                       WRITE
                       setDmgMax USER

                       true)

    Q_PROPERTY(int hit
                       READ
                               getHit
                       WRITE
                       setHit USER

                       true)

    Q_PROPERTY(int crit
                       READ
                               getCrit
                       WRITE
                       setCrit USER

                       true)

    Q_PROPERTY(int fireResist
                       READ
                               getFireResist
                       WRITE
                       setFireResist USER

                       true)

    Q_PROPERTY(int frostResist
                       READ
                               getFrostResist
                       WRITE
                       setFrostResist USER

                       true)

    Q_PROPERTY(int normalResist
                       READ
                               getNormalResist
                       WRITE
                       setNormalResist USER

                       true)

    Q_PROPERTY(int thunderResist
                       READ
                               getThunderResist
                       WRITE
                       setThunderResist USER

                       true)

    Q_PROPERTY(int shadowResist
                       READ
                               getShadowResist
                       WRITE
                       setShadowResist USER

                       true)

    Q_PROPERTY(int damage
                       READ
                               getDamage
                       WRITE
                       setDamage USER

                       true)

    Q_PROPERTY(int attack
                       READ
                               getAttack
                       WRITE
                       setAttack USER

                       true)
    Q_PROPERTY (QString
                        mainStat READ
                        getMainStat WRITE
                        setMainStat USER
                        true)
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

    QString getMainStat() const;

    void setMainStat(const QString &value);

    int getMainValue();

private:
    QString mainStat;
};

GAME_PROPERTY (Stats)

class Damage : public CGameObject {
Q_OBJECT
    Q_PROPERTY(int fire
                       READ
                               getFire
                       WRITE
                       setFire USER

                       true)

    Q_PROPERTY(int thunder
                       READ
                               getThunder
                       WRITE
                       setThunder USER

                       true)

    Q_PROPERTY(int shadow
                       READ
                               getShadow
                       WRITE
                       setShadow USER

                       true)

    Q_PROPERTY(int frost
                       READ
                               getFrost
                       WRITE
                       setFrost USER

                       true)

    Q_PROPERTY(int normal
                       READ
                               getNormal
                       WRITE
                       setNormal USER

                       true)
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

GAME_PROPERTY (Damage)
