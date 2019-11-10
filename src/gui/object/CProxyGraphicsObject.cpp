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

bool CProxyGraphicsObject::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    return CGameGraphicsObject::keyboardEvent(sharedPtr, type, i);
}

bool CProxyGraphicsObject::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) {
    return CGameGraphicsObject::mouseEvent(sharedPtr, type, x, y);
}

void
CProxyGraphicsObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
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

CProxyGraphicsObject::CProxyGraphicsObject(int x, int y) : x(x), y(y) {

}

CProxyGraphicsObject::CProxyGraphicsObject() {

}