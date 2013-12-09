#include "player.h"

#ifndef ROGUE_H
#define ROGUE_H

class Rogue : public Player
{
public:
    Rogue(Map* map,int x,int y);

protected:
    void levelUp();
};

#endif // ROGUE_H
