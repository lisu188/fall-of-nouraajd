

#include "CGameInventoryPanel.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"
#include "core/CGame.h"
#include "core/CMap.h"

void CGameInventoryPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    drawInventory(gui, pRect, i);
    drawEquipped(gui, pRect, i);
}

void CGameInventoryPanel::drawEquipped(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr<SDL_Rect> location = std::make_shared<SDL_Rect>(*pRect.get());//this a clone, do not remove
    location->x += 600;

    itemsView->drawCollection(gui, location,
                              [gui, frameTime](auto item, auto loc) {
                                  item.second->getAnimationObject()->render(gui, loc, frameTime);
                              },
                              [this, gui](auto
                                          object) {
                                  return selected.lock() &&
                                         gui->getGame()->getSlotConfiguration()->canFit(object.first, selected.lock());
                              }, selectionBarThickness / 2);
}

void CGameInventoryPanel::drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    inventoryView->drawCollection(gui, pRect,
                                  [gui, frameTime](auto item, auto loc) {
                                      item->getAnimationObject()->render(gui, loc, frameTime);
                                  },
                                  [this](auto object) {
                                      return selected.lock() = object;
                                  }, selectionBarThickness);
}

void CGameInventoryPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_i) {
        gui->removeObject(this->ptr<CGameInventoryPanel>());
    } else if (i == SDLK_RETURN) {
        handleEnter(gui);
    }
}


CGameInventoryPanel::CGameInventoryPanel() {
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
                if (selected.lock() != newSelection) {
                    selected = newSelection;
                } else {
                    selected.reset();
                }
            },
            true);

    itemsView = std::make_shared<
            CListView<CItemMap>>(
            xInv, yInv,
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getEquipped();
            },
            [](auto ob, int prevIndex) {
                return vstd::to_int(ob.first).first;
            },
            [this](std::shared_ptr<CGui> gui, auto newSelection) {
                if (selected.lock() &&
                    gui->getGame()->getSlotConfiguration()->canFit(newSelection.first, selected.lock())) {
                    gui->getGame()->getMap()->getPlayer()->equipItem(newSelection.first, selected.lock());
                    selected.reset();
                }
            },
            false);
}

void CGameInventoryPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    if (isInInventory(gui, x, y)) {
        handleInventoryClick(gui, x, y);
    } else if (isInEquipped(gui, x, y)) {
        handleEquippedClick(gui, x, y);
    }
}

void CGameInventoryPanel::handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y) {
    inventoryView->onClicked(gui, x, y);
}

void CGameInventoryPanel::handleEquippedClick(std::shared_ptr<CGui> gui, int x, int y) {
    itemsView->onClicked(gui, x - 600, y);

}

bool CGameInventoryPanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return x < gui->getTileSize() * xInv && y < gui->getTileSize() * yInv && !isInEquipped(gui, x, y);
}

bool CGameInventoryPanel::isInEquipped(std::shared_ptr<CGui> gui, int x, int y) {
    return x >= getXSize() - gui->getTileSize() * xInv && y < gui->getTileSize() * yInv && !isInInventory(gui, x, y);
}

int CGameInventoryPanel::getXInv() {
    return xInv;
}

void CGameInventoryPanel::setXInv(int xInv) {
    CGameInventoryPanel::xInv = xInv;
}

int CGameInventoryPanel::getYInv() {
    return yInv;
}

void CGameInventoryPanel::setYInv(int yInv) {
    CGameInventoryPanel::yInv = yInv;
}

int CGameInventoryPanel::getSelectionBarThickness() {
    return selectionBarThickness;
}

void CGameInventoryPanel::setSelectionBarThickness(int selectionBarThickness) {
    CGameInventoryPanel::selectionBarThickness = selectionBarThickness;
}

void CGameInventoryPanel::handleEnter(std::shared_ptr<CGui> gui) {
    if (selected.lock()) {
        auto fit = gui->getGame()->getSlotConfiguration()->getFittingSlots(selected.lock());
        if (fit.size() == 0) {
            gui->getGame()->getMap()->getPlayer()->useItem(selected.lock());
            selected.reset();
        } else if (fit.size() == 1) {
            gui->getGame()->getMap()->getPlayer()->equipItem((vstd::get(fit, 0)), selected.lock());
            selected.reset();
        }
    }
}
