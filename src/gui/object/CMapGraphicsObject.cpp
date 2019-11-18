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
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/CAnimation.h"
#include "core/CLoader.h"

CMapGraphicsObject::CMapGraphicsObject() {

}


std::set<std::shared_ptr<CGameGraphicsObject>>
CMapGraphicsObject::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    std::set<std::shared_ptr<CGameGraphicsObject>> return_val;
    if (std::shared_ptr<CMap> map = gui->getGame()->getMap()) {//TODO:
        auto playerCoords = map->getPlayer()->getCoords();

        Coords actualCoords(playerCoords.x - gui->getTileCountX() / 2 + x,
                            playerCoords.y - gui->getTileCountY() / 2 + y,
                            playerCoords.z);

        std::shared_ptr<CTile> tile = map->getTile(actualCoords.x, actualCoords.y, actualCoords.z);

        return_val.insert(tile->getGraphicsObject());


        for (auto ob: map->getObjectsAtCoords(actualCoords)) {
            return_val.insert(ob->getGraphicsObject());
        }
    }
    return return_val;
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
            gui->pushChild(panel);
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

int CMapGraphicsObject::getSizeY(std::shared_ptr<CGui> gui) {
    return gui->getTileCountY();
}

int CMapGraphicsObject::getSizeX(std::shared_ptr<CGui> gui) {
    return gui->getTileCountX();
}

bool CMapGraphicsObject::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        if (gui->getGame()->getMap()->isMoving()) {
            return true; //TODO: rethink this
        }
        switch (i) {
            case SDLK_UP:
                gui->getGame()->getMap()->getPlayer()->setController(
                        std::make_shared<CPlayerController>(Coords(0, -1, 0)));
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_DOWN:
                gui->getGame()->getMap()->getPlayer()->setController(
                        std::make_shared<CPlayerController>(Coords(0, 1, 0)));
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_LEFT:
                gui->getGame()->getMap()->getPlayer()->setController(
                        std::make_shared<CPlayerController>(Coords(-1, 0, 0)));
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_RIGHT:
                gui->getGame()->getMap()->getPlayer()->setController(
                        std::make_shared<CPlayerController>(Coords(1, 0, 0)));
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_SPACE:
                gui->getGame()->getMap()->getPlayer()->setController(
                        std::make_shared<CPlayerController>(Coords(0, 0, 0)));
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_s:
                CMapLoader::save(gui->getGame()->getMap(), gui->getGame()->getMap()->getName());
                return true;
        }
    }
    return false;
}
