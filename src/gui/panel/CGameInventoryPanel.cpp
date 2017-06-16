

#include "CGameInventoryPanel.h"
#include "gui/CGui.h"
#include "object/CItem.h"

void CGameInventoryPanel::panelRender(std::shared_ptr<CGui> gui, SDL_Rect *pRect, int i, std::string basic_string) {
    int index = 0;
    SDL_RenderFillRect(gui->getRenderer(), pRect);
    for (std::shared_ptr<CItem> item:_player->getAllItems()) {
        SDL_Rect location;
        location.x = TILE_SIZE * (index % 4) + pRect->x;
        location.y = TILE_SIZE * (index / 4) + pRect->y;
        location.w = TILE_SIZE;
        location.h = TILE_SIZE;
        gui->getAnimationHandler()->getAnimation(item->getAnimation())->render(gui, &location, i,
                                                                               item->getName());
        index++;

    }
}


void CGameInventoryPanel::panelEvent(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_i) {
        gui->removeObject(this->ptr<CGameInventoryPanel>());
    }
}

CGameInventoryPanel::CGameInventoryPanel(std::shared_ptr<CPlayer> _player) : _player(_player) {

}
