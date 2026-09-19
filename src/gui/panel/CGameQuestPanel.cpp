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
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CDetailViewport.h"
#include "gui/CUiTheme.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"

#include <algorithm>
#include <sstream>

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
    if (!gui || !rect || rect->w <= 0 || rect->h <= 0) {
        return;
    }
    for (const auto &child : getChildren()) {
        auto list = vstd::cast<CListView>(child);
        if (list && list->getCollection() == "questCollection") {
            CGamePanel::renderObject(gui, rect, i);
            return;
        }
    }
    refreshScrollLayout(gui);
    const int side = UiTheme::scaled(gui, 24);
    const int top = UiTheme::scaled(gui, 116);
    auto viewport = CUtil::rect(rect->x + side, rect->y + top, std::max(1, rect->w - side * 2), viewportHeight);
    auto textManager = gui->getTextManager();
    auto first = std::lower_bound(paragraphs.begin(), paragraphs.end(), scrollOffset,
                                  [](const auto &paragraph, int y) { return paragraph.y + paragraph.height <= y; });
    for (auto paragraph = first; paragraph != paragraphs.end() && paragraph->y < scrollOffset + viewportHeight;
         ++paragraph) {
        textManager->drawTextScrolled(paragraph->text, viewport, paragraph->y - scrollOffset);
    }
    const std::string position = scrollMaximum ? std::to_string(100LL * scrollOffset / scrollMaximum) + "%" : "100%";
    auto footer =
        CUtil::rect(rect->x + side, rect->y + top + viewportHeight, rect->w - side * 2, UiTheme::scaled(gui, 28));
    textManager->drawTextStyled("Scroll: wheel / arrows / PgUp / PgDn - " + position, footer, "small", UiTheme::Muted);
}

void CGameQuestPanel::refreshScrollLayout(const std::shared_ptr<CGui> &gui) {
    if (!gui) {
        return;
    }
    refreshTextCache(gui);
    const auto rect = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : CUtil::rect(0, 0, 0, 0);
    auto textManager = gui->getTextManager();
    const int currentLineHeight = std::max(24, textManager->getTextureSize("Ag").second);
    if (measuredTextManager.lock() != textManager || lineHeight != currentLineHeight) {
        lineHeight = currentLineHeight;
        measuredTextManager = textManager;
        paragraphLayoutDirty = true;
    }
    viewportHeight = std::max(0, rect->h - UiTheme::scaled(gui, 192));
    const int width = std::max(1, rect->w - UiTheme::scaled(gui, 48));
    if (paragraphLayoutDirty || paragraphWidth != width) {
        paragraphs.clear();
        contentHeight = 0;
        std::istringstream lines(cachedQuestText);
        std::string line;
        while (std::getline(lines, line)) {
            // Keep each texture below the text manager's byte limit; long journals
            // must remain readable even when their combined text exceeds that limit.
            constexpr std::size_t chunkSize = 1024;
            std::size_t offset = 0;
            do {
                auto end = std::min(offset + chunkSize, line.size());
                while (end < line.size() && end > offset && (static_cast<unsigned char>(line[end]) & 0xc0) == 0x80) {
                    --end;
                }
                if (end == offset) {
                    end = std::min(offset + chunkSize, line.size());
                }
                auto chunk = line.substr(offset, end - offset);
                const int height = measureParagraphHeight(textManager, chunk, width);
                paragraphs.push_back({std::move(chunk), contentHeight, height});
                contentHeight += height;
                offset = end;
            } while (offset < line.size());
        }
        paragraphWidth = width;
        paragraphLayoutDirty = false;
    }
    scrollMaximum = std::max(0, contentHeight - viewportHeight);
    scrollOffset = std::clamp(scrollOffset, 0, scrollMaximum);
}

int CGameQuestPanel::measureParagraphHeight(const std::shared_ptr<CTextManager> &textManager, const std::string &text,
                                            int width) {
    return text.empty() ? lineHeight : std::max(lineHeight, textManager->getWrappedTextureSize(text, width).second);
}

std::string CGameQuestPanel::getViewportText(const std::shared_ptr<CGui> &gui) {
    refreshScrollLayout(gui);
    std::string text;
    for (const auto &paragraph : paragraphs) {
        if (paragraph.y + paragraph.height > scrollOffset && paragraph.y < scrollOffset + viewportHeight) {
            text += paragraph.text + "\n";
        }
    }
    return text;
}

int CGameQuestPanel::getScrollOffset() const { return scrollOffset; }

int CGameQuestPanel::getScrollMaximum() const { return scrollMaximum; }

void CGameQuestPanel::scrollBy(long long delta) {
    scrollOffset = static_cast<int>(
        std::clamp(static_cast<long long>(scrollOffset) + delta, 0LL, static_cast<long long>(scrollMaximum)));
}

bool CGameQuestPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type != SDL_KEYDOWN) {
        return true;
    }
    if (detailsViewport.w > 0 && (key == SDLK_PAGEUP || key == SDLK_PAGEDOWN)) {
        detailsOffset = std::clamp(detailsOffset + (key == SDLK_PAGEUP ? -1 : 1) * std::max(1, detailsViewport.h - 24),
                                   0, detailsMaximum);
        return true;
    }
    refreshScrollLayout(gui);
    switch (key) {
    case SDLK_UP:
        scrollBy(-lineHeight);
        break;
    case SDLK_DOWN:
        scrollBy(lineHeight);
        break;
    case SDLK_PAGEUP:
        scrollBy(-std::max(1, viewportHeight - lineHeight));
        break;
    case SDLK_PAGEDOWN:
        scrollBy(std::max(1, viewportHeight - lineHeight));
        break;
    case SDLK_HOME:
        scrollOffset = 0;
        break;
    case SDLK_END:
        scrollOffset = scrollMaximum;
        break;
    default:
        return CGamePanel::keyboardEvent(gui, type, key);
    }
    return true;
}

bool CGameQuestPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
                                      int wheelY) {
    if (detailsViewport.w > 0) {
        auto origin = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : nullptr;
        SDL_Point point{x + (origin ? origin->x : 0), y + (origin ? origin->y : 0)};
        if (!SDL_PointInRect(&point, &detailsViewport)) {
            return false;
        }
        detailsOffset =
            static_cast<int>(std::clamp(static_cast<long long>(detailsOffset) - static_cast<long long>(wheelY) * 72,
                                        0LL, static_cast<long long>(detailsMaximum)));
        return true;
    }
    refreshScrollLayout(gui);
    scrollBy(-static_cast<long long>(wheelY) * lineHeight * 3);
    return true;
}

std::string CGameQuestPanel::getText(std::shared_ptr<CGui> ptr) {
    refreshTextCache(ptr);
    return cachedQuestText;
}

void CGameQuestPanel::refreshTextCache(const std::shared_ptr<CGui> &ptr) {
    // Reactive read path: the journal text is only rebuilt when a change subscription
    // (see refreshQuestSubscriptions) marked it stale, instead of re-walking the quest
    // log on every rendered frame.
    auto player = resolveQuestSource(ptr);
    refreshQuestSubscriptions(player, resolveQuestStateSource(ptr));
    if (activeTab == "history") {
        const auto dialogue = player ? player->getStringProperty("uiDialogueHistory") : "";
        const auto notifications = ptr ? ptr->getUiHistory() : "";
        if (dialogue != cachedDialogueHistory || notifications != cachedNotificationHistory) {
            cachedDialogueHistory = dialogue;
            cachedNotificationHistory = notifications;
            questTextDirty = true;
        }
    }
    if (questTextDirty) {
        cachedQuestText = buildText(player);
        ++questTextVersion;
        questTextDirty = false;
        paragraphLayoutDirty = true;
    }
}

std::shared_ptr<CPlayer> CGameQuestPanel::resolveQuestSource(const std::shared_ptr<CGui> &gui) {
    auto game = gui ? gui->getGame() : nullptr;
    auto map = game ? game->getMap() : nullptr;
    return map ? map->getPlayer() : nullptr;
}

std::shared_ptr<CGameObject> CGameQuestPanel::resolveQuestStateSource(const std::shared_ptr<CGui> &gui) {
    auto game = gui ? gui->getGame() : nullptr;
    return game ? game->getMap() : nullptr;
}

std::string CGameQuestPanel::buildText(const std::shared_ptr<CPlayer> &player) {
    if (activeTab == "history") {
        std::string text = "CONVERSATIONS\n\n";
        auto appendHistory = [&text](const std::string &serialized) {
            json entries;
            try {
                entries = json::parse(serialized.empty() ? "[]" : serialized);
            } catch (const std::exception &) {
                return;
            }
            if (!entries.is_array()) {
                return;
            }
            for (const auto &entry : entries) {
                if (entry.is_string()) {
                    text += entry.get<std::string>() + "\n\n";
                } else if (entry.is_object() && entry.contains("text") && entry["text"].is_string()) {
                    if (entry.contains("speaker") && entry["speaker"].is_string()) {
                        text += entry["speaker"].get<std::string>() + "\n";
                    }
                    text += entry["text"].get<std::string>() + "\n\n";
                }
            }
        };
        appendHistory(cachedDialogueHistory);
        text += "RECENT UPDATES\n\n";
        appendHistory(cachedNotificationHistory);
        return text;
    }
    if (!player) {
        return "No active quests.\n";
    }
    std::string text;
    if (activeTab == "completed") {
        for (auto quest : player->getCompletedQuests()) {
            append_quest_line(text, quest, true);
        }
    } else {
        const auto tracked = player->getStringProperty("uiTrackedQuestId");
        for (auto quest : player->getQuests()) {
            if (quest && !tracked.empty() && quest->getName() == tracked) {
                text += "TRACKED QUEST\n";
                append_quest_line(text, quest, false);
            }
        }
        for (auto quest : player->getQuests()) {
            if (quest && (tracked.empty() || quest->getName() != tracked)) {
                append_quest_line(text, quest, false);
            }
        }
    }
    if (text.empty()) {
        text = activeTab == "completed" ? "No completed quests yet.\n" : "No active quests.\n";
    }
    return text;
}

void CGameQuestPanel::showActive(std::shared_ptr<CGui> gui) { switchTab(gui, "active"); }

void CGameQuestPanel::showCompleted(std::shared_ptr<CGui> gui) { switchTab(gui, "completed"); }

void CGameQuestPanel::showHistory(std::shared_ptr<CGui> gui) { switchTab(gui, "history"); }

void CGameQuestPanel::switchTab(const std::shared_ptr<CGui> &gui, const std::string &tab) {
    if (activeTab == tab) {
        return;
    }
    auto &previous = tabStates[activeTab];
    previous.selectedQuest = selectedQuest;
    previous.scrollOffset = scrollOffset;
    previous.detailsOffset = detailsOffset;
    std::shared_ptr<CListView> list;
    for (const auto &child : getChildren()) {
        if (auto candidate = vstd::cast<CListView>(child);
            candidate && candidate->getCollection() == "questCollection") {
            list = candidate;
            previous.list = list->getViewState();
            break;
        }
    }
    activeTab = tab;
    const auto &restored = tabStates[tab];
    selectedQuest = restored.selectedQuest;
    scrollOffset = restored.scrollOffset;
    detailsOffset = restored.detailsOffset;
    selectedTextVersion = -1;
    questTextDirty = true;
    if (list) {
        list->restoreViewState(restored.list);
    }
    refreshViews();
}

bool CGameQuestPanel::setTrackedQuest(std::shared_ptr<CGui> gui, const std::string &questId) {
    auto player = resolveQuestSource(gui);
    if (!player) {
        return false;
    }
    if (!questId.empty()) {
        auto quests = player->getQuests();
        if (std::none_of(quests.begin(), quests.end(),
                         [&questId](const auto &quest) { return quest && quest->getName() == questId; })) {
            return false;
        }
    }
    player->setStringProperty("uiTrackedQuestId", questId);
    questTextDirty = true;
    return true;
}

void CGameQuestPanel::chooseTrackedQuest(std::shared_ptr<CGui> gui) {
    auto player = resolveQuestSource(gui);
    if (!player || !gui || !gui->getGame()) {
        return;
    }
    json choices = json::array();
    choices[choices.size()] = {{"id", "clearTracking"},
                               {"label", "Stop tracking"},
                               {"detail", "Keep your journal available without a tracked objective."}};
    for (const auto &quest : player->getQuests()) {
        if (quest) {
            choices[choices.size()] = {{"id", quest->getName()},
                                       {"label", quest->getDescription()},
                                       {"detail", quest->getObjective() + "\n" + quest->getHint()}};
        }
    }
    const auto choice =
        gui->getGame()->getGuiHandler()->showChoice("Track a quest", choices.dump(), "Track quest", "Back");
    if (!choice.empty()) {
        setTrackedQuest(gui, choice == "clearTracking" ? "" : choice);
    }
}

CListView::collection_pointer CGameQuestPanel::questCollection(std::shared_ptr<CGui> gui) {
    auto collection = std::make_shared<CListView::collection_type>();
    auto player = resolveQuestSource(gui);
    if (!player || activeTab == "history") {
        return collection;
    }
    const auto quests = activeTab == "completed" ? player->getCompletedQuests() : player->getQuests();
    for (const auto &quest : quests) {
        collection->push_back(quest);
    }
    auto selected = selectedQuest.lock();
    if (std::none_of(quests.begin(), quests.end(),
                     [selected](const auto &quest) { return CGameObject::sameInstance(selected, quest); })) {
        selectedQuest = quests.empty() ? nullptr : *quests.begin();
        selectedTextVersion = -1;
        detailsOffset = 0;
    }
    return collection;
}

void CGameQuestPanel::questCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    auto quests = questCollection(gui);
    if (std::any_of(quests->begin(), quests->end(),
                    [object](const auto &quest) { return CGameObject::sameInstance(object, quest); })) {
        selectedQuest = object;
        selectedTextVersion = -1;
        detailsOffset = 0;
        refreshViews();
    }
}

bool CGameQuestPanel::questSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && CGameObject::sameInstance(selectedQuest.lock(), object);
}

std::string CGameQuestPanel::getSelectedQuestText(std::shared_ptr<CGui> gui) {
    refreshTextCache(gui);
    if (activeTab == "history") {
        return cachedQuestText;
    }
    auto quests = questCollection(gui);
    auto current = selectedQuest.lock();
    if (std::none_of(quests->begin(), quests->end(),
                     [current](const auto &quest) { return CGameObject::sameInstance(current, quest); })) {
        current = quests->empty() ? nullptr : *quests->begin();
        selectedQuest = current;
        selectedTextVersion = -1;
    }
    if (selectedTextVersion != questTextVersion) {
        selectedQuestText.clear();
        auto quest = vstd::cast<CQuest>(current);
        if (quest) {
            append_quest_line(selectedQuestText, quest, activeTab == "completed");
            auto player = resolveQuestSource(gui);
            if (activeTab == "active" && player && player->getStringProperty("uiTrackedQuestId") == quest->getName()) {
                selectedQuestText = "TRACKED QUEST\n\n" + selectedQuestText;
            }
        } else {
            selectedQuestText = activeTab == "completed" ? "No completed quests yet." : "No active quests.";
        }
        selectedTextVersion = questTextVersion;
    }
    return selectedQuestText;
}

void CGameQuestPanel::renderSelectedQuest(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!gui || !rect) {
        return;
    }
    const auto text = getSelectedQuestText(gui);
    detailLayout.update(gui, text, rect->w);
    const auto content = DetailViewport::contentRect(gui, rect, detailLayout.getContentHeight());
    detailsViewport = *content;
    detailsMaximum = std::max(0, detailLayout.getContentHeight() - content->h);
    detailsOffset = std::clamp(detailsOffset, 0, detailsMaximum);
    detailLayout.draw(gui, content, detailsOffset);
    DetailViewport::drawScrollHint(gui, rect, content, detailsOffset, detailsMaximum);
}

void CGameQuestPanel::trackSelectedQuest(std::shared_ptr<CGui> gui) {
    if (activeTab != "active") {
        return;
    }
    getSelectedQuestText(gui);
    if (auto quest = selectedQuest.lock()) {
        auto player = resolveQuestSource(gui);
        setTrackedQuest(
            gui, player && player->getStringProperty("uiTrackedQuestId") == quest->getName() ? "" : quest->getName());
    }
}

void CGameQuestPanel::refreshFromQuestsChanged() { questTextDirty = true; }

void CGameQuestPanel::refreshFromMapPropertyChanged(std::string propertyName) { questTextDirty = true; }

void CGameQuestPanel::refreshFromMapObjectChanged(Coords coords) { questTextDirty = true; }

void CGameQuestPanel::refreshQuestSubscriptions(const std::shared_ptr<CPlayer> &player,
                                                const std::shared_ptr<CGameObject> &questState) {
    // CPlayer records every quest-log mutation through recordDirectPropertyChanged
    // ("quests" / "completedQuests"), which emits the derived "questsChanged" /
    // "completedQuestsChanged" property channels this panel subscribes to — the same
    // dynamic-property notification mechanism CListView refresh subscriptions ride on.
    auto subscribedPlayer = subscribedQuestSource.lock();
    if (subscribedPlayer != player) {
        auto self = this->ptr<CGameQuestPanel>();
        if (subscribedPlayer) {
            subscribedPlayer->disconnect("questsChanged", self, "refreshFromQuestsChanged");
            subscribedPlayer->disconnect("completedQuestsChanged", self, "refreshFromQuestsChanged");
        }
        subscribedQuestSource = player;
        if (player) {
            player->connect("questsChanged", self, "refreshFromQuestsChanged");
            player->connect("completedQuestsChanged", self, "refreshFromQuestsChanged");
        }
        // The quest source changed (first resolve, detach, or a new player after a
        // game load / map transition): whatever was cached belongs to the old source.
        questTextDirty = true;
    }

    // Quest journal getters are arbitrary map scripts: their objective/reward/hint
    // text derives from quest-state properties written on the map
    // (QuestStateStore.set_state → setStringProperty("quest_state_*") →
    // recordPropertyChanged → "propertyChanged") and from map object state advanced by
    // gameplay. Membership signals alone would leave that text stale, so the map's
    // generic propertyChanged channel plus the turnPassed / objectChanged typed
    // signals (the same set CMapGraphicsObject subscribes to) conservatively
    // invalidate the cache; the dirty flag keeps it to at most one rebuild per read.
    auto subscribedState = subscribedQuestStateSource.lock();
    if (subscribedState != questState) {
        auto self = this->ptr<CGameQuestPanel>();
        if (subscribedState) {
            subscribedState->disconnect("propertyChanged", self, "refreshFromMapPropertyChanged");
            subscribedState->disconnect("turnPassed", self, "refreshFromQuestsChanged");
            subscribedState->disconnect("objectChanged", self, "refreshFromMapObjectChanged");
        }
        subscribedQuestStateSource = questState;
        if (questState) {
            questState->connect("propertyChanged", self, "refreshFromMapPropertyChanged");
            questState->connect("turnPassed", self, "refreshFromQuestsChanged");
            questState->connect("objectChanged", self, "refreshFromMapObjectChanged");
        }
        questTextDirty = true;
    }
}
