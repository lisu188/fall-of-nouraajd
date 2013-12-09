#include "warrior.h"

#include <interactions/skills/doubleattack.h>
#include <interactions/skills/strike.h>
#include <stats/stats.h>

Warrior::Warrior(Map *map,int x,int y ):Player(map,x,y)
{
    loadJsonFile("config/players/warrior.json");
}

void Warrior::levelUp()
{
    Creature::levelUp();
    if(level==1)addAction(new Strike());
    if(level==5)addAction(new DoubleAttack());
}
