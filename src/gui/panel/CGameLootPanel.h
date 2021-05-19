/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

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
#include "object/CItem.h"
#include "gui/CGui.h"
#include "CListView.h"

class CGameLootPanel : public CGamePanel {
V_META(CGameLootPanel, CGamePanel,
       V_PROPERTY(CGameLootPanel, std::set<std::shared_ptr<CItem>>, items, getItems, setItems),
       V_PROPERTY(CGameLootPanel, std::shared_ptr<CCreature>, creature, getCreature, setCreature),
       V_METHOD(CGameLootPanel, itemsCollection, CListView::collection_pointer, std::shared_ptr<CGui>))
public:
    void setItems(std::set<std::shared_ptr<CItem>> items);

    std::set<std::shared_ptr<CItem>> getItems();

    CListView::collection_pointer itemsCollection(std::shared_ptr<CGui> gui);

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) override;

private:
    std::set<std::shared_ptr<CItem>> items;
    std::shared_ptr<CCreature> creature;
public:
    const std::shared_ptr<CCreature> &getCreature() const;

    void setCreature(const std::shared_ptr<CCreature> &creature);
};