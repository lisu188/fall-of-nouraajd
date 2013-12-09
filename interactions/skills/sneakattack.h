#include "skill.h"

#ifndef SNEAKATTACK_H
#define SNEAKATTACK_H

class SneakAttack : public Skill
{
public:
    SneakAttack();

    // Interaction interface
public:
    virtual void action(Creature *first, Creature *second);
};

#endif // SNEAKATTACK_H
