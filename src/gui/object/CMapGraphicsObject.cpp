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
#include "gui/CLayout.h"
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

void CMapGraphicsObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (proxyObjects.size() != gui->getTileCountX() * gui->getTileCountY()) {
        for (auto[key, val]:proxyObjects) {
            removeChild(val);
        }
        proxyObjects.clear();
        for (int x = 0; x <= gui->getTileCountX(); x++)
            for (int y = 0; y <= gui->getTileCountY(); y++) {
                std::shared_ptr<CMapGraphicsProxyObject> nh = std::make_shared<CMapGraphicsProxyObject>(x, y);
                nh->setLayout(std::make_shared<CMapGraphicsProxyLayout>());
                proxyObjects.emplace(std::make_pair(x, y), nh);
                addChild(nh);
            }
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
                gui->removeChild(panel);
                return true;
            });
            gui->addChild(panel);
            return true;
        });
    }
}

std::shared_ptr<CMapStringString> CMapGraphicsObject::getPanelKeys() {
    return panelKeys;
}

void CMapGraphicsObject::setPanelKeys(std::shared_ptr<CMapStringString> _panelKeys) {
    this->panelKeys = _panelKeys;
}

bool CMapGraphicsProxyObject::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    return CGameGraphicsObject::keyboardEvent(sharedPtr, type, i);
}

bool CMapGraphicsProxyObject::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) {
    return CGameGraphicsObject::mouseEvent(sharedPtr, type, x, y);
}

void
CMapGraphicsProxyObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (std::shared_ptr<CMap> map = gui->getGame()->getMap()) {//TODO:
        auto playerCoords = map->getPlayer()->getCoords();

        Coords actualCoords(playerCoords.x - gui->getTileCountX() / 2 + x,
                            playerCoords.y - gui->getTileCountY() / 2 + y,
                            playerCoords.z);

        std::shared_ptr<CTile> tile = map->getTile(actualCoords.x, actualCoords.y, actualCoords.z);

        tile->getGraphicsObject()->renderObject(gui, rect, frameTime);

        map->forObjects([&](std::shared_ptr<CMapObject> ob) {
            ob->getGraphicsObject()->renderObject(gui, rect, frameTime);
        }, [&](std::shared_ptr<CMapObject> ob) {
            return actualCoords == ob->getCoords();
        });
    }
}

CMapGraphicsProxyObject::CMapGraphicsProxyObject(int x, int y) : x(x), y(y) {

}

CMapGraphicsProxyObject::CMapGraphicsProxyObject() {

}