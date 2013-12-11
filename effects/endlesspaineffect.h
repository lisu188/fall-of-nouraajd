#include "effect.h"

#ifndef ENDLESSPAINEFFECT_H
#define ENDLESSPAINEFFECT_H
class Damage;
class EndlessPainEffect : public Effect
{
public:
    EndlessPainEffect(int duration,Damage *dmg);

    // Effect interface
public:
    virtual bool apply(Creature *creature);
private:
    Damage *damage;
};

#endif // ENDLESSPAINEFFECT_H
