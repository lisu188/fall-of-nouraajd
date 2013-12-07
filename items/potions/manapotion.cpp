#include "manapotion.h"

#include <view/gamescene.h>

ManaPotion::ManaPotion()
{
    className="ManaPotion";
    setAnimation("images/items/potions/mana/");
}

void ManaPotion::onUse(Creature *creature)
{
    Potion::onUse(creature);
    creature->addManaProc(10);
}
