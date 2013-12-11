#include "endlesspain.h"

#include <stats/damage.h>
#include <effects/endlesspaineffect.h>
#include <items/weapons/weapon.h>
#include <creatures/creature.h>

EndlessPain::EndlessPain()
{
    className="EndlessPain";
    manaCost=25;
    setAnimation("images/spells/endlesspain/");
}

void EndlessPain::action(Creature *first, Creature *second)
{
    Damage damage;
    damage.setShadow(first->getWeapon()->getStats()->getDamage()*15.0/100.0);//change to shadow
    second->addEffect(new EndlessPainEffect(2,&damage));
}
