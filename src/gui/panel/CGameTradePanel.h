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
//TODO: allow selecting couple of grouped objects
       V_PROPERTY(CGameTradePanel, std::shared_ptr<CMarket>, market, getMarket, setMarket),
       V_METHOD(CGameTradePanel, inventoryCollection, CListView::collection_pointer,
                std::shared_ptr<CGui>),
       V_METHOD(CGameTradePanel, inventoryCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameTradePanel, inventorySelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameTradePanel, marketCollection, CListView::collection_pointer,
                std::shared_ptr<CGui>),
       V_METHOD(CGameTradePanel, marketCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameTradePanel, marketSelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameTradePanel, renderSellCost, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
       V_METHOD(CGameTradePanel, renderBuyCost, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
       V_METHOD(CGameTradePanel, finalizeSell, void, std::shared_ptr<CGui>),
       V_METHOD(CGameTradePanel, finalizeBuy, void, std::shared_ptr<CGui>))

public:
    CGameTradePanel();

    std::shared_ptr<CMarket> getMarket();

    void setMarket(std::shared_ptr<CMarket> _market);

    CListView::collection_pointer inventoryCollection(std::shared_ptr<CGui> gui);

    void inventoryCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    CListView::collection_pointer marketCollection(std::shared_ptr<CGui> gui);

    void marketCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool marketSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    void renderSellCost(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i);

    void renderBuyCost(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i);

    void finalizeSell(std::shared_ptr<CGui> shared_ptr);

    void finalizeBuy(std::shared_ptr<CGui> shared_ptr);

private:
    std::shared_ptr<CMarket> market;
    std::list<std::weak_ptr<CItem>> selectedInventory;
    std::list<std::weak_ptr<CItem>> selectedMarket;

    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

    void selectMarket(std::weak_ptr<CItem> selection);

    void selectInventory(std::weak_ptr<CItem> selection);

    int getTotalSellCost();

    int getTotalBuyCost();

    //TODO: should be not unique collection. items get merged
    std::set<std::string> getItemNames(std::list<std::weak_ptr<CItem>> items);
};

