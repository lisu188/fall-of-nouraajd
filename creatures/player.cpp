#include "player.h"

#include <view/gamescene.h>
#include <view/playerstatsview.h>

#include <items/weapon.h>
#include <items/armor.h>

#include <view/playerlistview.h>

#include <view/gameview.h>

#include <view/playerlistview.h>
#include <stats/stats.h>
#include <math.h>

#include <QDebug>
#include <QBitmap>
#include <QEventLoop>
#include <QApplication>
#include <view/playerlistview.h>

void Player::updateViews() {
	for (std::set<Item*>::iterator it = inventory.begin();
			it != inventory.end(); it++) {
		Item *item = *it;
		if (map && item->getMap() != map) {
			item->setMap(map);
		}
	}
	for (std::set<Interaction*>::iterator it = actions.begin();
			it != actions.end(); it++) {
		Interaction *action = *it;
		if (map && action->getMap() != map) {
			action->setMap(map);
		}
	}
	for (std::map<int, Item*>::iterator it = equipped.begin();
			it != equipped.end(); it++) {
		Item *item = (*it).second;
		if (map && item && item->getMap() != map) {
			item->setMap(map);
		}
	}
}

Player::Player(std::string name, Json::Value config)
		: Creature(name, config) {
	init();
}

void Player::init() {
	gold = 0;
	turn = 0;
}

void Player::setMap(Map *map) {
	MapObject::setMap(map);
	updateViews();
}
bool Player::getCanMove() const {
	return canMove;
}

void Player::setCanMove(bool value) {
	canMove = value;
}

bool Player::event(QEvent *event) {
	if (event->type() == QEvent::User) {
		QApplication::instance()->processEvents(
				QEventLoop::ExcludeUserInputEvents);
		this->setCanMove(true);
		return true;
	}
	return false;
}

Player::Player(std::string name)
		: Creature(name) {
	init();
}

Player::Player() {
}

Player::Player(const Player &player)
		: Player(player.className) {
}

Player::~Player() {
	inventory.clear();
}

std::set<Item *> *Player::getLoot() {
	return (std::set<Item*>*) &inventory;
}

void Player::onMove() {
	addMana(manaRegRate);
	turn++;
}

void Player::onEnter() {
}

void Player::addToFightList(Creature *creature) {
	fightList.push_back(creature);
}

std::list<Creature *> *Player::getFightList() {
	return &fightList;
}

void Player::removeFromFightList(Creature *creature) {
	if (creature == this) {
		return;
	}
	qDebug() << className.c_str() << "defeated" << creature->className.c_str()
			<< "\n";
	addExpScaled(creature->getScale());
	addItem(creature->getLoot());
	creature->removeFromGame();
	getFightList()->remove(creature);
	if (getFightList()->size() == 0) {
		GameScene::getView()->getFightView()->setVisible(false);
		FightView::selected = 0;
	}
	else {
		FightView::selected = getFightList()->front();
	}
	GameScene::getView()->getFightView()->update();
	emit statsChanged();
}

void Player::performAction(Interaction *action, Creature *creature) {
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
	}
	else {
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

void Player::addEntered(MapObject *object) {
	entered.push_back(object);
}

std::list<MapObject *> *Player::getEntered() {
	return &entered;
}

void Player::fight(Creature *creature) {
	if (applyEffects()) {
		creature->fight(this);
	}
}

