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
#pragma once

#include "CGamePanel.h"
#include "object/CPlayer.h"

class CGameInventoryPanel : public CGamePanel {
    V_META(
        CGameInventoryPanel, CGamePanel,
        V_METHOD(CGameInventoryPanel, inventoryCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
        V_METHOD(CGameInventoryPanel, inventoryCallback, void, std::shared_ptr<CGui>, int,
                 std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, inventoryRightClickCallback, bool, std::shared_ptr<CGui>, int,
                 std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, inventorySelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, inventoryDragStart, bool, std::shared_ptr<CGui>, int,
                 std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, inventoryDropValidate, bool, std::shared_ptr<CGui>, int,
                 std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, inventoryDrop, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, equippedCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
        V_METHOD(CGameInventoryPanel, equippedCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, equippedDragStart, bool, std::shared_ptr<CGui>, int,
                 std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, equippedDropValidate, bool, std::shared_ptr<CGui>, int,
                 std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, equippedDrop, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
        V_METHOD(CGameInventoryPanel, equippedSelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>))

  public:
    CGameInventoryPanel();

    CListView::collection_pointer inventoryCollection(std::shared_ptr<CGui> gui);

    void inventoryCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool inventoryRightClickCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    bool inventoryDragStart(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    bool inventoryDropValidate(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    void inventoryDrop(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    CListView::collection_pointer equippedCollection(std::shared_ptr<CGui> gui);

    void equippedCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool equippedDragStart(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    bool equippedDropValidate(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    void equippedDrop(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    bool equippedSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

  private:
    std::weak_ptr<CItem> selectedInventory;
    std::weak_ptr<CItem> selectedEquipped;

    bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) override;
};
