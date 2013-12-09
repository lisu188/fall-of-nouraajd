#include "mage.h"

#include <interactions/spells/magicmissile.h>
#include <interactions/spells/chaosblast.h>
#include <interactions/spells/frostbolt.h>
#include <stats/stats.h>

Sorcerer::Sorcerer(Map *map,int x,int y):Player(map,x,y)
{
    loadJsonFile("config/players/sorcerer.json");
}

void Sorcerer::levelUp()
{
    Creature::levelUp();
    if(level==1)addAction(new MagicMissile());
    if(level==3)addAction(new FrostBolt());
    if(level==7)addAction(new ChaosBlast());
}
