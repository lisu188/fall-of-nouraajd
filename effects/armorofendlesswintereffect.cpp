#include "armorofendlesswintereffect.h"

#include <creatures/creature.h>


ArmorOfEndlessWinterEffect::ArmorOfEndlessWinterEffect(Creature *caster, int dur):Effect(caster,dur)
{
    className="ArmorOfEndlessWinterEffect";
    bonusArmor.setArmor(caster->getStats()->getArmor()*0.75);
}


bool ArmorOfEndlessWinterEffect::apply(Creature *creature)
{
    if(dur==1) {
        creature->getStats()->removeBonus(bonusArmor);
    }
    creature->healProc(20);
    return false&&Effect::apply(creature);//must implement ban to other skills
}
