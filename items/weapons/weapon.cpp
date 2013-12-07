#include "weapon.h"

#include <view/gamescene.h>
#include <creatures/players/player.h>
#include <view/gameview.h>

Weapon::Weapon()
{
    className="Weapon";
    bonus=new Stats();
    bonus->setDamage(5);
    bonus->setAttack(3);
    interaction=0;
}

void Weapon::onUse(Creature *creature)
{
    creature->setWeapon(this);
}
