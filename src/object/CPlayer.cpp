#include "CPlayer.h"
#include "core/CGame.h"

CPlayer::CPlayer() {

}

CPlayer::~CPlayer() {

}

void CPlayer::onTurn(std::shared_ptr<CGameEvent>) {
    addMana(manaRegRate);
    turn++;
    checkQuests();
}

void CPlayer::checkQuests() {
    auto set = quests;
    for (auto quest:set) {
        if (quest->isCompleted()) {
            quest->onComplete();
            quests.erase(quests.find(quest));
        }
    }
}

void CPlayer::onDestroy(std::shared_ptr<CGameEvent> event) {
    CCreature::onDestroy(event);
    getMap()->addObject(this->ptr<CPlayer>());
    moveTo(getMap()->getEntryX(), getMap()->getEntryY(), getMap()->getEntryZ());
    this->hp = 1;
}

std::shared_ptr<CInteraction> CPlayer::selectAction() {
    //TODO: code with futures
    return CCreature::selectAction();
//    while (!this->getSelectedAction()) {
////        QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
//    }
//    std::shared_ptr<CInteraction> action = this->getSelectedAction();
//    this->setSelectedAction(nullptr);
//    return action;
}

void CPlayer::fight(std::shared_ptr<CCreature> creature) {
    //TODO: fight
    setEnemy(creature);
    //getMap()->getGame()->getGuiHandler()->getPanel ( "CFightPanel" )->showPanel();
    CCreature::fight(creature);
    //getMap()->getGame()->getGuiHandler()->getPanel ( "CFightPanel" )->hidePanel();
    setEnemy(nullptr);
}

void CPlayer::trade(std::shared_ptr<CMarket> market) {
    //TODO: trade
//    if ( market ) {
//        setMarket ( market );
//        std::shared_ptr<AGamePanel> panel = getMap()->getGame()->getGuiHandler()->getPanel ( "CTradePanel" );
//        panel->showPanel();
//        //TODO: code with futures
//        while ( panel->isShown() ) {
//            QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
//        }
//        setMarket ( nullptr );
//    }
}

void CPlayer::setSelectedAction(std::shared_ptr<CInteraction> value) {
    selectedAction = value;
}

std::shared_ptr<CCreature> CPlayer::getEnemy() const {
    return enemy;
}

void CPlayer::setEnemy(std::shared_ptr<CCreature> value) {
    enemy = value;
}

std::shared_ptr<CMarket> CPlayer::getMarket() const {
    return market;
}

void CPlayer::setMarket(std::shared_ptr<CMarket> value) {
    market = value;
}

void CPlayer::addQuest(std::string questName) {
    std::shared_ptr<CQuest> quest = getMap()->createObject<CQuest>(questName);
    if (quest) {
        quests.insert(quest);
    }
}

void CPlayer::setNextMove(Coords coords) {
    this->next = coords;
}

std::shared_ptr<CInteraction> CPlayer::getSelectedAction() const {
    return selectedAction;
}
