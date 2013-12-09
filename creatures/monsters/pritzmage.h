#include "monster.h"

#ifndef PRITZMAGE_H
#define PRITZMAGE_H

class PritzMage : public Monster
{
public:
    PritzMage(Map* map, int x, int y);

    // Creature interface
public:
    virtual void levelUp();
};

#endif // PRITZMAGE_H
