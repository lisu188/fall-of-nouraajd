#include "endlesspaineffect.h"
#include <creatures/creature.h>
EndlessPainEffect::EndlessPainEffect(Creature *caster, int duration):Effect(caster,duration)
{
    className="EndlessPainEffect";
}

bool EndlessPainEffect::apply(Creature *creature)
{
    creature->hurt(caster->getDmg()*15.0/100.0);
    return true&&Effect::apply(creature);
}
