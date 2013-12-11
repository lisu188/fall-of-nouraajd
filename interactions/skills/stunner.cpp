#include "stunner.h"

#include <effects/stun.h>
#include <creatures/creature.h>

Stunner::Stunner()
{
    className="Stunner";
    manaCost=40;
    setAnimation("images/skills/stun/");
}

void Stunner::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    second->addEffect(new Stun(rand()%1+3));
}

Interaction *Stunner::clone()
{
    return new Stunner();
}
