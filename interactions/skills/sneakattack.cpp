#include "sneakattack.h"

#include <interactions/attacks/attack.h>

#include <creatures/players/player.h>

SneakAttack::SneakAttack()
{
    className="SneakAttack";
    manaCost=15;
    setAnimation("images/skills/sneakattack/");
}

void SneakAttack::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    Attack attack;
    attack.action(first,second);

    if(rand()%100>(100-second->getHpRatio()))
    {
        if(second->isAlive())
            attack.action(first,second);
    }
}
