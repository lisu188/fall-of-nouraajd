#include <creatures/creature.h>

#ifndef MONSTER_H
#define MONSTER_H

class Monster : public Creature
{
public:
    Monster(std::string name,Json::Value config, Map *map);
    Monster(std::string name, Map *map);
    virtual void onMove();
    virtual void onEnter();

    // Creature interface
public:
    virtual void levelUp();

    // Creature interface
public:
    virtual std::list<Item *> *getLoot();
};

#endif // MONSTER_H
