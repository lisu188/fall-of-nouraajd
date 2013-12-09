#include "pritzmage.h"

#include <interactions/spells/magicmissile.h>

PritzMage::PritzMage(Map* map, int x, int y):Monster(map,x,y)
{
    loadJsonFile("config/monsters/pritzmage.json");
}

void PritzMage::levelUp()
{
    Creature::levelUp();
    if(level==2)addAction(new MagicMissile());
}
