#include <items/item.h>

#include <interactions/interaction.h>

#ifndef WEAPON_H
#define WEAPON_H

class Weapon : public Item
{
public:
    Weapon();
    Interaction *getInteraction() {
        return interaction;
    }
protected:
    Interaction *interaction;

    // Item interface
protected:
    virtual void onUse(Creature *creature);
};

#endif // WEAPON_H
