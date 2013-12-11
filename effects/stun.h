#include "effect.h"

#ifndef STUN_H
#define STUN_H

class Stun : public Effect
{
public:
    Stun(Creature *caster,int duration);

    // Effect interface
public:
    virtual bool apply(Creature *creature);
};

#endif // STUN_H
