#include "gui/CMapGraphicsObject.h"
#include "core/CMap.h"
#include "gui/CAnimationHandler.h"
#include "gui/CGui.h"

CMapGraphicsObject::CMapGraphicsObject(std::shared_ptr<CMap> map) : _map(map) {

}

void CMapGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos) {
    std::shared_ptr<CMap> map = _map.lock();
    Coords playerCoords = map->getPlayer()->getCoords();
    for (int x = 0; x < X_SIZE; x++)
        for (int y = 0; y <= Y_SIZE; y++) {
            std::shared_ptr<CTile> tile = map->getTile(playerCoords.x - X_SIZE / 2 + x, playerCoords.x - Y_SIZE / 2 + y,
                                                       playerCoords.z);
            SDL_Rect physical;
            physical.x = TILE_SIZE * x + pos->x;
            physical.y = TILE_SIZE * y + pos->y;
            physical.w = TILE_SIZE;
            physical.h = TILE_SIZE;
            gui->getAnimationHandler()->getAnimation(tile->getAnimation())->render(gui, &physical);
        }
}

bool CMapGraphicsObject::event(SDL_Event *event) {
    return CGameGraphicsObject::event(event);
}
