#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "core/CController.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/CAnimation.h"
#include "core/CLoader.h"

CMapGraphicsObject::CMapGraphicsObject() {
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_UP;
    }, [](std::shared_ptr<CGui> gui, SDL_Event *event) {
        gui->getGame()->getMap()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(0, -1, 0)));
        gui->getGame()->getMap()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_DOWN;
    }, [](std::shared_ptr<CGui> gui, SDL_Event *event) {
        gui->getGame()->getMap()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(0, 1, 0)));
        gui->getGame()->getMap()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_LEFT;
    }, [](std::shared_ptr<CGui> gui, SDL_Event *event) {
        gui->getGame()->getMap()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(-1, 0, 0)));
        gui->getGame()->getMap()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_RIGHT;
    }, [](std::shared_ptr<CGui> gui, SDL_Event *event) {
        gui->getGame()->getMap()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(1, 0, 0)));
        gui->getGame()->getMap()->move();
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_SPACE;
    }, [](std::shared_ptr<CGui> gui, SDL_Event *event) {
        gui->getGame()->getMap()->getPlayer()->setController(std::make_shared<CPlayerController>(Coords(0, 0, 0)));
        gui->getGame()->getMap()->move();
        return true;
    });

    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_s;
    }, [](std::shared_ptr<CGui> gui, SDL_Event *event) {
        CMapLoader::save(gui->getGame()->getMap(), gui->getGame()->getMap()->getName());
        return true;
    });
}

void CMapGraphicsObject::render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) {
    std::shared_ptr<CMap> map = gui->getGame()->getMap();
    Coords playerCoords = map->getPlayer()->getCoords();
    std::unordered_set<Coords> tiles;
    for (int x = 0; x < gui->getTileCountX(); x++)
        for (int y = 0; y <= gui->getTileCountY(); y++) {
            std::shared_ptr<CTile> tile = map->getTile(playerCoords.x - gui->getTileCountX() / 2 + x,
                                                       playerCoords.y - gui->getTileCountY() / 2 + y,
                                                       playerCoords.z);

            tiles.insert(tile->getCoords());

            tile->getAnimationObject()->render(gui, RECT(
                    gui->getTileSize() * x + pos->x,
                    gui->getTileSize() * y + pos->y,
                    gui->getTileSize(),
                    gui->getTileSize()), frameTime);
        }
    map->forObjects([&](std::shared_ptr<CMapObject> ob) {
        if (vstd::ctn(tiles, ob->getCoords())) {
            ob->getAnimationObject()->render(gui, RECT(
                    gui->getTileSize() * (ob->getCoords().x + gui->getTileCountX() / 2 - playerCoords.x) +
                    pos->x,
                    gui->getTileSize() * (ob->getCoords().y + gui->getTileCountY() / 2 - playerCoords.y) +
                    pos->y,
                    gui->getTileSize(),
                    gui->getTileSize()), frameTime);
        }
    });
}

