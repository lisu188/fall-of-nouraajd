#include "lifepotion.h"

#include <view/gamescene.h>

LifePotion::LifePotion()
{
    className="LifePotion";
    setAnimation("images/items/potions/life/");
}

void LifePotion::onUse(Creature *creature)
{
    Potion::onUse(creature);
    creature->healProc(20);
}
