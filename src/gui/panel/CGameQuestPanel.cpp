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
    std::string text = "";
    auto game = ptr ? ptr->getGame() : nullptr;
    auto map = game ? game->getMap() : nullptr;
    auto player = map ? map->getPlayer() : nullptr;
    if (!player) {
        return "No active quests.\n";
    }
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
