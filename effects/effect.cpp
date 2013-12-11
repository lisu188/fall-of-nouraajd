#include "effect.h"
#include <QDebug>
#include <creatures/creature.h>

Effect::Effect(Creature *caster, int duration):dur(duration),caster(caster)
{
    className="Effect";
}

int Effect::getDuration() {
    return dur;
}

bool Effect::apply(Creature *creature)
{
    dur--;
    if(dur==0)
    {
        return false;
    }
    return true;
}
