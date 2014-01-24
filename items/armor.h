#include <items/item.h>

#include <interactions/interaction.h>

#ifndef ARMOR_H
#define ARMOR_H

class Armor : public Item
{
    Q_OBJECT
public:
    Armor();
    Armor(const Armor &armor);
    Armor(std::string name);
    Interaction *getInteraction();
    virtual void onUse(Creature *creature);
};
Q_DECLARE_METATYPE(Armor)

#endif // ARMOR_H
