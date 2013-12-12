#ifndef POTIONEFFECT_H
#define POTIONEFFECT_H
class Creature;
class PotionEffect
{
public:
    PotionEffect();
    virtual void effect(Creature *creature,int power)=0;
    static PotionEffect *getPotionEffect(const char*name);
};

#endif // POTIONEFFECT_H
