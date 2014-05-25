#ifndef MONSTER_H
#define MONSTER_H
#include <src/creatures/creature.h>

class Monster : public Creature
{
    Q_OBJECT
public:
    Monster(std::string name, Json::Value config);
    Monster(std::string name);
    Monster();
    Monster(const Monster& monster);
    virtual void onMove();
    virtual void onEnter();
    virtual void levelUp();
    virtual std::set<Item *> *getLoot();
public:
    virtual void loadFromProps(Tmx::PropertySet props);
};
Q_DECLARE_METATYPE(Monster)

#endif // MONSTER_H
