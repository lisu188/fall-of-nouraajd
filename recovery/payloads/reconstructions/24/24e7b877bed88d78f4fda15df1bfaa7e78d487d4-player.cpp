#include "player.h"
#include <configuration/configurationprovider.h>

#include <map/tile.h>

#include <view/gamescene.h>
#include <view/playerstatsview.h>

#include <view/playerlistview.h>

#include <view/gameview.h>

#include <items/armor.h>
#include <items/weapon.h>
#include <math.h>
#include <stats/stats.h>
#include <view/playerlistview.h>

#include <QDebug>
#include <interactions/interaction.h>
#include <view/fightview.h>

namespace {
struct PlayerLists {
    std::set<ListItem *> inventory;
    std::set<ListItem *> skills;
    std::set<ListItem *> equipped;
};
std::map<Player *, PlayerLists> playerLists;
} // namespace

Player::Player(std::string name, Json::Value config) : Creature(name, config) {
    gold = 0;
    turn = 0;
    playerStatsView = new PlayerStatsView(this);
    playerStatsView->setZValue(3);
    playerInventoryView = new PlayerListView(&playerLists[this].inventory);
    playerInventoryView->setZValue(3);
    playerSkillsView = new PlayerListView(&playerLists[this].skills);
    playerSkillsView->setZValue(3);
    playerEquippedView = new PlayerListView(&playerLists[this].equipped);
    playerEquippedView->setZValue(3);
    updateViews();
}

Player::Player(std::string name) : Player(name, (*ConfigurationProvider::getConfig("config/creatures.json"))[name]) {
    className = name;
}

Player::~Player() {
    playerLists.erase(this);
    inventory.clear();
}

void Player::onMove() {
    addMana(manaRegRate);
    turn++;
    playerStatsView->update();
}

void Player::onEnter() {}

void Player::update() {
    GameView *view = GameScene::getView();
    playerStatsView->setPos(view->mapToScene(0, 0));
    playerInventoryView->setPos(view->mapToScene(0, view->height() - playerInventoryView->boundingRect().height()));
    playerSkillsView->setPos(view->mapToScene(view->width() - playerSkillsView->boundingRect().width(),
                                              view->height() - playerSkillsView->boundingRect().height()));
    playerEquippedView->setPos(view->mapToScene(view->width() - playerEquippedView->boundingRect().width(), 0));
}

PlayerStatsView *Player::getStatsView() { return playerStatsView; }

PlayerListView *Player::getInventoryView() { return playerInventoryView; }

PlayerListView *Player::getEquippedView() { return playerEquippedView; }

PlayerListView *Player::getSkillsView() { return playerSkillsView; }

void Player::addToFightList(Creature *creature) { fightList.push_back(creature); }

void Player::removeFromFightList(Creature *creature) { fightList.remove(creature); }

std::set<Item *> *Player::getLoot() { return &inventory; }

void Player::updateViews() {
    Map *map = getMap();
    if (!map)
        return;
    for (std::set<Item *>::iterator item = inventory.begin(); item != inventory.end(); ++item)
        (*item)->setMap(map);
    for (std::set<Item *>::iterator item = equipped.begin(); item != equipped.end(); ++item)
        (*item)->setMap(map);
    for (std::set<Interaction *>::iterator action = actions.begin(); action != actions.end(); ++action)
        (*action)->setMap(map);
    PlayerLists &lists = playerLists[this];
    lists.inventory.clear();
    lists.skills.clear();
    lists.equipped.clear();
    for (Item *item : inventory)
        lists.inventory.insert(item);
    for (Interaction *action : actions)
        lists.skills.insert(action);
    for (Item *item : equipped)
        lists.equipped.insert(item);
    playerStatsView->update();
    playerInventoryView->update();
    playerSkillsView->update();
    playerEquippedView->update();
}

std::list<Creature *> *Player::getFightList() { return &fightList; }

void *Player::performAction(Interaction *action, Creature *creature) {
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
        qDebug() << className.c_str() << "defeated" << creature->className.c_str() << "\n";
        addExpScaled(creature->getScale());
        addItem(creature->getLoot());
        creature->removeFromGame();
        removeFromFightList(creature);
        if (fightList.size() == 0) {
            GameScene::getView()->getFightView()->setVisible(false);
            FightView::selected = 0;
        } else {
            FightView::selected = fightList.front();
        }
        updateViews();
    } else {
        qDebug() << "";
        for (std::list<Creature *>::iterator it = fightList.begin(); it != fightList.end(); it++) {
            (*it)->fight(this);
        }
    }
    GameScene::getView()->getFightView()->update();
    if (!isAlive()) {
        GameScene::getView()->close();
    }
    return 0;
}

void Player::fight(Creature *creature) {
    if (applyEffects()) {
        creature->fight(this);
    }
}

void Player::addEntered(MapObject *object) { entered.push_back(object); }

std::list<MapObject *> *Player::getEntered() { return &entered; }

void Player::setMap(Map *map) {
    MapObject::setMap(map);
    if (!map || !dynamic_cast<GameScene *>(map->getScene()))
        return;
    map->getScene()->addItem(playerStatsView);
    map->getScene()->addItem(playerInventoryView);
    map->getScene()->addItem(playerSkillsView);
    map->getScene()->addItem(playerEquippedView);
    updateViews();
}
