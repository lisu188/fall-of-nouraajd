#include "warrior.h"

#include <interactions/skills/doubleattack.h>
#include <interactions/skills/strike.h>
#include <stats/stats.h>

Warrior::Warrior(Map *map,int x,int y ):Player(map,x,y)
{
    initializeFromFile("config/players/warrior.json");
}
