#include "effect.h"

#include <stats/damage.h>

#ifndef ABYSSALSHADOWSEFFECT_H
#define ABYSSALSHADOWSEFFECT_H

class AbyssalShadowsEffect : public Effect
{
public:
    AbyssalShadowsEffect(Creature *caster,int dur);

    // Effect interface
public:
    virtual bool apply(Creature *creature);

};

#endif // ABYSSALSHADOWSEFFECT_H
