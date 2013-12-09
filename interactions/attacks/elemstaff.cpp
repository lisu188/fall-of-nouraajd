#include "elemstaff.h"

ElemStaff::ElemStaff()
{
    className="ElemStaff";
}

Interaction *ElemStaff::clone()
{
    return new ElemStaff();
}

void ElemStaff::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    Damage damage;
    damage.setFire(1);
    damage.setFrost(1);
    damage.setThunder(1);
    second->hurt(damage);
}
