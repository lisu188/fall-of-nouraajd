#include <items/item.h>

#include <interactions/interaction.h>

#ifndef ARMOR_H
#define ARMOR_H

class Armor : public Item
{
public:
    Armor();
    Interaction *getInteraction() {
        return interaction;
    }

protected:
    virtual void onUse(Creature *creature);
};

#endif // ARMOR_H
