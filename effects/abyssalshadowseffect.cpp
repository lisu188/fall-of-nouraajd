#include "abyssalshadowseffect.h"

#include <creatures/creature.h>

AbyssalShadowsEffect::AbyssalShadowsEffect(int dur,Damage dmg):Effect(dur),damage(dmg)
{
    className="AbyssalShadowsEffect";
}

bool AbyssalShadowsEffect::apply(Creature *creature)
{
    if(dur>1)
    {
        Damage tmp;
        tmp.setShadow(damage.getShadow()*45.0/100.0);
        creature->hurt(tmp);
    }
    else
    {
        creature->hurt(damage);
    }
    return false&&Effect::apply(creature);
}
