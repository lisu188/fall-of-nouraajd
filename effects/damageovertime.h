#include "effect.h"

#include <stats/damage.h>

#ifndef DAMAGEOVERTIME_H
#define DAMAGEOVERTIME_H

class DamageOverTime : public Effect
{
public:
    DamageOverTime(int duration,Damage dmg);

    // Effect interface
public:
    virtual bool apply(Creature *creature);
private:
    Damage damage;
};

#endif // DAMAGEOVERTIME_H
