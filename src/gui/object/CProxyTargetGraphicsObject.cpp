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

#include <utility>
#include "CProxyGraphicsObject.h"
#include "gui/CLayout.h"
#include "gui/CGui.h"

void CProxyTargetGraphicsObject::render(std::shared_ptr<CGui> gui, int frameTime) {
    CGameGraphicsObject::render(gui, frameTime);
}

void CProxyTargetGraphicsObject::refresh() {
    vstd::with<void>(getGui(), [this](auto gui) {
        auto[previousSizeX, xRow]=*std::max_element(proxyObjects.begin(), proxyObjects.end());
        auto[previousSizeY, unused]=*std::max_element(xRow.begin(), xRow.end());


        int currentSizeX = getSizeX(gui);
        int currentSizeY = getSizeY(gui);

        int xDiff = currentSizeX - previousSizeX;
        int yDiff = currentSizeX - previousSizeY;

        if (proxyObjects.size() != (unsigned int) currentSizeX * (unsigned int) currentSizeY) {
            for (auto[_x, map_x]: proxyObjects) {
                for (auto[no, val]: map_x) {
                    removeChild(val);
                }
            }
            proxyObjects.clear();
            auto tileSize = getTileSize(this->ptr<CGameGraphicsObject>());
            for (int x = 0; x < getSizeX(gui); x++) {
                for (int y = 0; y < currentSizeY; y++) {
                    std::shared_ptr<CProxyGraphicsObject> nh = std::make_shared<CProxyGraphicsObject>(x, y);
                    std::shared_ptr<CLayout> layout1 = gui->getGame()->template createObject<CLayout>(
                            proxyLayout);
                    layout1->setNumericProperty("tileSize", tileSize);
                    nh->setLayout(layout1);
                    proxyObjects[x][y] = nh;
                    addChild(nh);
                }
            }
            refreshAll();
        }
    });
}

void CProxyTargetGraphicsObject::refreshAll() {
    for (auto[_x, map_x]: proxyObjects) {
        for (auto[no, val]: map_x) {
            val->refresh();
        }
    }
}

void CProxyTargetGraphicsObject::refreshObject(int x, int y) {
    for (auto[_x, map_x]: proxyObjects) {
        vstd::execute_if(map_x, [=](auto object) {
            return object.second->getX() == x && object.second->getY() == y;
        }, [=](auto ob) {
            ob.second->refresh();
        });//TODO: index
    }
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

std::list<std::shared_ptr<CGameGraphicsObject>>
CProxyTargetGraphicsObject::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    return {};
}

std::string CProxyTargetGraphicsObject::getProxyLayout() {
    return proxyLayout;
}

void CProxyTargetGraphicsObject::setProxyLayout(std::string _layout) {
    proxyLayout = std::move(_layout);
}
