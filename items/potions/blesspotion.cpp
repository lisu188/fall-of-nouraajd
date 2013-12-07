#include "blesspotion.h"

BlessPotion::BlessPotion()
{
    className="BlessPotion";
    setAnimation("images/items/potions/bless/");
}

void BlessPotion::onUse(Creature *creature)
{
    Potion::onUse(creature);
}
