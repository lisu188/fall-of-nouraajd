#include "abyssalshadows.h"

#include <effects/damageovertime.h>
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
    damage.setNormal(first->getWeapon()->getStats()->getDamage()*45.0/100.0);//change to shadow
    second->addEffect(new DamageOverTime(4,damage));
}
