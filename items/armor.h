#include <items/item.h>

#include <interactions/interaction.h>

#ifndef ARMOR_H
#define ARMOR_H

class Armor : public Item
{
public:
    Armor(std::string name);
    Interaction *getInteraction();

protected:
    virtual void onUse(Creature *creature);
};

#endif // ARMOR_H
