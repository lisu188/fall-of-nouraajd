#include "pritz.h"

#include <items/potions/manapotion.h>

Pritz::Pritz(Map *map, int x, int y):Monster(map,x,y)
{
    loadJsonFile("config/monsters/pritz.json");
}
