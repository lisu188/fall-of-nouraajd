#include "skill.h"

#ifndef STUN_H
#define STUN_H

class Stun : public Skill
{
public:
    Stun();

    // Interaction interface
public:
    void action(Creature *first, Creature *second);
};

#endif // STUN_H
