#include "abyssalshadows.h"

#include <effects/abyssalshadowseffect.h>
#include <items/weapons/weapon.h>
#include <stats/stats.h>
#include <creatures/creature.h>

AbyssalShadows::AbyssalShadows()
{
    className="AbyssalShadows";
    manaCost=15;
    setAnimation("images/spells/abyssalshadows/");
}


void AbyssalShadows::action(Creature *first, Creature *second)
{
    second->addEffect(new AbyssalShadowsEffect(first,4));
}
