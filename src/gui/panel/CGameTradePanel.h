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


class CGameTradePanel : public CGamePanel {
V_META(CGameTradePanel, CGamePanel,
//TODO: unify this with CGameInventoryPanel
//TODO: stacking of same type objects
       V_PROPERTY(CGameTradePanel, int, xInv, getXInv, setXInv),
       V_PROPERTY(CGameTradePanel, int, yInv, getYInv, setYInv),
       V_PROPERTY(CGameTradePanel, int, selectionBarThickness, getSelectionBarThickness, setSelectionBarThickness),
       V_PROPERTY(CGameTradePanel, std::shared_ptr<CMarket>, market, getMarket, setMarket))

public:
    CGameTradePanel();

    int getXInv();

    void setXInv(int xInv);

    int getYInv();

    void setYInv(int yInv);

    int getSelectionBarThickness();

    void setSelectionBarThickness(int selectionBarThickness);

    std::shared_ptr<CMarket> getMarket();

    void setMarket(std::shared_ptr<CMarket> _market);

private:
    std::shared_ptr<CListView<std::set<std::shared_ptr<CItem>>>> inventoryView;
    std::shared_ptr<CListView<std::set<std::shared_ptr<CItem>>>> marketView;

    int xInv = 4;
    int yInv = 4;
    int selectionBarThickness = 5;

    std::shared_ptr<CMarket> market;
    std::list<std::weak_ptr<CItem>> selectedInventory;
    std::list<std::weak_ptr<CItem>> selectedMarket;

    virtual bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

    virtual bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) override;

    virtual void renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    void drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawMarket(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInInventory(std::shared_ptr<CGui> x, int y, int i1);

    bool isInMarket(std::shared_ptr<CGui> shared_ptr, int x, int y);

    void handleMarketClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleEnter(std::shared_ptr<CGui> shared_ptr);

    void selectMarket(std::weak_ptr<CItem> selection);

    void selectInventory(std::weak_ptr<CItem> selection);

    int getTotalSellCost();

    int getTotalBuyCost();

    bool canPlayerAfford(std::shared_ptr<CGui> gui);
};

