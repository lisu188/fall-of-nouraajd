#include "rogue.h"

#include <interactions/skills/sneakattack.h>
#include <interactions/skills/stunner.h>
#include <stats/stats.h>

Assasin::Assasin(Map *map,int x,int y):Player(map,x,y)
{
    loadJsonFile("config/players/assasin.json");
}

void Assasin::levelUp()
{
    Creature::levelUp();
    if(level==1)addAction(new SneakAttack());
    if(level==5)addAction(new Stunner());
}
