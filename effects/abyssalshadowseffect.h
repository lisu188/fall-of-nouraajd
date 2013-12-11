#include "effect.h"

#include <stats/damage.h>

#ifndef ABYSSALSHADOWSEFFECT_H
#define ABYSSALSHADOWSEFFECT_H

class AbyssalShadowsEffect : public Effect
{
public:
    AbyssalShadowsEffect(int dur,Damage *dmg);

    // Effect interface
public:
    virtual bool apply(Creature *creature);
private:
    Damage *damage;

};

#endif // ABYSSALSHADOWSEFFECT_H
