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
#include "CGameQuestPanel.h"
#include "core/CMap.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"

namespace {
void append_quest_line(std::string &text, const std::shared_ptr<CQuest> &quest, bool completed) {
    if (!quest) {
        return;
    }

    text += completed ? "[Completed] " : "[Active] ";
    text += quest->getDescription();
    text += "\n";

    const auto objective = quest->getObjective();
    if (!objective.empty()) {
        text += "  Objective: ";
        text += objective;
        text += "\n";
    }

    const auto reward = quest->getReward();
    if (!reward.empty()) {
        text += "  Reward: ";
        text += reward;
        text += "\n";
    }

    const auto hint = quest->getHint();
    if (!completed && !hint.empty()) {
        text += "  Hint: ";
        text += hint;
        text += "\n";
    }

    if (completed) {
        text += "  Status: Completed\n";
    }
    text += "\n";
}
} // namespace

void CGameQuestPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int i) {
    gui->getTextManager()->drawText(getText(gui), rect);
}

std::string CGameQuestPanel::getText(std::shared_ptr<CGui> ptr) {
    // Reactive read path: the journal text is only rebuilt when the quest-change
    // subscription (see refreshQuestSubscription) marked it stale, instead of
    // re-walking the quest log on every rendered frame.
    auto player = resolveQuestSource(ptr);
    refreshQuestSubscription(player);
    if (questTextDirty) {
        cachedQuestText = buildText(player);
        questTextDirty = false;
    }
    return cachedQuestText;
}

std::shared_ptr<CPlayer> CGameQuestPanel::resolveQuestSource(const std::shared_ptr<CGui> &gui) {
    auto game = gui ? gui->getGame() : nullptr;
    auto map = game ? game->getMap() : nullptr;
    return map ? map->getPlayer() : nullptr;
}

std::string CGameQuestPanel::buildText(const std::shared_ptr<CPlayer> &player) {
    if (!player) {
        return "No active quests.\n";
    }
    std::string text = "";
    for (auto quest : player->getCompletedQuests()) {
        append_quest_line(text, quest, true);
    }
    for (auto quest : player->getQuests()) {
        append_quest_line(text, quest, false);
    }
    if (text.empty()) {
        text = "No active quests.\n";
    }
    return text;
}

void CGameQuestPanel::refreshFromQuestsChanged() { questTextDirty = true; }

void CGameQuestPanel::refreshQuestSubscription(const std::shared_ptr<CPlayer> &player) {
    auto subscribed = subscribedQuestSource.lock();
    if (subscribed == player) {
        return;
    }

    // CPlayer records every quest-log mutation through recordDirectPropertyChanged
    // ("quests" / "completedQuests"), which emits the derived "questsChanged" /
    // "completedQuestsChanged" property channels this panel subscribes to — the same
    // dynamic-property notification mechanism CListView refresh subscriptions ride on.
    auto self = this->ptr<CGameQuestPanel>();
    if (subscribed) {
        subscribed->disconnect("questsChanged", self, "refreshFromQuestsChanged");
        subscribed->disconnect("completedQuestsChanged", self, "refreshFromQuestsChanged");
    }
    subscribedQuestSource = player;
    if (player) {
        player->connect("questsChanged", self, "refreshFromQuestsChanged");
        player->connect("completedQuestsChanged", self, "refreshFromQuestsChanged");
    }
    // The quest source changed (first resolve, detach, or a new player after a game
    // load / map transition): whatever was cached belongs to the old source.
    questTextDirty = true;
}
