#include "spell.h"

#ifndef ARMOROFENDLESSWINTER_H
#define ARMOROFENDLESSWINTER_H

class ArmorOfEndlessWinter : public Spell
{
public:
    ArmorOfEndlessWinter();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);
};

#endif // ARMOROFENDLESSWINTER_H
