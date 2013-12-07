#include "chaossword.h"

#include <interactions/spells/chaosblast.h>

ChaosSword::ChaosSword()
{
    className="ChaosSword";
    bonus->setDamage(25);
    bonus->setAttack(15);

    setAnimation("images/items/weapons/chaossword/");
    interaction=new ChaosBlast();
}
