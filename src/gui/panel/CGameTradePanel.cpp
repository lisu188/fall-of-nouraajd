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
#include "CGameTradePanel.h"
#include "gui/CTextureCache.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

CListView::collection_pointer CGameTradePanel::inventoryCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(
            gui->getGame()->getMap()->getPlayer()->getItems()));
}

void
CGameTradePanel::inventoryCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    this->selectInventory(vstd::cast<CItem>(_newSelection));
    refreshViews();
}

bool CGameTradePanel::inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return vstd::ctn(selectedInventory, object, [](auto a, auto b) { return a == b.lock(); });
}

CListView::collection_pointer CGameTradePanel::marketCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(
            market->getItems()));
}

void CGameTradePanel::marketCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    this->selectMarket(vstd::cast<CItem>(_newSelection));
    refreshViews();
}

bool CGameTradePanel::marketSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return vstd::ctn(selectedMarket, object, [](auto a, auto b) { return a == b.lock(); });
}


void CGameTradePanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int i) {
    CGamePanel::renderObject(gui, rect, i);
    //TODO: move this to CWidgets
    gui->getTextManager()->drawTextCentered(vstd::str(getTotalBuyCost()), rect->x + 200, rect->y, 200, 200);
    gui->getTextManager()->drawTextCentered(vstd::str(getTotalSellCost()), rect->x + 400, rect->y, 200, 200);
}

bool CGameTradePanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        //TODO: get rid of this
        if (i == SDLK_SPACE) {
            gui->removeChild(this->ptr<CGameTradePanel>());
        } else if (i == SDLK_RETURN) {
            handleEnter(gui);
        }
    }
    return true;
}


CGameTradePanel::CGameTradePanel() {

}

void CGameTradePanel::handleEnter(std::shared_ptr<CGui> gui) {
    if (canPlayerAfford(gui)) {
        for (auto item:selectedInventory) {
            market->buyItem(gui->getGame()->getMap()->getPlayer(), item.lock());
        }
        for (auto item:selectedMarket) {
            market->sellItem(gui->getGame()->getMap()->getPlayer(), item.lock());
        }
        selectedMarket.clear();
        selectedInventory.clear();
    }
}

bool CGameTradePanel::canPlayerAfford(std::shared_ptr<CGui> gui) {
    return getTotalSellCost() - getTotalBuyCost() <= gui->getGame()->getMap()->getPlayer()->getGold();
}

int CGameTradePanel::getTotalSellCost() {
    return vstd::functional::sum<int>(selectedMarket, [this](auto item) {
        return market->getSellCost(item.lock());
    });
}

int CGameTradePanel::getTotalBuyCost() {
    return vstd::functional::sum<int>(selectedInventory, [this](auto item) {
        return market->getBuyCost(item.lock());
    });
}

void CGameTradePanel::selectMarket(std::weak_ptr<CItem> selection) {
    if (selection.lock()) {
        if (vstd::ctn(selectedMarket, selection, [](auto a, auto b) { return a.lock() == b.lock(); })) {
            vstd::erase(selectedMarket, selection, [](auto a, auto b) { return a.lock() == b.lock(); });
        } else {
            selectedMarket.push_back(selection);
        }
    }
}

void CGameTradePanel::selectInventory(std::weak_ptr<CItem> selection) {
    if (selection.lock() && !selection.lock()->hasTag("quest")) {
        if (vstd::ctn(selectedInventory, selection, [](auto a, auto b) { return a.lock() == b.lock(); })) {
            vstd::erase(selectedInventory, selection, [](auto a, auto b) { return a.lock() == b.lock(); });
        } else {
            selectedInventory.push_back(selection);
        }
    }
}

void CGameTradePanel::setMarket(std::shared_ptr<CMarket> _market) {
    market = _market;
}

std::shared_ptr<CMarket> CGameTradePanel::getMarket() {
    return market;
}
