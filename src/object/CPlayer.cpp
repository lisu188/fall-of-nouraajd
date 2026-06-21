/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "core/CPlaytestTrace.h"
#include <utility>

namespace {
constexpr const char *DEFAULT_PLAYER_RACE_ID = "human";

std::string questId(const std::shared_ptr<CQuest> &quest) {
    if (!quest) {
        return "";
    }
    auto typeId = quest->getTypeId();
    return typeId.empty() ? quest->getName() : typeId;
}
} // namespace

void CPlayer::checkQuests() {
    auto set = quests;
    for (const auto &quest : set) {
        if (!quest) {
            quests.erase(quest);
            continue;
        }
        if (quest->isCompleted()) {
            if (CPlaytestTrace::enabled()) {
                json fields = {
                    {"player", CPlaytestTrace::objectRef(this->ptr<CPlayer>())},
                    {"quest", questId(quest)},
                };
                CPlaytestTrace::addMapContext(fields, getMap());
                CPlaytestTrace::record("quest_completed", fields);
            }
            quest->onComplete();
            quests.erase(quests.find(quest));
            completedQuests.insert(quest);
            recordDirectPropertyChanged("quests");
            recordDirectPropertyChanged("completedQuests");
        }
    }
}

void CPlayer::addQuest(std::string questName) {
    for (const auto &q : quests) {
        if (questId(q) == questName) {
            return;
        }
    }
    for (const auto &q : completedQuests) {
        if (questId(q) == questName) {
            return;
        }
    }
    std::shared_ptr<CQuest> quest = getGame()->createObject<CQuest>(questName);
    if (quest) {
        quests.insert(quest);
        if (CPlaytestTrace::enabled()) {
            json fields = {
                {"player", CPlaytestTrace::objectRef(this->ptr<CPlayer>())},
                {"quest", questName},
            };
            CPlaytestTrace::addMapContext(fields, getMap());
            CPlaytestTrace::record("quest_added", fields);
        }
        recordDirectPropertyChanged("quests");
    }
}

std::set<std::shared_ptr<CQuest>> CPlayer::getQuests() { return quests; }

void CPlayer::setQuests(std::set<std::shared_ptr<CQuest>> _quests) {
    std::erase_if(_quests, [](const auto &quest) { return quest == nullptr; });
    this->quests = std::move(_quests);
    recordDirectPropertyChanged("quests");
}

std::set<std::shared_ptr<CQuest>> CPlayer::getCompletedQuests() { return completedQuests; }

void CPlayer::setCompletedQuests(std::set<std::shared_ptr<CQuest>> _completedQuests) {
    std::erase_if(_completedQuests, [](const auto &quest) { return quest == nullptr; });
    completedQuests = std::move(_completedQuests);
    recordDirectPropertyChanged("completedQuests");
}

std::string CPlayer::getPlayerClassId() {
    if (!playerClassId.empty()) {
        return playerClassId;
    }
    return getTypeId();
}

void CPlayer::setPlayerClassId(std::string _playerClassId) {
    playerClassId = std::move(_playerClassId);
    recordDirectPropertyChanged("playerClassId");
}

std::string CPlayer::getRaceId() {
    if (!raceId.empty()) {
        return raceId;
    }
    return DEFAULT_PLAYER_RACE_ID;
}

void CPlayer::setRaceId(std::string _raceId) {
    raceId = std::move(_raceId);
    recordDirectPropertyChanged("raceId");
}

void CPlayer::incTurn() { turn++; }
