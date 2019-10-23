/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
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
    if (std::shared_ptr<CMap> map = gui->getGame()->getMap()) {
        Coords playerCoords = map->getPlayer()->getCoords();
        std::unordered_set<Coords> tiles;
        for (int x = 0; x <= gui->getTileCountX(); x++)
            for (int y = 0; y <= gui->getTileCountY(); y++) {
                std::shared_ptr<CTile> tile = map->getTile(playerCoords.x - gui->getTileCountX() / 2 + x,
                                                           playerCoords.y - gui->getTileCountY() / 2 + y,
                                                           playerCoords.z);

                tiles.insert(tile->getCoords());

                tile->getGraphicsObject()->render(gui, RECT(
                        gui->getTileSize() * x + pos->x,
                        gui->getTileSize() * y + pos->y,
                        gui->getTileSize(),
                        gui->getTileSize()), frameTime);
            }
        map->forObjects([&](std::shared_ptr<CMapObject> ob) {
            if (vstd::ctn(tiles, ob->getCoords())) {
                ob->getGraphicsObject()->render(gui, RECT(
                        gui->getTileSize() * (ob->getCoords().x + gui->getTileCountX() / 2 - playerCoords.x) +
                        pos->x,
                        gui->getTileSize() * (ob->getCoords().y + gui->getTileCountY() / 2 - playerCoords.y) +
                        pos->y,
                        gui->getTileSize(),
                        gui->getTileSize()), frameTime);
            }
        });
    }
}

void CMapGraphicsObject::initialize() {
    for (auto val:panelKeys->getValues()) {
        auto keyPred = [=](std::shared_ptr<CGui> gui, SDL_Event *event) {
            return event->type == SDL_KEYDOWN && event->key.keysym.sym == val.first[0];
        };
        registerEventCallback(keyPred, [=](std::shared_ptr<CGui> gui, SDL_Event *event) {
            std::shared_ptr<CGamePanel> panel = gui->getGame()->createObject<CGamePanel>(val.second);
            panel->registerEventCallback(keyPred, [=](std::shared_ptr<CGui> gui, SDL_Event *event) {
                gui->removeObject(panel);
                return true;
            });
            gui->addObject(panel);
            return true;
        });
    }
}

std::shared_ptr<CMapStringString> CMapGraphicsObject::getPanelKeys() {
    return panelKeys;
}

void CMapGraphicsObject::setPanelKeys(std::shared_ptr<CMapStringString> panelKeys) {
    this->panelKeys = panelKeys;
}
