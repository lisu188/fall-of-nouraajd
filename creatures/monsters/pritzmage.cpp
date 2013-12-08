#include "pritzmage.h"

#include <interactions/spells/magicmissile.h>

PritzMage::PritzMage(Map* map, int x, int y):Pritz(map,x,y)
{
    className="PritzMage";
    this->setAnimation("images/monsters/pritzmage/");
    bonusLevel->setIntelligence(3);
    stats->setMain("I");
    sw=2;
}

void PritzMage::levelUp()
{
    Pritz::levelUp();
    if(level==2)addAction(new MagicMissile());
}
