#ifndef PLAYER_H
#define PLAYER_H

#include "creatures/creature.h"
#include <items/item.h>
#include <queue>

class PlayerStatsView;
class PlayerListView;

class Player : public Creature
{
    Q_OBJECT
    friend class PlayerStatsView;
public:
    Player(std::string name,Json::Value config);
    Player(std::string name);
    Player();
    Player(const Player& player);
    ~Player();

    std::set<Item *> *getLoot();

    virtual void fight(Creature *creature);

    void onMove();
    void onEnter();

    void update();
    void updateViews();

    PlayerListView *getEquippedView();

    void addToFightList(Creature *creature);
    void removeFromFightList(Creature *creature);

    std::list<Creature *> *getFightList();
    void performAction(Interaction *action,Creature *creature);
    void addEntered(MapObject *object);
    std::list<MapObject *> *getEntered();

    void init();
    virtual void setMap(Map *map);
private:
    std::list<Creature *> fightList;

    int turn;
    std::list<MapObject *> entered;
};
Q_DECLARE_METATYPE(Player)

#endif // PLAYER_H
