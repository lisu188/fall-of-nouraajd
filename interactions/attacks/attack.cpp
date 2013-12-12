#include "attack.h"

#include <creatures/creature.h>

#include <items/weapon.h>

Attack::Attack()
{
    className="Attack";
    setAnimation("images/attacks/attack/");
}

void Attack::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    int dmg=first->getDmg();
    if(dmg)
    {
        second->hurt(dmg);
        Weapon *weapon=first->getWeapon();
        if(weapon)
        {
            Interaction *interaction=weapon->getInteraction();
            if(interaction)
            {
                interaction->action(first,second);
            }
        }
    }
}

Interaction *Attack::clone()
{
    return new Attack();
}
