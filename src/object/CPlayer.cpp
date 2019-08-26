#include "CPlayer.h"
#include "core/CGame.h"
#include "core/CMap.h"

CPlayer::CPlayer() {

}

CPlayer::~CPlayer() {

}

void CPlayer::onTurn(std::shared_ptr<CGameEvent>) {
    addMana(getManaRegRate());
    turn++;
    checkQuests();
}

void CPlayer::checkQuests() {
    auto set = quests;
    for (auto quest:set) {
        if (quest->isCompleted()) {
            quest->onComplete();
            quests.erase(quests.find(quest));
            completedQuests.insert(quest);
        }
    }
}

void CPlayer::onDestroy(std::shared_ptr<CGameEvent> event) {
    CCreature::onDestroy(event);
    getMap()->addObject(this->ptr<CPlayer>());
    moveTo(getMap()->getEntryX(), getMap()->getEntryY(), getMap()->getEntryZ());
    setHp(1);
}


void CPlayer::addQuest(std::string questName) {
    std::shared_ptr<CQuest> quest = getGame()->createObject<CQuest>(questName);
    if (quest) {
        quests.insert(quest);
    }
}

std::set<std::shared_ptr<CQuest>> CPlayer::getQuests() {
    return quests;
}

void CPlayer::setQuests(std::set<std::shared_ptr<CQuest>> quests) {
    this->quests = quests;
}

std::set<std::shared_ptr<CQuest>> CPlayer::getCompletedQuests() {
    return completedQuests;
}

void CPlayer::setCompletedQuests(std::set<std::shared_ptr<CQuest>> completedQuests) {
    CPlayer::completedQuests = completedQuests;
}


