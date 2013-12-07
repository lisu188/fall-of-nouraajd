#include "pritz.h"

#include <creatures/players/mage.h>

#ifndef PRITZMAGE_H
#define PRITZMAGE_H

class PritzMage : public Pritz
{
public:
    PritzMage(Map* map, int x, int y);

    // Creature interface
public:
    virtual void levelUp();
};

#endif // PRITZMAGE_H
