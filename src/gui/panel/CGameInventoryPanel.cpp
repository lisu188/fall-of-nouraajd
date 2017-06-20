

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
        if (item->getName() == selected) {
            drawSelection(gui, &location);
        }
        index++;
    }
    for (auto it:gui->getGame()->getMap()->getPlayer()->getEquipped()) {
        SDL_Rect location;
        index = vstd::to_int(it.first).first;
        location.x = gui->getTileSize() * (index % 4) + pRect->x + 600;
        location.y = gui->getTileSize() * (index / 4) + pRect->y;
        location.w = gui->getTileSize();
        location.h = gui->getTileSize();
        it.second->getAnimationObject()->render(gui, &location, i);
    }
}

void CGameInventoryPanel::drawSelection(std::shared_ptr<CGui> gui, SDL_Rect *location) {
    SDL_SetRenderDrawColor(gui->getRenderer(), YELLOW);
    SDL_Rect tmp = {location->x, location->y, selectionBarThickness, location->h};
    SDL_Rect tmp2 = {location->x, location->y, location->w, selectionBarThickness};
    SDL_Rect tmp3 = {location->x, location->y + location->h - selectionBarThickness, location->w,
                     selectionBarThickness};
    SDL_Rect tmp4 = {location->x + location->w - selectionBarThickness, location->y, selectionBarThickness,
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
            std::string newSelection = vstd::get(items, clickedIndex)->getName();
            if (selected != newSelection) {
                selected = newSelection;
            } else {
                selected = "";
            }

        }
    }
}

bool CGameInventoryPanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return x < gui->getTileSize() * xInv && y < gui->getTileSize() * yInv;
}
