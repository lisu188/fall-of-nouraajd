#include "chaosblast.h"

#include <stats/damage.h>

#include <creatures/creature.h>

ChaosBlast::ChaosBlast()
{
    className="ChaosBlast";
    manaCost=150;
    setAnimation("images/spells/chaosblast/");
}

void ChaosBlast::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    Damage damage;
    damage.setFire(first->getMana()/2);
    damage.setThunder(first->getMana()/2);
    second->hurt(damage);
}
