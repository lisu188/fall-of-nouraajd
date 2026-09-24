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
#include "CGameLootPanel.h"
#include "CButton.h"
#include <algorithm>
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include <map>

void CGameLootPanel::setItems(const std::set<std::shared_ptr<CItem>> &_items) {
    items = _items;
    detailsOffset = 0;
}

CListView::collection_pointer CGameLootPanel::itemsCollection(const std::shared_ptr<CGui> &gui) {
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(items));
}

std::set<std::shared_ptr<CItem>> CGameLootPanel::getItems() { return items; }

bool CGameLootPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN && (i == SDLK_PAGEUP || i == SDLK_PAGEDOWN)) {
        detailsOffset = std::clamp(detailsOffset + (i == SDLK_PAGEUP ? -1 : 1) * std::max(1, detailsViewport.h - 24), 0,
                                   detailsMaximum);
        return true;
    }
    if (type == SDL_KEYDOWN) {
        if (i == SDLK_RETURN || i == SDLK_KP_ENTER) {
            close();
            return true;
        }
    }
    return CGamePanel::keyboardEvent(gui, type, i);
}

std::string CGameLootPanel::getRewardsText() const {
    std::map<std::string, int> quantities;
    for (const auto &item : items) {
        if (item) {
            quantities[item->getLabel()]++;
        }
    }
    if (quantities.empty()) {
        return "No items were found.\nContinue your journey.";
    }
    std::string text = "These rewards will be added to your inventory.\n\n";
    for (const auto &[label, quantity] : quantities) {
        text += std::to_string(quantity) + " x " + label + "\n";
    }
    return text;
}

void CGameLootPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    CGamePanel::renderObject(gui, rect, frameTime);
    if (!gui || !rect) {
        return;
    }
    const int padding = UiTheme::scaled(gui, 24);
    const int gap = UiTheme::scaled(gui, 8);
    const int width = std::max(1, rect->w - padding * 2);
    int footerTop = rect->h - padding;
    for (const auto &child : getChildren()) {
        auto button = vstd::cast<CButton>(child);
        if (!button || button->getStringProperty("click") != "collectRewards" || !button->getLayout()) {
            continue;
        }
        auto textManager = gui->getTextManager();
        const int buttonWidth = std::min(
            width, std::max(width / 3, textManager->measureText(button->getText(), 0, button->getTextRole()).first +
                                           UiTheme::scaled(gui, 32)));
        const int buttonHeight =
            std::max(UiTheme::scaled(gui, 40),
                     textManager
                             ->measureText(button->getText(), std::max(1, buttonWidth - UiTheme::scaled(gui, 16)),
                                           button->getTextRole())
                             .second +
                         UiTheme::scaled(gui, 16));
        footerTop -= buttonHeight;
        button->getLayout()->setRuntimeRect(rect->w - padding - buttonWidth, footerTop, buttonWidth, buttonHeight);
    }
    const int contentTop = getShellHeaderHeight(gui) + gap;
    for (const auto &child : getChildren()) {
        if (child->getStringProperty("render") == "renderRewards" && child->getLayout()) {
            child->getLayout()->setRuntimeRect(padding, contentTop, width, std::max(1, footerTop - gap - contentTop));
        }
    }
}

void CGameLootPanel::renderRewards(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (gui && rect) {
        const auto text = getRewardsText();
        detailLayout.update(gui, text, rect->w);
        const auto content = DetailViewport::contentRect(gui, rect, detailLayout.getContentHeight());
        detailsViewport = *content;
        detailsMaximum = std::max(0, detailLayout.getContentHeight() - content->h);
        detailsOffset = std::clamp(detailsOffset, 0, detailsMaximum);
        detailLayout.draw(gui, content, detailsOffset);
        DetailViewport::drawScrollHint(gui, rect, content, detailsOffset, detailsMaximum);
    }
}

void CGameLootPanel::collectRewards(std::shared_ptr<CGui> gui) { close(); }

const std::shared_ptr<CCreature> &CGameLootPanel::getCreature() const { return creature; }

void CGameLootPanel::setCreature(const std::shared_ptr<CCreature> &_creature) { creature = _creature; }

bool CGameLootPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
                                     int wheelY) {
    auto origin = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : nullptr;
    SDL_Point point{x + (origin ? origin->x : 0), y + (origin ? origin->y : 0)};
    if (!SDL_PointInRect(&point, &detailsViewport)) {
        return false;
    }
    detailsOffset =
        static_cast<int>(std::clamp(static_cast<long long>(detailsOffset) - static_cast<long long>(wheelY) * 72, 0LL,
                                    static_cast<long long>(detailsMaximum)));
    return true;
}
