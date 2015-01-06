#include "CMonster.h"
#include "CMap.h"
#include "CPathFinder.h"

void CMonster::levelUp() {
	CCreature::levelUp();
	heal ( 0 );
	addMana ( 0 );
}

std::set<CItem *> CMonster::getLoot() {
	return this->getMap()->getLootHandler()->getLoot ( getScale() );
}

Coords CMonster::getNextMove() {
	if ( this->getCoords().getDist ( this->getMap()->getPlayer()->getCoords() ) <25 ) {
		return CSmartPathFinder().findPath ( this,this->getMap()->getPlayer() );
	} else {
		return CRandomPathFinder().findPath ( this,this->getMap()->getPlayer() );
	}
}

CMonster::CMonster() {

}

CMonster::~CMonster() {

}

void CMonster::onTurn ( CGameEvent * ) {
	this->addExp ( rand() % 25 );
}
