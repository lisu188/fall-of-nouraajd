#include "strike.h"
#include "items/weapons/weapon.h"

#include <creatures/creature.h>

Strike::Strike()
{
    className="Strike";
    manaCost=25;
    setAnimation("images/skills/strike/");
}

void Strike::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    if(first->getWeapon())
    {
        int dmg=first->getDmg();
        if(dmg)
        {
            second->hurt(dmg+first->getStats()->getDamage());
        }
    }
}

Interaction *Strike::clone()
{
    return new Strike();
}
