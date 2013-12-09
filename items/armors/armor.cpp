#include "armor.h"

#include <view/gamescene.h>

Armor::Armor()
{
    className="Armor";
    bonus=new Stats();
    bonus->setBlock(5);
    bonus->setArmor(10);
    interaction=0;
}

void Armor::onUse(Creature *creature)
{
    creature->setArmor(this);
}
