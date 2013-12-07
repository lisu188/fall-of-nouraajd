#include "stun.h"

Stun::Stun()
{
    className="Stun";
    manaCost=40;
    setAnimation("images/skills/stun/");
}

void Stun::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    second->addStun(rand()%1+3);
}
