#include <items/item.h>

#include <interactions/interaction.h>

#ifndef WEAPON_H
#define WEAPON_H

class Weapon : public Item
{
public:
    Weapon(std::string name);
    Interaction *getInteraction();
    Stats *getStats();
    virtual void onUse(Creature *creature);
};

#endif // WEAPON_H
