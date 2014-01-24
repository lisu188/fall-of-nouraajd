#include <items/item.h>

#include <interactions/interaction.h>

#ifndef WEAPON_H
#define WEAPON_H

class Weapon : public Item
{
    Q_OBJECT
public:
    Weapon();
    Weapon(std::string name);
    Weapon(const Weapon &weapon);
    Interaction *getInteraction();
    Stats *getStats();
    virtual void onUse(Creature *creature);
};
Q_DECLARE_METATYPE(Weapon)

#endif // WEAPON_H
