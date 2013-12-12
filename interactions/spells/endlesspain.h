#include "spell.h"

#ifndef ENDLESSPAIN_H
#define ENDLESSPAIN_H

class EndlessPain : public Spell
{
public:
    EndlessPain();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);
};

#endif // ENDLESSPAIN_H
