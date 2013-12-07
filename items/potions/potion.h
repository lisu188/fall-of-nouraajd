#include <items/item.h>

#ifndef POTION_H
#define POTION_H

class Potion : public Item
{
public:
    Potion();

    // Item interface
protected:
    virtual void onUse(Creature *creature);
};

#endif // POTION_H
