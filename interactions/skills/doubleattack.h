#include "skill.h"

#ifndef DOUBLEATTACK_H
#define DOUBLEATTACK_H

class DoubleAttack : public Skill
{
public:
    DoubleAttack();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);

    // Interaction interface
public:
    virtual Interaction *clone();
};

#endif // DOUBLEATTACK_H
