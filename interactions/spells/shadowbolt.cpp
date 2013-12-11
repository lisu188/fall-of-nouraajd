#include "shadowbolt.h"

#include <effects/abyssalshadowseffect.h>
#include <items/weapons/weapon.h>
#include <stats/stats.h>
#include <creatures/creature.h>

ShadowBolt::ShadowBolt()
{
    className="ShadowBolt";
    manaCost=45;
    setAnimation("images/spells/shadowbolt/");
}

void ShadowBolt::action(Creature *first, Creature *second)
{
    Damage damage;
    damage.setShadow(first->getDmg()*2.25);
    second->hurt(damage);
    if(rand()%2==0)
    {
        damage.setShadow(first->getWeapon()->getStats()->getDamage());
        second->addEffect(new AbyssalShadowsEffect(first,4));
    }
}
