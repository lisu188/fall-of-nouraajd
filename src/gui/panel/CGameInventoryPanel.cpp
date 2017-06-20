

#include "CGameInventoryPanel.h"
#include "gui/CGui.h"

void CGameInventoryPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    SDL_RenderFillRect(gui->getRenderer(), pRect.get());
    int index = 0;
    for (std::shared_ptr<CItem> item:gui->getGame()->getMap()->getPlayer()->getItems()) {
        SDL_Rect location;
        location.x = gui->getTileSize() * (index % xInv) + pRect->x;
        location.y = gui->getTileSize() * (index / xInv) + pRect->y;
        location.w = gui->getTileSize();
        location.h = gui->getTileSize();
        item->getAnimationObject()->render(gui, &location, i);
        if (item == selected.lock()) {
            drawSelection(gui, &location, selectionBarThickness);
        }
        index++;
    }
    for (auto it:gui->getGame()->getMap()->getPlayer()->getEquipped()) {
        SDL_Rect location;
        std::string slotName = it.first;
        index = vstd::to_int(slotName).first;

        location.x = gui->getTileSize() * (index % 4) + pRect->x + 600;
        location.y = gui->getTileSize() * (index / 4) + pRect->y;
        location.w = gui->getTileSize();
        location.h = gui->getTileSize();
        it.second->getAnimationObject()->render(gui, &location, i);

        if (selected.lock() && gui->getGame()->getSlotConfiguration()->canFit(slotName, selected.lock())) {
            drawSelection(gui, &location, selectionBarThickness / 2);
        }
    }
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
    }
}


CGameInventoryPanel::CGameInventoryPanel() {

}

void CGameInventoryPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    if (isInInventory(gui, x, y)) {
        std::set<std::shared_ptr<CItem>> items = gui->getGame()->getMap()->getPlayer()->getItems();
        unsigned int clickedIndex = (unsigned int) (x / gui->getTileSize() + ((y / gui->getTileSize()) * xInv));
        if (clickedIndex < items.size()) {
            auto newSelection = vstd::get(items, clickedIndex);
            if (selected.lock() != newSelection) {
                selected = newSelection;
            } else {
                selected.reset();
            }

        }
    }
}

bool CGameInventoryPanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return x < gui->getTileSize() * xInv && y < gui->getTileSize() * yInv;
}
