#include "player.h"

#ifndef MAGE_H
#define MAGE_H

class Mage : public Player
{
public:
    Mage(Map *map, int x, int y);

protected:
    void levelUp();
};

#endif // MAGE_H
