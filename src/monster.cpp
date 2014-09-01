#include "monster.h"
#include <src/gamescene.h>
#include <src/lootprovider.h>
#include <src/pathfinder.h>
#include <QDebug>
#include "CConfigurationProvider.h"
#include <QThreadPool>

Monster::Monster() : Creature() {}

Monster::Monster ( const Monster &monster ) {}

void Monster::onMove() {
	if ( !isAlive() ) {
		return;
	}
	PathFinder *finder;
	if ( ( this->getCoords().getDist ( this->getMap()->getScene()->getPlayer()->getCoords() ) ) < 25 ) {
		finder = new SmartPathFinder();
	} else {
		finder = new RandomPathFinder();
	}
	this->addExp ( rand() % 25 );
	QThreadPool::globalInstance()->start ( new PathFinderWorker ( this,map->getScene()->getPlayer(), finder ) );
}

void Monster::onEnter() {
	if ( !isAlive() ) {
		return;
	}
	map->getScene()->getPlayer()->addToFightList ( this );
}

void Monster::levelUp() {
	Creature::levelUp();
	heal ( 0 );
	addMana ( 0 );
}

std::set<Item *> *Monster::getLoot() {
	return this->getMap()->getLootProvider()->getLoot ( getScale() );
}
