#include "endlesspain.h"

#include <stats/damage.h>
#include <effects/endlesspaineffect.h>
#include <items/weapons/weapon.h>
#include <creatures/creature.h>

EndlessPain::EndlessPain()
{
    className="EndlessPain";
    manaCost=25;
    setAnimation("images/spells/endlesspain/");
}

void EndlessPain::action(Creature *first, Creature *second)
{
    second->addEffect(new EndlessPainEffect(first,2));
}
