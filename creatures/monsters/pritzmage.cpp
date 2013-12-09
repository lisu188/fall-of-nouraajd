#include "pritzmage.h"

#include <interactions/spells/magicmissile.h>

PritzMage::PritzMage(Map* map, int x, int y):Monster(map,x,y)
{
    initializeFromFile("config/monsters/pritzmage.json");
}
