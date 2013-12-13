#include "player.h"

#include <map/tiles/tile.h>

#include <view/gamescene.h>
#include <view/playerstatsview.h>


#include <view/playerlistview.h>

#include <view/gameview.h>


#include <items/armor.h>
#include <items/weapon.h>
#include <view/playerlistview.h>
#include <stats/stats.h>
#include <math.h>

#include <interactions/interaction.h>
#include <view/fightview.h>
#include <QDebug>

Player::Player(char *path,Map *map, int x, int y):Creature(path,map,x,y)
{
    lock=false;
    gold=0;
    turn=0;
    playerStatsView=new PlayerStatsView(this);
    playerStatsView->setZValue(3);
    playerInventoryView=new PlayerListView((std::list<ListItem*>*)&inventory);
    playerInventoryView->setZValue(3);
    playerSkillsView=new PlayerListView((std::list<ListItem*>*)&actions);
    playerSkillsView->setZValue(3);
    GameScene::getGame()->addItem(playerStatsView);
    GameScene::getGame()->addItem(playerInventoryView);
    GameScene::getGame()->addItem(playerSkillsView);
    updateViews();
}

Player::~Player()
{
    inventory.clear();
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

void Player::removeFromFightList(Creature *creature)
{
    fightList.remove(creature);
}

std::list<Item *> *Player::getLoot()
{
    return &inventory;
}

void Player::updateViews()
{
    playerStatsView->update();
    playerInventoryView->update();
    playerSkillsView->update();
}

std::list<Creature *> *Player::getFightList() {
    return &fightList;
}

void Player::unLock()
{
    lock=false;
}

void Player::doLock()
{
    lock=true;
}

bool Player::isLock()
{
    return lock;
}

void *Player::performAction(Interaction *action, Creature *creature)
{
    action->onAction(this,creature);
    takeMana(action->getManaCost());
    Armor *armor=creature->getArmor();
    if(armor) {
        Interaction *interaction=armor->getInteraction();
        if(interaction) {
            interaction->onAction(creature,this);
        }
    }
    if(!creature->isAlive()) {
        qDebug()<<className.c_str()<<"defeated"<<creature->className.c_str()<<"\n";
        addExpScaled(creature->getScale());
        addItem(creature->getLoot());
        creature->removeFromGame();
        removeFromFightList(creature);
        if(fightList.size()==0) {
            GameScene::getView()->getFightView()->setVisible(false);
            FightView::selected=0;
        } else {
            FightView::selected=fightList.front();
        }
        updateViews();
    } else {
        qDebug()<<"";
        for(std::list<Creature*>::iterator it=fightList.begin(); it!=fightList.end(); it++) {
            (*it)->fight(this);
        }
    }
    GameScene::getView()->getFightView()->update();
    if(!isAlive()) {
        GameScene::getView()->close();
    }
    return 0;
}




void Player::fight(Creature *creature)
{
    if(applyEffects()) {
        creature->fight(this);
    }
}
