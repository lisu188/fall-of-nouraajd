#include "potioneffect.h"

#ifndef LIFEPOTIONEFFECT_H
#define LIFEPOTIONEFFECT_H

class LifePotionEffect : public PotionEffect
{
public:
    LifePotionEffect();

    // PotionEffect interface
public:
    virtual void effect(Creature *creature, int power);
};

#endif // LIFEPOTIONEFFECT_H
