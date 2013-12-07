#include "warrior.h"

#include <interactions/skills/doubleattack.h>
#include <interactions/skills/strike.h>
#include <stats/stats.h>

Warrior::Warrior(Map *map,int x,int y ):Player(map,x,y)
{
    className="Warrior";
    setAnimation("images/players/warrior/");

    bonusLevel->setStrength(3);
    bonusLevel->setAgility(2);
    bonusLevel->setIntelligence(1);
    bonusLevel->setStamina(2);

    bonusLevel->setDmgMin(2);
    bonusLevel->setDmgMax(3);

    bonusLevel->setHit(3);
    bonusLevel->setCrit(1);

    stats->setMain("S");
}

void Warrior::levelUp()
{
    Creature::levelUp();
    if(level==1)addAction(new Strike());
    if(level==5)addAction(new DoubleAttack());
}
