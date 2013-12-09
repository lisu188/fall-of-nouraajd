#include "spell.h"

#ifndef ABYSSALSHADOWS_H
#define ABYSSALSHADOWS_H

class AbyssalShadows : public Spell
{
public:
    AbyssalShadows();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);
};

#endif // ABYSSALSHADOWS_H
