

#include "CGameTradePanel.h"
#include "gui/CTextureCache.h"
#include "core/CGame.h"
#include "core/CMap.h"

void CGameTradePanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    drawInventory(gui, pRect, i);
    drawMarket(gui, pRect, i);
}

void CGameTradePanel::drawMarket(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr<SDL_Rect> location = std::make_shared<SDL_Rect>(*pRect.get());
    location->x += 600;

    marketView->drawCollection(gui, location,
                               [this, gui](int index, auto item) {
                                   return vstd::ctn(selectedMarket, item);
                               }, selectionBarThickness, frameTime);
}

void CGameTradePanel::drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    inventoryView->drawCollection(gui, pRect,
                                  [this, gui](int index, auto item) {
                                      return vstd::ctn(selectedInventory, item);
                                  }, selectionBarThickness, frameTime);
}

void CGameTradePanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameTradePanel>());
    } else if (i == SDLK_RETURN) {
        handleEnter(gui);
    }
}


CGameTradePanel::CGameTradePanel() {
    inventoryView = std::make_shared<
            CListView<
                    std::set<
                            std::shared_ptr<
                                    CItem>>>>(
            xInv, yInv,
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getInInventory();
            },
            [](auto ob, int prevIndex) {
                return prevIndex + 1;
            },
            [this](std::shared_ptr<CGui> gui, auto newSelection) {
                this->selectInventory(newSelection);
            },
            [](auto gui, auto item, auto loc, auto frameTime) {
                item->getAnimationObject()->render(gui, loc, frameTime);
            },
            50,
            true);

    marketView = std::make_shared<
            CListView<
                    std::set<
                            std::shared_ptr<
                                    CItem>>>>(
            xInv, yInv,
            [this](std::shared_ptr<CGui> gui) {
                return market->getItems();
            },
            [](auto ob, int prevIndex) {
                return prevIndex + 1;
            },
            [this](std::shared_ptr<CGui> gui, auto newSelection) {
                this->selectMarket(newSelection);
            },
            [](auto gui, auto item, auto loc, auto frameTime) {
                item->getAnimationObject()->render(gui, loc, frameTime);
            },
            50,
            true);
}

void CGameTradePanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    if (isInInventory(gui, x, y)) {
        handleInventoryClick(gui, x, y);
    } else if (isInMarket(gui, x, y)) {
        handleMarketClick(gui, x, y);
    }
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
    return x >= getXSize() - gui->getTileSize() * 4 && y < gui->getTileSize() * 4;
}

int CGameTradePanel::getXInv() {
    return xInv;
}

void CGameTradePanel::setXInv(int xInv) {
    CGameTradePanel::xInv = xInv;
}

int CGameTradePanel::getYInv() {
    return yInv;
}

void CGameTradePanel::setYInv(int yInv) {
    CGameTradePanel::yInv = yInv;
}

int CGameTradePanel::getSelectionBarThickness() {
    return selectionBarThickness;
}

void CGameTradePanel::setSelectionBarThickness(int selectionBarThickness) {
    CGameTradePanel::selectionBarThickness = selectionBarThickness;
}

void CGameTradePanel::handleEnter(std::shared_ptr<CGui> gui) {
    vstd::fail_if(selectedMarket.size() > 0 && selectedInventory.size() > 0, "Both selections greater than zero!");
    if (selectedInventory.size() > 0) {
        for (auto item:selectedInventory) {
            market->buyItem(gui->getGame()->getMap()->getPlayer(), item);
        }
        selectedInventory.clear();
    }
    if (selectedMarket.size() > 0) {
        if (vstd::functional::sum<int>(selectedMarket, [this](auto item) {
            return market->getSellCost(item);
        }) > gui->getGame()->getMap()->getPlayer()->getGold()) {
            vstd::logger::debug("Cannot afford all selected items!");
        } else {
            for (auto item:selectedMarket) {
                market->sellItem(gui->getGame()->getMap()->getPlayer(), item);
            }
        }
        selectedMarket.clear();
    }
}

void CGameTradePanel::selectMarket(std::shared_ptr<CItem> selection) {
    selectedInventory.clear();
    if (vstd::ctn(selectedMarket, selection)) {
        selectedMarket.erase(selection);
    } else {
        selectedMarket.insert(selection);
    }
}

void CGameTradePanel::selectInventory(std::shared_ptr<CItem> selection) {
    selectedMarket.clear();
    if (vstd::ctn(selectedInventory, selection)) {
        selectedInventory.erase(selection);
    } else {
        selectedInventory.insert(selection);
    }
}

void CGameTradePanel::setMarket(std::shared_ptr<CMarket> _market) {
    market = _market;
}

std::shared_ptr<CMarket> CGameTradePanel::getMarket() {
    return market;
}
