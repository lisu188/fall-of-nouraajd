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
#include "core/CAsync.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "handler/CGuiHandler.h"
#include "handler/CScriptHandler.h"
#include <exception>
#include <utility>

namespace {
constexpr const char *DEFAULT_PLAYER_RACE_ID = "human";

class QuestCheckGuard {
  public:
    explicit QuestCheckGuard(bool &checking) : checking(checking) { checking = true; }

    ~QuestCheckGuard() { checking = false; }

  private:
    bool &checking;
};

std::string questId(const std::shared_ptr<CQuest> &quest) {
    if (!quest) {
        return "";
    }
    auto typeId = quest->getTypeId();
    return typeId.empty() ? quest->getName() : typeId;
}
} // namespace

std::string CPlayer::getUiDialogueHistory() { return uiDialogueHistory; }

void CPlayer::setUiDialogueHistory(std::string history) { uiDialogueHistory = std::move(history); }

std::string CPlayer::getUiDefeatReceipt() { return uiDefeatReceipt; }

void CPlayer::setUiDefeatReceipt(std::string receipt) { uiDefeatReceipt = std::move(receipt); }

void CPlayer::checkQuests() {
    if (checkingQuests) {
        return;
    }
    if (auto game = getGame()) {
        game_async::wait(game->getContext()->spawnTask(checkQuestsAsync()));
    } else {
        game_async::run(checkQuestsAsync());
    }
}

vstd::task<void> CPlayer::checkQuestsAsync() {
    return [](std::shared_ptr<CPlayer> self) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        if (self->checkingQuests) {
            co_return;
        }
        QuestCheckGuard checkGuard(self->checkingQuests);
        const auto stop = co_await vstd::thisTaskStopToken();
        auto owner = self->getGame();
        auto context = owner ? owner->getContext() : nullptr;
        owner.reset();
        auto checkActive = [&] {
            if (stop.stop_requested() || (context && !context->isActive())) {
                throw vstd::task_cancelled();
            }
        };
        auto set = self->quests;
        for (const auto &quest : set) {
            checkActive();
            if (!quest) {
                self->quests.erase(quest);
                continue;
            }
            if (!self->quests.contains(quest)) {
                continue;
            }
            const bool completed = quest->isCompleted();
            checkActive();
            if (!completed || !self->quests.contains(quest)) {
                continue;
            }
            if (CPlaytestTrace::enabled()) {
                json fields = {{"player", CPlaytestTrace::objectRef(self)}, {"quest", questId(quest)}};
                CPlaytestTrace::addMapContext(fields, self->getMap());
                CPlaytestTrace::record("quest_completed", fields);
            }
            auto finish = [self, quest, context](bool notify) {
                std::exception_ptr captureFailure;
                if (notify) {
                    try {
                        quest->captureJournal(true);
                    } catch (...) {
                        captureFailure = std::current_exception();
                    }
                }
                self->quests.erase(quest);
                self->completedQuests.insert(quest);
                if (notify && (!context || context->isActive())) {
                    self->recordDirectPropertyChanged("quests");
                    if (!context || context->isActive()) {
                        self->recordDirectPropertyChanged("completedQuests");
                    }
                }
                if (captureFailure) {
                    std::rethrow_exception(captureFailure);
                }
            };
            auto game = self->getGame();
            auto committed = std::make_shared<bool>(false);
            auto flow = CScriptHandler::createObjectFlow(quest, "onCompleteFlow", {}, game, committed);
            checkActive();
            if (flow) {
                auto gui = game->getGuiHandler();
                game.reset();
                try {
                    co_await gui->runScriptFlowAsync(std::move(flow));
                } catch (...) {
                    if (*committed) {
                        finish(context->isActive());
                    }
                    throw;
                }
            } else {
                game.reset();
                quest->onComplete();
            }
            finish(!context || context->isActive());
        }
    }(this->ptr<CPlayer>());
}

void CPlayer::captureQuestJournal() {
    const auto active = quests;
    const auto completed = completedQuests;
    for (const auto &quest : active) {
        if (quest && quests.contains(quest)) {
            quest->captureJournal(false);
        }
    }
    for (const auto &quest : completed) {
        if (quest && completedQuests.contains(quest)) {
            quest->captureJournal(true);
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
