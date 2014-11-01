#include "CPlayer.h"
#include "CMap.h"
#include "panel/CPanel.h"
#include <QApplication>

CPlayer::CPlayer() {

}

CPlayer::CPlayer ( const CPlayer & ) {

}

CPlayer::~CPlayer() {
	inventory.clear();
}

void CPlayer::onTurn ( CGameEvent * ) {
	addMana ( manaRegRate );
	turn++;
}

void CPlayer::onDestroy ( CGameEvent * ) {
	CMap* map=getMap();
	map->addObject ( this );
	moveTo ( map->getEntryX(),map->getEntryY(),map->getEntryZ() );
	this->hp=1;
}

CInteraction *CPlayer::selectAction() {
	while ( this->getSelectedAction() ==0 ) {
		QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
	}
	CInteraction* action=this->getSelectedAction();
	this->setSelectedAction ( nullptr );
	return action;
}

void CPlayer::fight ( CCreature *creature ) {
	setEnemy ( creature );
	getMap()->getGuiHandler()->getPanel ( "CFightPanel" )->showPanel();
	CCreature::fight ( creature );
	getMap()->getGuiHandler()->getPanel ( "CFightPanel" )->hidePanel();
	setEnemy ( nullptr );
}

Coords CPlayer::getNextMove() {
	return next;
}

void CPlayer::setSelectedAction ( CInteraction *value ) {
	selectedAction = value;
}

CCreature *CPlayer::getEnemy() const {
	return enemy;
}

void CPlayer::setEnemy ( CCreature *value ) {
	enemy = value;
}

void CPlayer::setNextMove ( Coords coords ) {
	this->next=coords;
}

CInteraction *CPlayer::getSelectedAction() const {
	return selectedAction;
}
