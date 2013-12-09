#include "spell.h"

#ifndef MAGICMISSILE_H
#define MAGICMISSILE_H

class MagicMissile : public Spell
{
public:
    MagicMissile();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);

    // Interaction interface
public:
    virtual Interaction *clone();
};

#endif // MAGICMISSILE_H
