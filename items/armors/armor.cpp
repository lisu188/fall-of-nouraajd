#include "armor.h"

#include <view/gamescene.h>

Armor::Armor()
{
    className="Armor";
    interaction=0;
}

void Armor::onUse(Creature *creature)
{
    creature->setArmor(this);
}
