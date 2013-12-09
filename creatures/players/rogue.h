#include "player.h"

#ifndef ROGUE_H
#define ROGUE_H

class Assasin : public Player
{
public:
    Assasin(Map* map,int x,int y);

protected:
    void levelUp();
};

#endif // ROGUE_H
