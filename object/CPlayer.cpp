#include "CPlayer.h"
#include "CMap.h"
#include "CGame.h"

#include "panel/CPanel.h"
#include <QApplication>
#include <QDebug>

CPlayer::CPlayer() {

}

CPlayer::~CPlayer() {

}

void CPlayer::onTurn ( std::shared_ptr<CGameEvent> ) {
    addMana ( manaRegRate );
    turn++;
    checkQuests();
}

void CPlayer::checkQuests() {
    auto set=quests;
    for ( auto quest:set ) {
        if ( quest->isCompleted() ) {
            quest->onComplete();
            quests.erase ( quests.find ( quest ) );
        }
    }
}

void CPlayer::onDestroy ( std::shared_ptr<CGameEvent> ) {
    getMap()->addObject ( this->ptr<CPlayer>() );
    moveTo ( getMap()->getEntryX(),getMap()->getEntryY(),getMap()->getEntryZ() );
    this->hp=1;
}

std::shared_ptr<CInteraction> CPlayer::selectAction() {
    while ( ! this->getSelectedAction() ) {
        QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
    }
    std::shared_ptr<CInteraction> action=this->getSelectedAction();
    this->setSelectedAction ( nullptr );
    return action;
}

void CPlayer::fight ( std::shared_ptr<CCreature> creature ) {
    setEnemy ( creature );
    getMap()->getGame()->getGuiHandler()->getPanel ( "CFightPanel" )->showPanel();
    CCreature::fight ( creature );
    getMap()->getGame()->getGuiHandler()->getPanel ( "CFightPanel" )->hidePanel();
    setEnemy ( nullptr );
}

void CPlayer::trade ( std::shared_ptr<CGameObject> object ) {
    if ( std::shared_ptr<CMarket> market=cast<CMarket> ( object ) ) {
        setMarket ( market );
        std::shared_ptr<AGamePanel> panel=getMap()->getGame()->getGuiHandler()->getPanel ( "CTradePanel" );
        panel->showPanel();
        while ( panel->isShown() ) {
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

void CPlayer::setSelectedAction ( std::shared_ptr<CInteraction> value ) {
    selectedAction = value;
}

std::shared_ptr<CCreature> CPlayer::getEnemy() const {
    return enemy;
}

void CPlayer::setEnemy ( std::shared_ptr<CCreature> value ) {
    enemy = value;
}

std::shared_ptr<CMarket> CPlayer::getMarket() const {
    return market;
}

void CPlayer::setMarket ( std::shared_ptr<CMarket> value ) {
    market = value;
}

void CPlayer::addQuest ( QString questName ) {
    std::shared_ptr<CQuest> quest=getMap()->createObject<CQuest> ( questName );
    if ( quest ) {
        quests.insert ( quest );
    }
}

void CPlayer::setNextMove ( Coords coords ) {
    this->next=coords;
}

std::shared_ptr<CInteraction> CPlayer::getSelectedAction() const {
    return selectedAction;
}
