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
#include "gui/panel/CListView.h"

class CGameFightPanel : public CGamePanel {
V_META(CGameFightPanel, CGamePanel,
       V_PROPERTY(CGameFightPanel, int, selectionBarThickness, getSelectionBarThickness, setSelectionBarThickness))

public:
    CGameFightPanel();

    int getSelectionBarThickness();

    void setSelectionBarThickness(int selectionBarThickness);

    std::shared_ptr<CInteraction> selectInteraction();

    std::shared_ptr<CCreature> getEnemy();

    void setEnemy(std::shared_ptr<CCreature> en);

private:
    std::shared_ptr<CListView> interactionsView;
    std::shared_ptr<CListView> itemsView;

    int selectionBarThickness = 5;
    std::weak_ptr<CCreature> enemy;
    std::weak_ptr<CInteraction> selected;
    std::weak_ptr<CItem> selectedItem;
    std::weak_ptr<CInteraction> finalSelected;

    void renderObject(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> rect, int i) override;

     bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) override;

    void drawInteractions(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawEnemy(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInInteractions(std::shared_ptr<CGui> x, int y, int i1);

    void handleInteractionsClick(std::shared_ptr<CGui> gui, int x, int y);

    bool isInInventory(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

    int tileSize = 50;//TODO: make property, requires later initialization when gui is accessible
    int getInventoryLocation(std::shared_ptr<CGui> gui);

    int getInteractionsLocation(std::shared_ptr<CGui> gui);
};

