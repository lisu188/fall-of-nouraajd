#include "potion.h"

#ifndef POISONPOTION_H
#define POISONPOTION_H

class PoisonPotion : public Potion
{
public:
    PoisonPotion();

    // Item interface
protected:
    virtual void onUse(Creature *creature);
};

#endif // POISONPOTION_H
