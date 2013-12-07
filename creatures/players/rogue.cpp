#include "rogue.h"

#include <interactions/skills/sneakattack.h>
#include <interactions/skills/stun.h>
#include <stats/stats.h>

Rogue::Rogue(Map *map,int x,int y):Player(map,x,y)
{
    className="Rogue";
    setAnimation("images/players/rogue/");

    bonusLevel->setStrength(1);
    bonusLevel->setAgility(3);
    bonusLevel->setIntelligence(2);
    bonusLevel->setStamina(1);

    bonusLevel->setDmgMin(1);
    bonusLevel->setDmgMax(2);

    bonusLevel->setHit(3);
    bonusLevel->setCrit(2);

    stats->setMain("A");
}

void Rogue::levelUp()
{
    Creature::levelUp();
    if(level==1)addAction(new SneakAttack());
    if(level==5)addAction(new Stun());
}
