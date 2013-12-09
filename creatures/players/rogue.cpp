#include "rogue.h"

#include <interactions/skills/sneakattack.h>
#include <interactions/skills/stunner.h>
#include <stats/stats.h>

Assasin::Assasin(Map *map,int x,int y):Player(map,x,y)
{
    initializeFromFile("config/players/assasin.json");
}
