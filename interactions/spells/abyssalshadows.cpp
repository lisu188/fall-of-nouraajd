#include "abyssalshadows.h"

#include <effects/abyssalshadowseffect.h>
#include <items/weapons/weapon.h>
#include <stats/stats.h>

AbyssalShadows::AbyssalShadows()
{
    className="AbyssalShadows";
    manaCost=15;
    setAnimation("images/spells/abyssalshadows/");
}


void AbyssalShadows::action(Creature *first, Creature *second)
{
    Damage damage;
    damage.setShadow(first->getWeapon()->getStats()->getDamage());//change to shadow
    second->addEffect(new AbyssalShadowsEffect(4,&damage));
}
