#include "weapon.h"

#include <view/gamescene.h>
#include <creatures/player.h>
#include <view/gameview.h>


Weapon::Weapon()
{
    className="Weapon";
}

Interaction *Weapon::getInteraction() {
    return interaction;
}

Stats *Weapon::getStats() {
    return &bonus;
}

void Weapon::onUse(Creature *creature)
{
    creature->setWeapon(this);
}


