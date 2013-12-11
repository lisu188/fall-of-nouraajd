#include "devour.h"

#include <creatures/creature.h>

Devour::Devour()
{
    className="Devour";
    manaCost=75;
    setAnimation("images/spells/devour/");
}

void Devour::action(Creature *first, Creature *second)
{
    int crit=first->getStats()->getCrit();
    first->getStats()->setCrit(0);
    int dmg=first->getDmg();
    if(dmg)
    {
        second->hurt(dmg);
        first->heal(dmg*0.75);
    }
    first->getStats()->setCrit(crit);
}
