

#include "CGameInventoryPanel.h"
#include "gui/CGui.h"
#include "object/CItem.h"

void CGameInventoryPanel::panelRender(std::shared_ptr<CGui> gui, SDL_Rect *pRect, int i, std::string basic_string) {

    SDL_RenderFillRect(gui->getRenderer(), pRect);
    int index = 0;
    for (std::shared_ptr<CItem> item:_player->getItems()) {
        SDL_Rect location;
        location.x = TILE_SIZE * (index % 4) + pRect->x;
        location.y = TILE_SIZE * (index / 4) + pRect->y;
        location.w = TILE_SIZE;
        location.h = TILE_SIZE;
        gui->getAnimationHandler()->getAnimation(item->getAnimation())->render(gui, &location, i,
                                                                               item->getName());
        index++;
    }
    for (auto it:_player->getEquipped()) {
        SDL_Rect location;
        index = vstd::to_int(it.first).first;
        location.x = TILE_SIZE * (index % 4) + pRect->x + 600;
        location.y = TILE_SIZE * (index / 4) + pRect->y;
        location.w = TILE_SIZE;
        location.h = TILE_SIZE;
        gui->getAnimationHandler()->getAnimation(it.second->getAnimation())->render(gui, &location, i,
                                                                                    it.second->getName());
    }
}


void CGameInventoryPanel::panelEvent(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_i) {
        gui->removeObject(this->ptr<CGameInventoryPanel>());
    }
}

CGameInventoryPanel::CGameInventoryPanel(std::shared_ptr<CPlayer> _player) : _player(_player) {

}
