/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include <utility>

void CPlayer::checkQuests() {
  auto set = quests;
  for (const auto &quest : set) {
    if (quest->isCompleted()) {
      quest->onComplete();
      quests.erase(quests.find(quest));
      completedQuests.insert(quest);
    }
  }
}

void CPlayer::addQuest(std::string questName) {
  for (const auto &q : quests) {
    if (q->getName() == questName) {
      return;
    }
  }
  for (const auto &q : completedQuests) {
    if (q->getName() == questName) {
      return;
    }
  }
  std::shared_ptr<CQuest> quest = getGame()->createObject<CQuest>(questName);
  if (quest) {
    quests.insert(quest);
  }
}

std::set<std::shared_ptr<CQuest>> CPlayer::getQuests() { return quests; }

void CPlayer::setQuests(std::set<std::shared_ptr<CQuest>> _quests) {
  this->quests = std::move(_quests);
}

std::set<std::shared_ptr<CQuest>> CPlayer::getCompletedQuests() {
  return completedQuests;
}

void CPlayer::setCompletedQuests(
    std::set<std::shared_ptr<CQuest>> _completedQuests) {
  completedQuests = std::move(_completedQuests);
}

void CPlayer::incTurn() { turn++; }
