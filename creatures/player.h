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

    Player(char *path, Map *map, int x, int y);
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

    void addToFightList(Creature *creature);
    void removeFromFightList(Creature *creature);

    std::list<Creature *> *getFightList();
    void *performAction(Interaction *action,Creature *creature);

private:
    PlayerStatsView *playerStatsView;
    PlayerListView *playerInventoryView;
    PlayerListView *playerSkillsView;
    bool lock;
    std::list<Creature *> fightList;
    int turn;
};

#endif // PLAYER_H
