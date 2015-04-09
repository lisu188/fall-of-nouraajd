#include "CMonster.h"
#include "CMap.h"
#include "CPathFinder.h"

void CMonster::levelUp() {
	CCreature::levelUp();
	heal ( 0 );
	addMana ( 0 );
}

Coords CMonster::getNextMove() {
	return CSmartPathFinder::findNextStep ( this->getCoords(),this->getMap()->getPlayer() ?this->getMap()->getPlayer()->getCoords() :this->getCoords(),[this] ( const Coords& coords ) {
		return this->getMap()->canStep ( coords );
	} )-this->getCoords();
}

CMonster::CMonster() {

}

CMonster::~CMonster() {

}

void CMonster::onTurn ( CGameEvent * ) {
	this->addExp ( rand() % 25 );
}
