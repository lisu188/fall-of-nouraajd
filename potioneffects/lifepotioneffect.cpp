#include "lifepotioneffect.h"

#include <creatures/creature.h>

LifePotionEffect::LifePotionEffect()
{
}

void LifePotionEffect::effect(Creature *creature, int power)
{
    creature->healProc(power*20);
}
