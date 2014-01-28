#include "weapon.h"

#ifndef SMALLWEAPON_H
#define SMALLWEAPON_H

class SmallWeapon : public Weapon
{
public:
    SmallWeapon();
    SmallWeapon(const SmallWeapon &weapon);
};
Q_DECLARE_METATYPE(SmallWeapon)
#endif // SMALLWEAPON_H
