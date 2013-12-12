#include "potioneffect.h"

#ifndef MANAPOTIONEFFECT_H
#define MANAPOTIONEFFECT_H

class ManaPotionEffect : public PotionEffect
{
public:
    ManaPotionEffect();

    // PotionEffect interface
public:
    virtual void effect(Creature *creature, int power);
};

#endif // MANAPOTIONEFFECT_H
