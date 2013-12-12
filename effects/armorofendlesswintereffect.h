#include "effect.h"

#ifndef ARMOROFENDLESSWINTEREFFECT_H
#define ARMOROFENDLESSWINTEREFFECT_H

#include <stats/stats.h>

class ArmorOfEndlessWinterEffect : public Effect
{
public:
    ArmorOfEndlessWinterEffect(Creature *caster, int dur);

    // Effect interface
public:
    virtual bool apply(Creature *creature);
private:
    Stats bonusArmor;
};

#endif // ARMOROFENDLESSWINTEREFFECT_H
