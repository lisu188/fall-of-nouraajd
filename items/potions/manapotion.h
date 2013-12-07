#include "potion.h"

#ifndef MANAPOTION_H
#define MANAPOTION_H

class ManaPotion : public Potion
{
public:
    ManaPotion();
protected:
    virtual void onUse(Creature *creature);
};

#endif // MANAPOTION_H
