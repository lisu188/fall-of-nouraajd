#include "doubleattack.h"

#include <interactions/attacks/attack.h>

DoubleAttack::DoubleAttack()
{
    className="DoubleAttack";
    manaCost=50;
    setAnimation("images/skills/doubleattack/");
}

void DoubleAttack::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    Attack attack;
    attack.action(first,second);
    attack.action(first,second);
}
