#include <items/item.h>

#include <interactions/interaction.h>

#ifndef ARMOR_H
#define ARMOR_H

class Armor : public Item
{
public:
    Armor(const char *path);
    Interaction *getInteraction();

protected:
    virtual void onUse(Creature *creature);
};

#endif // ARMOR_H
