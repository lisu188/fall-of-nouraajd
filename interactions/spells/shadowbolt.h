#include "spell.h"

#ifndef SHADOWBOLT_H
#define SHADOWBOLT_H

class ShadowBolt : public Spell
{
public:
    ShadowBolt();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);
};

#endif // SHADOWBOLT_H
