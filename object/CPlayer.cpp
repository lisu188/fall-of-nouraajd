#include "CPlayer.h"
#include "CMap.h"
#include "panel/CPanel.h"
#include <QApplication>
#include <QDebug>

CPlayer::CPlayer() {

}

CPlayer::~CPlayer() {
	inventory.clear();
}

void CPlayer::onTurn ( CGameEvent * ) {
	addMana ( manaRegRate );
	turn++;
	checkQuests();
}

void CPlayer::checkQuests() {
	std::set<CQuest*> set=quests;
	for ( CQuest *quest:set ) {
		if ( quest->isCompleted() ) {
			quest->onComplete();
			quests.erase ( quests.find ( quest ) );
		}
	}
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

void CPlayer::trade ( CGameObject *object ) {
	if ( CMarket * market=dynamic_cast<CMarket*> ( object ) ) {
		setMarket ( market );
		AGamePanel*panel=getMap()->getGuiHandler()->getPanel ( "CTradePanel" );
		panel->showPanel();
		while ( panel->isVisible() ) {
			QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
		}
		setMarket ( nullptr );
	} else {
		qFatal ( "Called trade with not a CMarket" );
	}
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

CMarket *CPlayer::getMarket() const {
	return market;
}

void CPlayer::setMarket ( CMarket *value ) {
	market = value;
}

void CPlayer::addQuest ( QString questName ) {
	CQuest *quest=getMap()->getObjectHandler()->createObject<CQuest*> ( questName );
	if ( quest ) {
		quests.insert ( quest );
	}
}

void CPlayer::setNextMove ( Coords coords ) {
	this->next=coords;
}

CInteraction *CPlayer::getSelectedAction() const {
	return selectedAction;
}
