#include "effect.h"

#ifndef ENDLESSPAINEFFECT_H
#define ENDLESSPAINEFFECT_H
class Damage;
class EndlessPainEffect : public Effect
{
public:
    EndlessPainEffect(Creature*caster,int duration);

    // Effect interface
public:
    virtual bool apply(Creature * creature);
};

#endif // ENDLESSPAINEFFECT_H
