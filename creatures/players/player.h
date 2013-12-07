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

    Player(Map *map,int x,int y);
    ~Player();

    std::list<Item *>* getLoot() {
        return inventory;
    }

    virtual void fight(Creature *creature);

    void onMove();
    void onEnter();
    void unLock() {
        lock=false;
    }
    void doLock() {
        lock=true;
    }
    bool isLock() {
        return lock;
    }


    void addItem(std::list<Item *> *items);

    void addItem(Item *item);
    void loseItem(Item *item);

    void update();

    std::list<Item*> *getInventory();

    PlayerStatsView *getStatsView();
    PlayerListView *getInventoryView();
    PlayerListView *getSkillsView();

    void addToFightList(Creature *creature);
    std::list<Creature *> *getFightList() {
        return &fightList;
    }

protected:


    int gold;

    std::list<Item*> *inventory;
private:

    PlayerStatsView *playerStatsView;
    PlayerListView *playerInventoryView;
    PlayerListView *playerSkillsView;
    bool lock;
    std::list<Creature *> fightList;
    int turn;
};

#endif // PLAYER_H
