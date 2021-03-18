/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

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
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/object/CProxyTargetGraphicsObject.h"
#include "gui/CLayout.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "core/CController.h"
#include "gui/object/CMapGraphicsObject.h"
#include "core/CLoader.h"

CProxyGraphicsObject::CProxyGraphicsObject(int x, int y) : x(x), y(y) {

}

CProxyGraphicsObject::CProxyGraphicsObject() {

}

void CProxyGraphicsObject::render(std::shared_ptr<CGui> gui, int frameTime) {
    CGameGraphicsObject::render(gui, frameTime);
}

void CProxyGraphicsObject::refresh() {
    vstd::with<void>(getGui(), [=](auto gui) {
        std::list<std::shared_ptr<CGameGraphicsObject>> objects = vstd::cast<CProxyTargetGraphicsObject>(
                getParent())->getProxiedObjects(gui, x, y);
        children.clear();
        for (auto &object:objects) {
            addChild(object);
        }
    });
}

bool CProxyGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    return CGameGraphicsObject::event(gui, event);
}
