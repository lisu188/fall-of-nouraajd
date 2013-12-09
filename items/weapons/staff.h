#include "weapon.h"

#ifndef STAFF_H
#define STAFF_H

class Staff : public Weapon
{
public:
    Staff();
};

class ElemStaff : public Interaction
{
public:
    virtual void action(Creature *first, Creature *second);
    ElemStaff();
};

#endif // STAFF_H
