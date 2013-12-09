#include "spell.h"

#ifndef FROSTBOLT_H
#define FROSTBOLT_H

class FrostBolt : public Spell
{
public:
    FrostBolt();

    // Interaction interface
public:
    void action(Creature *first, Creature *second);

    // Interaction interface
public:
    virtual Interaction *clone();
};

#endif // FROSTBOLT_H
