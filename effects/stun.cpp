#include "effects/stun.h"

Stun::Stun(int duration):Effect(duration)
{
}

bool Stun::apply(Creature *creature)
{
    return(true&&Effect::apply(creature));
}
