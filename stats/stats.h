#ifndef STATS_H
#define STATS_H
#include <json/json.h>

class Stats
{
public:
    Stats();
    void setMain(const char* stat);
    int getMain();

    void addBonus(Stats stats);
    void removeBonus(Stats stats);

    int getStrength() const;
    void setStrength(int value);

    int getStamina() const;
    void setStamina(int value);

    int getAgility() const;
    void setAgility(int value);

    int getIntelligence() const;
    void setIntelligence(int value);

    int getArmor() const;
    void setArmor(int value);

    int getBlock() const;
    void setBlock(int value);

    int getDmgMin() const;
    void setDmgMin(int value);

    int getDmgMax() const;
    void setDmgMax(int value);

    int getHit() const;
    void setHit(int value);

    int getCrit() const;
    void setCrit(int value);

    int getFireResist() const;
    void setFireResist(int value);

    int getThunderResist() const;
    void setThunderResist(int value);

    int getFrostResist() const;
    void setFrostResist(int value);

    int getNormalResist() const;
    void setNormalResist(int value);

    int getDamage() const;
    void setDamage(int value);

    int getAttack() const;
    void setAttack(int value);

    const char *getText(int level);
    void init(Json::Value statConfig);

    int getShadowResist() const;
    void setShadowResist(int value);

private:
    int strength=0;
    int stamina=0;
    int agility=0;
    int intelligence=0;

    int armor=0;
    int block=0;

    int dmgMin=0;
    int dmgMax=0;
    int hit=0;
    int crit=0;

    int fireResist=0;
    int thunderResist=0;
    int frostResist=0;
    int normalResist=0;
    int shadowResist=0;

    int damage=0;
    int attack=0;

    int *main=0;
};

#endif // STATS_H
