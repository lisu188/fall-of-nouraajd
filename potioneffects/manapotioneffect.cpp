#include "manapotioneffect.h"

#include <creatures/creature.h>

ManaPotionEffect::ManaPotionEffect()
{
}

void ManaPotionEffect::effect(Creature *creature, int power)
{
    creature->addManaProc(power*20);
}
