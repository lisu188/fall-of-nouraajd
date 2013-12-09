#include "damage.h"

Damage::Damage()
{
}
int Damage::getFire() const
{
    return fire;
}

void Damage::setFire(int value)
{
    fire = value;
}
int Damage::getThunder() const
{
    return thunder;
}

void Damage::setThunder(int value)
{
    thunder = value;
}
int Damage::getFrost() const
{
    return frost;
}

void Damage::setFrost(int value)
{
    frost = value;
}
int Damage::getNormal() const
{
    return normal;
}

void Damage::setNormal(int value)
{
    normal = value;
}




