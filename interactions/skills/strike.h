#include "skill.h"

#ifndef STRIKE_H
#define STRIKE_H

class Strike : public Skill
{
public:
    Strike();

    // Interaction interface
public:
    void action(Creature *first, Creature *second);
};

#endif // STRIKE_H
