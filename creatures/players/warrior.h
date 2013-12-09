#include "player.h"

#ifndef WARRIOR_H
#define WARRIOR_H

class Warrior : public Player
{
public:
    Warrior(Map *map, int x, int y);
};

#endif // WARRIOR_H
