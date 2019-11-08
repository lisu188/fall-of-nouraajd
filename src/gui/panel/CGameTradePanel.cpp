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


void CGameTradePanel::renderObject(std::shared_ptr<CGui> gui, int i) {
    auto pRect = getRect();
    drawInventory(gui, pRect, i);
    drawMarket(gui, pRect, i);
    gui->getTextManager()->drawTextCentered(vstd::str(getTotalBuyCost()), pRect->x + 200, pRect->y, 200, 200);
    gui->getTextManager()->drawTextCentered(vstd::str(getTotalSellCost()), pRect->x + 400, pRect->y, 200, 200);
}

void CGameTradePanel::drawMarket(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr<SDL_Rect> location = std::make_shared<SDL_Rect>(*pRect.get());//cloning
    location->x += 600;

    marketView->drawCollection(gui, location, frameTime);
}

void CGameTradePanel::drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    inventoryView->drawCollection(gui, pRect, frameTime);
}

bool CGameTradePanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (i == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameTradePanel>());
    } else if (i == SDLK_RETURN) {
        handleEnter(gui);
    }
    return true;
}


CGameTradePanel::CGameTradePanel() {
    inventoryView = std::make_shared<
            CListView<
                    std::set<
                            std::shared_ptr<
                                    CItem>>>>
            (
                    xInv, yInv, 50, true, selectionBarThickness)->withCollection(
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getInInventory();
            })->withCallback(
            [this](std::shared_ptr<CGui> gui, int index, auto newSelection) {
                this->selectInventory(newSelection);
            })->withSelect(
            [this](std::shared_ptr<CGui> gui, int index, auto item) {
                return vstd::ctn(selectedInventory, item, [](auto a, auto b) { return a == b.lock(); });
            });

    marketView = std::make_shared<
            CListView<
                    std::set<
                            std::shared_ptr<
                                    CItem>>>>
            (
                    xInv, yInv, 50, true, selectionBarThickness)->withCollection(
            [this](std::shared_ptr<CGui> gui) {
                return market->getItems();
            })->withCallback(
            [this](std::shared_ptr<CGui> gui, int index, auto newSelection) {
                this->selectMarket(newSelection);
            })->withSelect(
            [this](std::shared_ptr<CGui> gui, int index, auto item) {
                return vstd::ctn(selectedMarket, item, [](auto a, auto b) { return a == b.lock(); });
            });
}

bool CGameTradePanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y)(
        std::shared_ptr<CGui> gui, int x, int y) {
    if (isInInventory(gui, x, y)) {
        handleInventoryClick(gui, x, y);
    } else if (isInMarket(gui, x, y)) {
        handleMarketClick(gui, x, y);
    }
    return true;
}

void CGameTradePanel::handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y) {
    inventoryView->onClicked(gui, x, y);
}

void CGameTradePanel::handleMarketClick(std::shared_ptr<CGui> gui, int x, int y) {
    marketView->onClicked(gui, x - 600, y);
}

bool CGameTradePanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return x < gui->getTileSize() * xInv && y < gui->getTileSize() * yInv;
}

bool CGameTradePanel::isInMarket(std::shared_ptr<CGui> gui, int x, int y) {
    return x >= getWidth() - gui->getTileSize() * 4 && y < gui->getTileSize() * 4;
}

int CGameTradePanel::getXInv() {
    return xInv;
}

void CGameTradePanel::setXInv(int _xInv) {
    CGameTradePanel::xInv = _xInv;
}

int CGameTradePanel::getYInv() {
    return yInv;
}

void CGameTradePanel::setYInv(int _yInv) {
    CGameTradePanel::yInv = _yInv;
}

int CGameTradePanel::getSelectionBarThickness() {
    return selectionBarThickness;
}

void CGameTradePanel::setSelectionBarThickness(int _selectionBarThickness) {
    CGameTradePanel::selectionBarThickness = _selectionBarThickness;
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
