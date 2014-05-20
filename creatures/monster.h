#ifndef MONSTER_H
#define MONSTER_H
#include <creatures/creature.h>
#include <future>

class Monster : public Creature
{
    Q_OBJECT
public:
    Monster(std::string name,Json::Value config);
    Monster(std::string name);
    Monster();
    Monster(const Monster& monster);
    virtual void onMove();
    virtual void onEnter();
    virtual void levelUp();
    virtual std::set<Item *> *getLoot();
};
Q_DECLARE_METATYPE(Monster)

#endif // MONSTER_H
