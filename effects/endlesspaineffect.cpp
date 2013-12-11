#include "endlesspaineffect.h"
#include <creatures/creature.h>
EndlessPainEffect::EndlessPainEffect(int duration, Damage *dmg):Effect(duration),damage(dmg)
{
    className="EndlessPainEffect";
}

bool EndlessPainEffect::apply(Creature *creature)
{
    creature->hurt(*damage);
    return true&&Effect::apply(creature);
}
