#include "abyssalshadowseffect.h"

#include <creatures/creature.h>

AbyssalShadowsEffect::AbyssalShadowsEffect(Creature *caster, int dur):Effect(caster,dur)
{
    className="AbyssalShadowsEffect";
}

bool AbyssalShadowsEffect::apply(Creature *creature)
{
    if(dur>1)
    {
        Damage tmp;
        tmp.setShadow(caster->getDmg()*45.0/100.0);
        creature->hurt(tmp);
    }
    else
    {
        Damage tmp;
        tmp.setShadow(caster->getDmg());
        creature->hurt(tmp);
    }
    return false&&Effect::apply(creature);
}
