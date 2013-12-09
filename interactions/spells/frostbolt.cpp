#include "frostbolt.h"

#include <interactions/attacks/attack.h>

FrostBolt::FrostBolt()
{
    className="FrostBolt";
    manaCost=20;
    setAnimation("images/spells/frostbolt/");
}

void FrostBolt::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    Attack attack;
    attack.action(first,second);
    Damage damage;
    damage.setFrost(first->getStats()->getIntelligence()*75.0/100.0);
    second->hurt(damage);
    //change to ice
}

Interaction *FrostBolt::clone()
{
    return new FrostBolt();
}
