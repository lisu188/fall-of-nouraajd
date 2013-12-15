#include "effects/stun.h"

#include <creatures/creature.h>

Stun::Stun(Creature *caster, int duration):Effect(caster,duration)
{
    className="Stun";
}


