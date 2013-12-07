#include "potion.h"

#ifndef LIFEPOTION_H
#define LIFEPOTION_H

class LifePotion : public Potion
{
public:
    LifePotion();

protected:
    virtual void onUse(Creature *creature);
};

#endif // LIFEPOTION_H
