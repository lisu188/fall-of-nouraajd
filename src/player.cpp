#include "player.h"
#include <src/gamescene.h>
#include <src/playerstatsview.h>
#include <src/item.h>
#include <src/playerlistview.h>
#include <src/gameview.h>
#include <src/playerlistview.h>
#include <src/stats.h>
#include <src/interaction.h>
#include <math.h>
#include <QDebug>
#include <QBitmap>
#include <QEventLoop>
#include <QApplication>
#include <src/playerlistview.h>

void Player::updateViews()
{
    for (std::set<Item*>::iterator it = inventory.begin(); it != inventory.end(); it++) {
        Item *item = *it;
        if (map && item->getMap() != map) {
            item->setMap(map);
        }
    }
    for (std::set<Interaction*>::iterator it = actions.begin(); it != actions.end(); it++) {
        Interaction *action = *it;
        if (map && action->getMap() != map) {
            action->setMap(map);
        }
    }
    for (std::map<int, Item*>::iterator it = equipped.begin(); it != equipped.end(); it++) {
        Item *item = (*it).second;
        if (map && item && item->getMap() != map) {
            item->setMap(map);
        }
    }
}

void Player::init()
{
    gold = 0;
    turn = 0;
}

void Player::setMap(Map *map)
{
    MapObject::setMap(map);
    updateViews();
}

Player::Player(std::string name)
{
    init();
    this->name="PLAYER";
    this->loadFromJson(name);
}

Player::Player()
{
}

Player::Player(const Player &player)
{
}

Player::~Player()
{
    inventory.clear();
}

std::set<Item *> *Player::getLoot()
{
    return (std::set<Item*>*)&inventory;
}

void Player::onMove()
{
    addMana(manaRegRate);
    turn++;
}

void Player::onEnter()
{
}

void Player::addToFightList(Creature *creature)
{
    fightList.push_back(creature);
}

std::list<Creature *> *Player::getFightList()
{
    return &fightList;
}

void Player::removeFromFightList(Creature *creature)
{
    if (creature == this) {
        return;
    }
    qDebug() << typeName.c_str() << "defeated" << creature->typeName.c_str() << "\n";
    addExpScaled(creature->getScale());
    addItem(creature->getLoot());
    creature->removeFromGame();
    getFightList()->remove(creature);
    if (getFightList()->size() == 0) {
        GameScene::getView()->getFightView()->setVisible(false);
        FightView::selected = 0;
    } else {
        FightView::selected = getFightList()->front();
    }
    GameScene::getView()->getFightView()->update();
    Q_EMIT statsChanged();
}

void Player::performAction(Interaction *action, Creature *creature)
{
    action->onAction(this, creature);
    takeMana(action->getManaCost());
    Armor *armor = creature->getArmor();
    if (armor) {
        Interaction *interaction = armor->getInteraction();
        if (interaction) {
            interaction->onAction(creature, this);
        }
    }
    if (!creature->isAlive()) {
        removeFromFightList(creature);
    } else {
        qDebug() << "";
        std::list<Creature*> tmpList(*getFightList());
        for (std::list<Creature*>::iterator it = tmpList.begin();
             it != tmpList.end(); it++) {
            (*it)->fight(this);
        }
    }
    GameScene::getView()->getFightView()->update();
    if (!isAlive()) {
        GameScene::getView()->close();
    }
}

void Player::addEntered(MapObject *object)
{
    entered.push_back(object);
}

std::list<MapObject *> *Player::getEntered()
{
    return &entered;
}

void Player::fight(Creature *creature)
{
    if (applyEffects()) {
        creature->fight(this);
    }
}





