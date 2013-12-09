#include "mage.h"

#include <interactions/spells/magicmissile.h>
#include <interactions/spells/chaosblast.h>
#include <interactions/spells/frostbolt.h>
#include <stats/stats.h>

Sorcerer::Sorcerer(Map *map,int x,int y):Player(map,x,y)
{
    initializeFromFile("config/players/sorcerer.json");
}
