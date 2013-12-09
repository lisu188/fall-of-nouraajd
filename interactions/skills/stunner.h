#include "skill.h"

#ifndef STUNNER_H
#define STUNNER_H

class Stunner : public Skill
{
public:
    Stunner();

    // Interaction interface
public:
    void action(Creature *first, Creature *second);
};

#endif // STUNNER_H
