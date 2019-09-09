//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#pragma once

#include "object/CPlayer.h"
#include "CGamePanel.h"

//TODO: dynamic load of layout from slot configuration
//TODO: make x y adequate to panel size
//TODO: make icons on empty inventory slots
class CGameInventoryPanel : public CGamePanel {
V_META(CGameInventoryPanel, CGamePanel,
       V_PROPERTY(CGameInventoryPanel, int, xInv, getXInv, setXInv),
       V_PROPERTY(CGameInventoryPanel, int, yInv, getYInv, setYInv),
       V_PROPERTY(CGameInventoryPanel, int, selectionBarThickness, getSelectionBarThickness, setSelectionBarThickness))

public:
    CGameInventoryPanel();

    int getXInv();

    void setXInv(int xInv);

    int getYInv();

    void setYInv(int yInv);

    int getSelectionBarThickness();

    void setSelectionBarThickness(int selectionBarThickness);

private:
    std::shared_ptr<CListView<std::set<std::shared_ptr<CItem>>>> inventoryView;
    std::shared_ptr<CListView<CItemMap>> equippedView;

    int xInv = 4;
    int yInv = 4;
    int selectionBarThickness = 5;
    std::weak_ptr<CItem> selectedInventory;
    std::weak_ptr<CItem> selectedEquipped;

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

    void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) override;

    void drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawEquipped(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInInventory(std::shared_ptr<CGui> x, int y, int i1);

    bool isInEquipped(std::shared_ptr<CGui> shared_ptr, int x, int y);

    void handleEquippedClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

};

