#include <interactions/interaction.h>

#ifndef ELEMSTAFF_H
#define ELEMSTAFF_H

class ElemStaff : public Interaction
{
public:
    virtual void action(Creature *first, Creature *second);
    ElemStaff();

    // Interaction interface
public:
    virtual Interaction *clone();
};

#endif // ELEMSTAFF_H
