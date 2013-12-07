#include <creatures/creature.h>

#ifndef MONSTER_H
#define MONSTER_H

class Monster : public Creature
{
public:
    Monster(Map* map, int x, int y);
    virtual void onMove();
    virtual void onEnter();
};

#endif // MONSTER_H
