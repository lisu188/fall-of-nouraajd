

#include "CGameInventoryPanel.h"
#include "gui/CGui.h"
#include "object/CItem.h"

void CGameInventoryPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {

    SDL_RenderFillRect(gui->getRenderer(), pRect.get());
    int index = 0;
    for (std::shared_ptr<CItem> item:_player->getItems()) {
        SDL_Rect location;
        location.x = gui->getTileSize() * (index % 4) + pRect->x;
        location.y = gui->getTileSize() * (index / 4) + pRect->y;
        location.w = gui->getTileSize();
        location.h = gui->getTileSize();
        item->getAnimationObject()->render(gui, &location, i);
        index++;
    }
    for (auto it:_player->getEquipped()) {
        SDL_Rect location;
        index = vstd::to_int(it.first).first;
        location.x = gui->getTileSize() * (index % 4) + pRect->x + 600;
        location.y = gui->getTileSize() * (index / 4) + pRect->y;
        location.w = gui->getTileSize();
        location.h = gui->getTileSize();
        it.second->getAnimationObject()->render(gui, &location, i);
    }
}


void CGameInventoryPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_i) {
        gui->removeObject(this->ptr<CGameInventoryPanel>());
    }
}

CGameInventoryPanel::CGameInventoryPanel(std::shared_ptr<CPlayer> _player) : _player(_player) {

}

CGameInventoryPanel::CGameInventoryPanel() {

}

void CGameInventoryPanel::panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) {
    vstd::logger::debug(x, y);
}
