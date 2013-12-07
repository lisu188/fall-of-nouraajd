#include "poisonpotion.h"

PoisonPotion::PoisonPotion()
{
    className="PoisonPotion";
    setAnimation("images/items/potions/poison/");
}

void PoisonPotion::onUse(Creature *creature)
{
    Potion::onUse(creature);
}
