#include "spell.h"

#ifndef CHAOSBLAST_H
#define CHAOSBLAST_H

class ChaosBlast : public Spell
{
public:
    ChaosBlast();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);

    // Interaction interface
public:
    virtual Interaction *clone();
};

#endif // CHAOSBLAST_H
