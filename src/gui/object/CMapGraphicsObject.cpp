#include <gui/panel/CGameInventoryPanel.h>
#include "core/CController.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/CTextureCache.h"

CMapGraphicsObject::CMapGraphicsObject(std::function<std::shared_ptr<CMap>()> map) : _map(map) {
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_UP;
    }, [map](std::shared_ptr<CGui> gui, SDL_Event *event) {
        map()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(0, -1, 0)));
        map()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_DOWN;
    }, [map](std::shared_ptr<CGui> gui, SDL_Event *event) {
        map()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(0, 1, 0)));
        map()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_LEFT;
    }, [map](std::shared_ptr<CGui> gui, SDL_Event *event) {
        map()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(-1, 0, 0)));
        map()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_RIGHT;
    }, [map](std::shared_ptr<CGui> gui, SDL_Event *event) {
        map()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(1, 0, 0)));
        map()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_SPACE;
    }, [map](std::shared_ptr<CGui> gui, SDL_Event *event) {
        map()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(0, 0, 0)));
        map()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_i;
    }, [map](std::shared_ptr<CGui> gui, SDL_Event *event) {
        gui->addObject(std::make_shared<CGameInventoryPanel>(map()->getPlayer()));
        return true;
    });
}

void CMapGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    std::shared_ptr<CMap> map = _map();
    Coords playerCoords = map->getPlayer()->getCoords();
    std::unordered_set<Coords> tiles;
    for (int x = 0; x < gui->getTileCountX(); x++)
        for (int y = 0; y <= gui->getTileCountY(); y++) {
            std::shared_ptr<CTile> tile = map->getTile(playerCoords.x - gui->getTileCountX() / 2 + x,
                                                       playerCoords.y - gui->getTileCountY() / 2 + y,
                                                       playerCoords.z);

            tiles.insert(tile->getCoords());

            SDL_Rect physical;
            physical.x = gui->getTileSize() * x + pos->x;
            physical.y = gui->getTileSize() * y + pos->y;
            physical.w = gui->getTileSize();
            physical.h = gui->getTileSize();
            tile->getAnimationObject()->render(gui, &physical, frameTime);
        }
    map->forObjects([&](std::shared_ptr<CMapObject> ob) {
        if (vstd::ctn(tiles, ob->getCoords())) {
            SDL_Rect physical;
            physical.x = gui->getTileSize() * (ob->getCoords().x + gui->getTileCountX() / 2 - playerCoords.x) + pos->x;
            physical.y = gui->getTileSize() * (ob->getCoords().y + gui->getTileCountY() / 2 - playerCoords.y) + pos->y;
            physical.w = gui->getTileSize();
            physical.h = gui->getTileSize();
            ob->getAnimationObject()->render(gui, &physical, frameTime);
        }
    });
}

CMapGraphicsObject::CMapGraphicsObject() {

}

