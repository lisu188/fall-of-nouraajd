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
#pragma once

#include "CGamePanel.h"
#include "CListView.h"
#include "gui/CDetailViewport.h"
#include "gui/CGui.h"
#include "object/CItem.h"

class CGameLootPanel : public CGamePanel {
    V_META(CGameLootPanel, CGamePanel,
           V_PROPERTY(CGameLootPanel, std::set<std::shared_ptr<CItem>>, items, getItems, setItems),
           V_PROPERTY(CGameLootPanel, std::shared_ptr<CCreature>, creature, getCreature, setCreature),
           V_METHOD(CGameLootPanel, itemsCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
           V_METHOD(CGameLootPanel, renderRewards, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
           V_METHOD(CGameLootPanel, collectRewards, void, std::shared_ptr<CGui>))
  public:
    void setItems(const std::set<std::shared_ptr<CItem>> &_items);

    std::set<std::shared_ptr<CItem>> getItems();

    CListView::collection_pointer itemsCollection(const std::shared_ptr<CGui> &gui);

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) override;

    std::string getRewardsText() const;

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    void renderRewards(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void collectRewards(std::shared_ptr<CGui> gui);

    bool mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX, int wheelY) override;

  private:
    DetailViewport::Layout detailLayout;
    int detailsOffset = 0;
    int detailsMaximum = 0;
    SDL_Rect detailsViewport{};
    std::set<std::shared_ptr<CItem>> items;
    std::shared_ptr<CCreature> creature;

  public:
    const std::shared_ptr<CCreature> &getCreature() const;

    void setCreature(const std::shared_ptr<CCreature> &creature);
};
