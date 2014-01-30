#include <items/item.h>

#include <interactions/interaction.h>

#ifndef WEAPON_H
#define WEAPON_H

class Weapon : public Item
{
    Q_OBJECT
public:
    Weapon();
    void init(std::string name);
    Weapon(const Weapon &weapon);
    Interaction *getInteraction();
    Stats *getStats();
};
Q_DECLARE_METATYPE(Weapon)

#endif // WEAPON_H
