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
#include "CSideBar.h"
#include "core/CList.h"
#include "gui/CGui.h"
#include "gui/panel/CGamePanel.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"
#include "core/CMap.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "handler/CGuiHandler.h"
#include "gui/CLayout.h"
#include "gui/object/CWidget.h"

void CSideBar::clickInventory(std::shared_ptr<CGui> gui) { flipPanel(gui, "inventoryPanel"); }

void CSideBar::clickJournal(std::shared_ptr<CGui> gui) { flipPanel(gui, "questPanel"); }

void CSideBar::clickCharacter(std::shared_ptr<CGui> gui) { flipPanel(gui, "characterPanel"); }

void CSideBar::clickPause(std::shared_ptr<CGui> gui) { gui->getGame()->getGuiHandler()->showPauseMenu(); }

void CSideBar::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int) {
    auto map = gui->getGame() ? gui->getGame()->getMap() : nullptr;
    auto player = map ? map->getPlayer() : nullptr;
    if (!player)
        return;
    auto text = gui->getTextManager();
    const int pad = UiTheme::scaled(gui, 12);
    const double scale = std::max(gui->getUiScale(), gui->getTextScale());
    const auto preferences = json::parse(gui->getUiPreferences());
    const std::map<std::string, std::pair<std::string, std::string>> dockLabels{
        {"clickInventory", {"Inventory", "inventory"}},
        {"clickJournal", {"Journal", "journal"}},
        {"clickCharacter", {"Character", "character"}},
        {"clickPause", {"Pause", "pause"}}};
    for (const auto &child : getChildren()) {
        auto button = vstd::cast<CButton>(child);
        if (!button)
            continue;
        auto entry = dockLabels.find(button->getClick());
        if (entry != dockLabels.end())
            button->setText(entry->second.first + "  " +
                            preferences["bindings"].value(entry->second.second, std::string{}));
    }
    const bool compact = gui->getWidth() < 1200 * scale;
    int dockWidth = static_cast<int>(240 * scale);
    int dockHeight = static_cast<int>(240 * scale);
    if (compact) {
        dockWidth = std::max(1, gui->getWidth() - static_cast<int>(220 * std::max(1.0, gui->getHeight() / 1080.0)));
        const int controlWidth = dockWidth / 4;
        dockHeight = UiTheme::scaled(gui, 48);
        for (const auto &child : getChildren()) {
            if (auto button = vstd::cast<CButton>(child))
                dockHeight = std::max(dockHeight,
                                      text->measureText(button->getText(), std::max(1, controlWidth - pad * 2)).second +
                                          UiTheme::scaled(gui, 16));
        }
        getLayout()->setRuntimeRect(0, gui->getHeight() - dockHeight, dockWidth, dockHeight);
        const std::map<std::string, int> order{
            {"clickInventory", 0}, {"clickJournal", 1}, {"clickCharacter", 2}, {"clickPause", 3}};
        for (const auto &child : getChildren()) {
            if (auto button = vstd::cast<CButton>(child); button && order.contains(button->getClick()))
                button->getLayout()->setRuntimeRect(order.at(button->getClick()) * controlWidth, 0, controlWidth,
                                                    dockHeight);
        }
    } else {
        getLayout()->setRuntimeRect(gui->getWidth() - dockWidth, 0, dockWidth, dockHeight);
        for (const auto &child : getChildren())
            if (child->getLayout())
                child->getLayout()->clearRuntimeRect();
    }
    int start = static_cast<int>(336 * scale);
    int width = std::max(1, gui->getWidth() - start - dockWidth - pad * 2);
    int headerTop = pad;
    if (compact) {
        start = pad;
        width = std::max(1, gui->getWidth() - pad * 2);
        headerTop = std::max(UiTheme::scaled(gui, 44),
                             text->measureText("HP 999 / 999", 0, "small").second + UiTheme::scaled(gui, 16)) +
                    8;
    }
    auto header = CUtil::rect(start, headerTop, width, static_cast<int>(64 * scale));
    const auto mapName = map->getMapName();
    const auto location =
        map->getLabel().empty() ? (mapName.empty() ? "Random map" : vstd::camel(mapName)) : map->getLabel();
    const auto locationLine = location + " · Elevation " + std::to_string(player->getCoords().z) +
                              (compact ? " · Level " + std::to_string(player->getLevel()) + " · " +
                                             std::to_string(player->getGold()) + " gold"
                                       : "");
    if (compact)
        header->h = text->measureText(locationLine, std::max(1, width - pad * 2)).second + pad * 2;
    UiTheme::fill(gui->getRenderer(), *header, UiTheme::Background);
    text->drawTextStyled(locationLine, UiTheme::inset(header, pad), "body", UiTheme::Text);
    const auto tracked = player->getStringProperty("uiTrackedQuestId");
    for (const auto &quest : player->getQuests()) {
        if (quest && quest->getName() == tracked) {
            auto summary = quest->getObjective();
            if (compact && summary.size() > 40) {
                size_t end = 40;
                while (end > 0 && (static_cast<unsigned char>(summary[end]) & 0xc0) == 0x80)
                    --end;
                summary = summary.substr(0, end) + "…";
            }
            const auto body = "Objective: " + summary;
            const int objectiveHeight = text->measureText(body, std::max(1, width - pad * 2)).second + pad * 2;
            auto objective = CUtil::rect(start, header->y + header->h + 4, width,
                                         compact ? objectiveHeight : UiTheme::scaled(gui, 84));
            UiTheme::fill(gui->getRenderer(), *objective, UiTheme::Background);
            text->drawTextStyled(body, UiTheme::inset(objective, pad), "body", UiTheme::Text);
            break;
        }
    }
    if (!compact) {
        auto identity = CUtil::rect(pad, static_cast<int>(142 * scale), static_cast<int>(300 * scale),
                                    static_cast<int>(48 * scale));
        UiTheme::fill(gui->getRenderer(), *identity, UiTheme::Background);
        text->drawTextStyled("Level " + std::to_string(player->getLevel()) + " · " + std::to_string(player->getGold()) +
                                 " gold",
                             identity, "body", UiTheme::Accent, true);
    }
    const auto recent = gui->getRecentNotification();
    if (!recent.empty()) {
        const int available =
            std::min(UiTheme::scaled(gui, 740), std::max(1, gui->getWidth() - UiTheme::scaled(gui, 280)));
        const int height =
            std::min(UiTheme::scaled(gui, 164), text->measureText(recent, available - pad * 2).second + pad * 2);
        auto feed = CUtil::rect(pad, gui->getHeight() - height - pad - (compact ? dockHeight : 0), available, height);
        UiTheme::fill(gui->getRenderer(), *feed, UiTheme::Background);
        UiTheme::stroke(gui->getRenderer(), *feed, UiTheme::Border);
        text->drawTextStyled(recent, UiTheme::inset(feed, pad), "body", UiTheme::Text);
    }
}

std::shared_ptr<CMapStringString> CSideBar::getPanelKeys() { return panelKeys; }

void CSideBar::setPanelKeys(std::shared_ptr<CMapStringString> _panelKeys) { this->panelKeys = _panelKeys; }

void CSideBar::flipPanel(std::shared_ptr<CGui> gui, std::string panel) {
    for (auto val : panelKeys->getValues()) {
        if (val.second == panel) {
            gui->getGame()->getGuiHandler()->flipPanel(panel, val.first);
        }
    }
}

bool CSideBar::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        if (i == SDLK_ESCAPE) {
            clickPause(sharedPtr);
            return true;
        }
        for (auto val : panelKeys->getValues()) {
            if (i == val.first[0]) {
                flipPanel(sharedPtr, val.second);
                return true;
            }
        }
    }
    return false;
}
