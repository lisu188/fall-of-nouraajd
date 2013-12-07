#include "mage.h"

#include <interactions/spells/magicmissile.h>
#include <interactions/spells/chaosblast.h>
#include <interactions/spells/frostbolt.h>
#include <stats/stats.h>

Mage::Mage(Map *map,int x,int y):Player(map,x,y)
{
    className="Mage";
    setAnimation("images/players/mage/");

    bonusLevel->setStrength(1);
    bonusLevel->setAgility(2);
    bonusLevel->setIntelligence(3);
    bonusLevel->setStamina(1);

    bonusLevel->setDmgMin(1);
    bonusLevel->setDmgMax(1);

    bonusLevel->setHit(1);
    bonusLevel->setCrit(1);

    stats->setMain("I");
}

void Mage::levelUp()
{
    Creature::levelUp();
    if(level==1)addAction(new MagicMissile());
    if(level==3)addAction(new FrostBolt());
    if(level==7)addAction(new ChaosBlast());
}
