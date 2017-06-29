

#include "CGameInventoryPanel.h"
#include "gui/CGui.h"

void CGameInventoryPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    SDL_RenderFillRect(gui->getRenderer(), pRect.get());
    drawInventory(gui, pRect, i);
    drawEquipped(gui, pRect, i);
}

void CGameInventoryPanel::drawEquipped(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr<SDL_Rect> location = std::make_shared<SDL_Rect>(*pRect.get());
    location->x += 600;

    drawCollection(gui, location,
                   [this, gui]() {
                       return gui->getGame()->getMap()->getPlayer()->getEquipped();
                   }, 4, 4, gui->getTileSize(),
                   [this, gui](auto ob, int prevIndex) {
                       return vstd::to_int(ob.first).first;
                   },
                   [this, gui, frameTime](auto item, auto loc) {
                       item.second->getAnimationObject()->render(gui, loc, frameTime);
                   }, [this, gui](auto object) {
                return selected.lock() &&
                       gui->getGame()->getSlotConfiguration()->canFit(object.first, selected.lock());
            }, [this](auto g, auto l, auto t) {
                this->drawSelection(g, l, t);
            }, selectionBarThickness / 2);
}

void CGameInventoryPanel::drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    drawCollection(gui, pRect,
                   [this, gui]() {
                       return gui->getGame()->getMap()->getPlayer()->getInInventory();
                   }, xInv, yInv, gui->getTileSize(),
                   [this, gui](auto item, int prevIndex) {
                       return prevIndex + 1;
                   },
                   [this, gui, frameTime](auto item, auto loc) {
                       item->getAnimationObject()->render(gui, loc, frameTime);
                   }, [this, gui](auto item) {
                return item == selected.lock();
            }, [this](auto g, auto l, auto t) {
                this->drawSelection(g, l, t);
            }, selectionBarThickness);
}

void CGameInventoryPanel::drawSelection(std::shared_ptr<CGui> gui, SDL_Rect *location, int thickness) {
    SDL_SetRenderDrawColor(gui->getRenderer(), YELLOW);
    SDL_Rect tmp = {location->x, location->y, thickness, location->h};
    SDL_Rect tmp2 = {location->x, location->y, location->w, thickness};
    SDL_Rect tmp3 = {location->x, location->y + location->h - thickness, location->w,
                     thickness};
    SDL_Rect tmp4 = {location->x + location->w - thickness, location->y, thickness,
                     location->h};
    SDL_RenderFillRect(gui->getRenderer(), &tmp);
    SDL_RenderFillRect(gui->getRenderer(), &tmp2);
    SDL_RenderFillRect(gui->getRenderer(), &tmp3);
    SDL_RenderFillRect(gui->getRenderer(), &tmp4);
}


void CGameInventoryPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_i) {
        gui->removeObject(this->ptr<CGameInventoryPanel>());
    } else if (i == SDLK_RETURN) {
        handleEnter(gui);
    }
}


CGameInventoryPanel::CGameInventoryPanel() {

}

void CGameInventoryPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    if (isInInventory(gui, x, y)) {
        handleInventoryClick(gui, x, y);
    } else if (isInEquipped(gui, x, y)) {
        handleEquippedClick(gui, x, y);
    }
}

void CGameInventoryPanel::handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y) {
    onClicked([this, gui]() {
        return gui->getGame()->getMap()->getPlayer()->getItems();
    }, x, y, xInv, yInv, gui->getTileSize(), [this, gui](auto item, int prevIndex) {
        return prevIndex + 1;
    }, [this, gui](auto newSelection) {
        if (selected.lock() != newSelection) {
            selected = newSelection;
        } else {
            selected.reset();
        }
    });

}

void CGameInventoryPanel::handleEquippedClick(std::shared_ptr<CGui> gui, int x, int y) {
    onClicked([this, gui]() {
        return gui->getGame()->getMap()->getPlayer()->getEquipped();
    }, x - 600, y, 4, 4, gui->getTileSize(), [this, gui](auto ob, int prevIndex) {
        return vstd::to_int(ob.first).first;
    }, [this, gui](auto newSelection) {
        if (selected.lock() &&
            gui->getGame()->getSlotConfiguration()->canFit(newSelection.first, selected.lock())) {
            gui->getGame()->getMap()->getPlayer()->equipItem(newSelection.first, selected.lock());
            selected.reset();
        }
    });

}

bool CGameInventoryPanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return x < gui->getTileSize() * xInv && y < gui->getTileSize() * yInv;
}

bool CGameInventoryPanel::isInEquipped(std::shared_ptr<CGui> shared_ptr, int x, int y) {
    return x >= 600 && y < 200;//TODO: do not hardcode this
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
