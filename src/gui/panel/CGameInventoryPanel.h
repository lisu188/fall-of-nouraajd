/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

#include "object/CPlayer.h"
#include "CGamePanel.h"

class CGameInventoryPanel : public CGamePanel {
V_META(CGameInventoryPanel, CGamePanel,
       V_METHOD(CGameInventoryPanel, inventoryCollection,CListView::collection_pointer,
                std::shared_ptr<CGui>),
       V_METHOD(CGameInventoryPanel, inventoryCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameInventoryPanel, inventorySelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameInventoryPanel, equippedCollection,CListView::collection_pointer,
                std::shared_ptr<CGui>),
       V_METHOD(CGameInventoryPanel, equippedCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameInventoryPanel, equippedSelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>))

public:
    CGameInventoryPanel();

    CListView::collection_pointer inventoryCollection(std::shared_ptr<CGui> gui);

    void inventoryCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    CListView::collection_pointer equippedCollection(std::shared_ptr<CGui> gui);

    void equippedCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool equippedSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    void refreshViews();

private:
    std::weak_ptr<CItem> selectedInventory;
    std::weak_ptr<CItem> selectedEquipped;
};

