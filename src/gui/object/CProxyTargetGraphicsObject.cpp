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
#include "CProxyTargetGraphicsObject.h"
#include "CProxyGraphicsObject.h"
#include "gui/CLayout.h"


CProxyTargetGraphicsObject::CProxyTargetGraphicsObject() {

}

void CProxyTargetGraphicsObject::render(std::shared_ptr<CGui> gui, int frameTime) {
    CGameGraphicsObject::render(gui, frameTime);
}

void CProxyTargetGraphicsObject::refresh(std::shared_ptr<CGui> gui) {
    if (proxyObjects.size() != (unsigned int) getSizeX(gui) * (unsigned int) getSizeY(gui)) {
        for (auto val:proxyObjects) {
            removeChild(val);
        }
        proxyObjects.clear();
        for (int x = 0; x < getSizeX(gui); x++) {
            for (int y = 0; y < getSizeY(gui); y++) {
                std::shared_ptr<CProxyGraphicsObject> nh = std::make_shared<CProxyGraphicsObject>(x, y);
                nh->setLayout(std::make_shared<CProxyGraphicsLayout>());
                proxyObjects.insert(nh);
                addChild(nh);
            }
        }
        for (auto object:proxyObjects) {
            object->refresh(gui);
        }
    }
}

void CProxyTargetGraphicsObject::refreshObject(std::shared_ptr<CGui> gui, int x, int y) {
    vstd::find_if(proxyObjects, [=](std::shared_ptr<CProxyGraphicsObject> object) {
        return object->getX() == x && object->getY() == y;
    })->refresh(gui);//TODO: index
}

bool CProxyTargetGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    return CGameGraphicsObject::event(gui, event);
}


int CProxyTargetGraphicsObject::getSizeX(std::shared_ptr<CGui> gui) {
    return 0;
}

int CProxyTargetGraphicsObject::getSizeY(std::shared_ptr<CGui> gui) {
    return 0;
}

std::set<std::shared_ptr<CGameGraphicsObject>>
CProxyTargetGraphicsObject::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    return std::set<std::shared_ptr<CGameGraphicsObject>>();
}
