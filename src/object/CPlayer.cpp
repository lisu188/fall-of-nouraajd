/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
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


