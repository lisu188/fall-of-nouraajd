#include <interactions/interaction.h>

#ifndef ATTACK_H
#define ATTACK_H

class Attack : public Interaction
{
public:
    Attack();

public:
    virtual void action(Creature *first, Creature *second);

    // Interaction interface
public:
    virtual Interaction *clone();
};

#endif // ATTACK_H
