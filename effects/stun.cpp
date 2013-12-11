#include "effects/stun.h"

#include <creatures/creature.h>

Stun::Stun(Creature *caster, int duration):Effect(caster,duration)
{
    className="Stun";
}

bool Stun::apply(Creature *creature)
{
    return(true&&Effect::apply(creature));
}
