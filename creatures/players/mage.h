#include "player.h"

#ifndef MAGE_H
#define MAGE_H

class Sorcerer : public Player
{
public:
    Sorcerer(Map *map, int x, int y);

protected:
    void levelUp();
};

#endif // MAGE_H
