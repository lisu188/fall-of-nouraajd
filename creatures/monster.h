#include <creatures/creature.h>

#ifndef MONSTER_H
#define MONSTER_H

class Monster : public Creature
{
    Q_OBJECT
public:
    Monster(std::string name,Json::Value config);
    Monster(std::string name);
    virtual void onMove();
    virtual void onEnter();

    // Creature interface
public:
    virtual void levelUp();

    // Creature interface
public:
    virtual std::set<Item *> *getLoot();
};

#endif // MONSTER_H
