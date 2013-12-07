#include "monster.h"

#include <items/potions/lifepotion.h>

#ifndef DOGE_H
#define DOGE_H

class Pritz : public Monster
{
public:
    Pritz(Map* map, int x, int y);
    int getExp() {
        return 800;
    }
    std::list<Item*> *getLoot();
    virtual void onMove();
    virtual void levelUp();

};

#endif // DOGE_H
