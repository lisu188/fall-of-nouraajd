#include "damageovertime.h"

#include <creatures/creature.h>

DamageOverTime::DamageOverTime(int duration, Damage dmg):Effect(duration),damage(dmg)
{
}

bool DamageOverTime::apply(Creature *creature)
{
    if(dur>0)
    {
        creature->hurt(damage);
    }
    return false&&Effect::apply(creature);
}
