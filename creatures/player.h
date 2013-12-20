#ifndef PLAYER_H
#define PLAYER_H

#include "creatures/creature.h"
#include <items/item.h>
#include <queue>

class PlayerStatsView;
class PlayerListView;

class Player : public Creature
{
    friend class PlayerStatsView;

public:

    Player(std::string name,Json::Value config, Map *map);
    Player(std::string name, Map *map);
    ~Player();

    std::list<Item *>* getLoot();

    virtual void fight(Creature *creature);

    void onMove();
    void onEnter();
    void unLock();
    void doLock();
    bool isLock();

    void update();
    void updateViews();

    PlayerStatsView *getStatsView();
    PlayerListView *getInventoryView();
    PlayerListView *getSkillsView();
    PlayerListView *getEquippedView();

    void addToFightList(Creature *creature);
    void removeFromFightList(Creature *creature);

    std::list<Creature *> *getFightList();
    void *performAction(Interaction *action,Creature *creature);
    void addEntered(MapObject *object);
    std::list<MapObject *> *getEntered();

private:
    PlayerStatsView *playerStatsView;
    PlayerListView *playerInventoryView;
    PlayerListView *playerSkillsView;
    PlayerListView *playerEquippedView;
    bool lock;
    std::list<Creature *> fightList;
    int turn;

    std::list<MapObject *> entered;
};

#endif // PLAYER_H
