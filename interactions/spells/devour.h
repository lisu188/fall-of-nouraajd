#include "spell.h"

#ifndef DEVOUR_H
#define DEVOUR_H

class Devour : public Spell
{
public:
    Devour();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);
};

#endif // DEVOUR_H
