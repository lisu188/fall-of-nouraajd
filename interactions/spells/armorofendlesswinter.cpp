#include "armorofendlesswinter.h"

#include <effects/armorofendlesswintereffect.h>

#include <creatures/creature.h>

ArmorOfEndlessWinter::ArmorOfEndlessWinter()
{
    className="ArmorOfEndlessWinter";
    manaCost=60;
    setAnimation("images/spells/armorofendlesswinter/");
}


void ArmorOfEndlessWinter::action(Creature *first, Creature *second)
{
    first->addEffect(new ArmorOfEndlessWinterEffect(first,3));
}
