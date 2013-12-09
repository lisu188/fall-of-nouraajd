#include "weapon.h"

#include <view/gamescene.h>
#include <creatures/players/player.h>
#include <view/gameview.h>


Weapon::Weapon()
{
    className="Weapon";
}

Interaction *Weapon::getInteraction() {
    return interaction;
}

void Weapon::onUse(Creature *creature)
{
    creature->setWeapon(this);
}


