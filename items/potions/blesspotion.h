#include "potion.h"

#ifndef BLESSPOTION_H
#define BLESSPOTION_H

class BlessPotion : public Potion
{
public:
    BlessPotion();

    // Item interface
protected:
    virtual void onUse(Creature *creature);
};

#endif // BLESSPOTION_H
