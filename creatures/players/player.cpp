#include "player.h"

#include <map/tiles/tile.h>

#include <view/gamescene.h>
#include <view/playerstatsview.h>

#include <items/potions/blesspotion.h>
#include <items/potions/lifepotion.h>
#include <items/potions/manapotion.h>
#include <items/potions/poisonpotion.h>

#include <view/playerlistview.h>

#include <view/gameview.h>

#include <items/weapons/swords/chaossword.h>
#include <items/weapons/swords/sword.h>

#include <items/armors/platearmor.h>
#include <view/playerlistview.h>
#include <stats/stats.h>
#include <math.h>

Player::Player(Map *map, int x, int y):Creature(map,x,y)
{
    className="Player";
    lock=false;
    level=0;

    gold=0;
    sw=0;
    turn=0;

    inventory=new std::list<Item*>();

    playerStatsView=new PlayerStatsView(this);
    playerStatsView->setZValue(3);

    playerInventoryView=new PlayerListView((std::list<ListItem*>*)inventory);
    playerInventoryView->setZValue(3);

    playerSkillsView=new PlayerListView((std::list<ListItem*>*)actions);
    playerSkillsView->setZValue(3);

    GameScene::getGame()->addItem(playerStatsView);
    GameScene::getGame()->addItem(playerInventoryView);
    GameScene::getGame()->addItem(playerSkillsView);


    std::list<Item *> list;
    list.push_back(new LifePotion());
    list.push_back(new ManaPotion());
    list.push_back(new BlessPotion());
    list.push_back(new PoisonPotion());
    addItem(&list);
}

Player::~Player()
{
    inventory->clear();
    delete inventory;
}

void Player::onMove()
{
    addMana(manaRegRate);
    turn++;
    playerStatsView->update();
}

void Player::onEnter()
{

}

void Player::addItem(Item *item)
{
    std::list<Item *> list;
    list.push_back(item);
    addItem(&list);
}

void Player::addItem(std::list<Item*> *items)
{
    inventory->merge(*items);
    playerInventoryView->update();
}

void Player::loseItem(Item *item)
{
    inventory->remove(item);
    playerInventoryView->update();
}

void Player::update()
{
    GameView *view=GameScene::getView();
    playerStatsView->setPos(view->mapToScene(0,0));
    playerInventoryView->setPos(view->mapToScene(0,
                                view->height()-playerInventoryView->boundingRect().height()));
    playerSkillsView->setPos(view->mapToScene(
                                 view->width()-playerSkillsView->boundingRect().width(),
                                 view->height()-playerSkillsView->boundingRect().height()));
    if(weapon)
    {
        weapon->setPos(view->mapToScene(view->width()-Tile::size,0));
    }
    if(armor)
    {
        armor->setPos(view->mapToScene(view->width()-Tile::size,Tile::size));
    }
}

std::list<Item *> *Player::getInventory()
{
    return inventory;
}

PlayerStatsView *Player::getStatsView() {
    return playerStatsView;
}

PlayerListView *Player::getInventoryView() {
    return playerInventoryView;
}

PlayerListView *Player::getSkillsView()
{
    return playerSkillsView;
}

void Player::addToFightList(Creature *creature)
{
    fightList.push_back(creature);
}



void Player::fight(Creature *creature)
{
    if(isStun())creature->fight(this);
}
