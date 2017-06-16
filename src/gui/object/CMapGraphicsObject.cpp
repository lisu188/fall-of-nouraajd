#include <gui/panel/CGameInventoryPanel.h>
#include "core/CController.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/CAnimationHandler.h"
#include "gui/CGui.h"

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

void CMapGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime,
                                std::string data) {
    std::shared_ptr<CMap> map = _map();
    Coords playerCoords = map->getPlayer()->getCoords();
    std::unordered_set<Coords> tiles;
    for (int x = 0; x < X_SIZE; x++)
        for (int y = 0; y <= Y_SIZE; y++) {
            std::shared_ptr<CTile> tile = map->getTile(playerCoords.x - X_SIZE / 2 + x, playerCoords.y - Y_SIZE / 2 + y,
                                                       playerCoords.z);

            tiles.insert(tile->getCoords());

            SDL_Rect physical;
            physical.x = TILE_SIZE * x + pos->x;
            physical.y = TILE_SIZE * y + pos->y;
            physical.w = TILE_SIZE;
            physical.h = TILE_SIZE;
            gui->getAnimationHandler()->getAnimation(tile->getAnimation())->render(gui, &physical, frameTime,
                                                                                   tile->getName());
        }
    map->forObjects([&](std::shared_ptr<CMapObject> ob) {
        if (vstd::ctn(tiles, ob->getCoords())) {
            SDL_Rect physical;
            physical.x = TILE_SIZE * (ob->getCoords().x + X_SIZE / 2 - playerCoords.x) + pos->x;
            physical.y = TILE_SIZE * (ob->getCoords().y + Y_SIZE / 2 - playerCoords.y) + pos->y;
            physical.w = TILE_SIZE;
            physical.h = TILE_SIZE;
            gui->getAnimationHandler()->getAnimation(ob->getAnimation())->render(gui, &physical, frameTime,
                                                                                 ob->getName());
        }
    });
}

CMapGraphicsObject::CMapGraphicsObject() {

}

