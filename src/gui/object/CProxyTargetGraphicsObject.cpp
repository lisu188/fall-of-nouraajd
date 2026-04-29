/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include <algorithm>
#include <utility>

void CProxyTargetGraphicsObject::refresh() {
    vstd::with<void>(getGui(), [this](auto gui) {
        int prevX = 0, prevY = 0;
        for (const auto &x_pair : proxyObjects) {
            prevX = std::max(prevX, x_pair.first + 1);
            if (!x_pair.second.empty()) {
                prevY = std::max(prevY, x_pair.second.rbegin()->first + 1);
            }
        }

        int currentSizeX = getSizeX(gui);
        int currentSizeY = getSizeY(gui);

        int xDiff = currentSizeX - prevX;
        int yDiff = currentSizeY - prevY;

        for (int x = 0; x < std::max(prevX, currentSizeX); x++) {
            for (int y = 0; y < std::max(prevY, currentSizeY); y++) {
                if (vstd::square_ctn(currentSizeX, currentSizeY, x, y) && !vstd::square_ctn(prevX, prevY, x, y)) {
                    addProxyObject(gui, x, y);
                } else if (!vstd::square_ctn(currentSizeX, currentSizeY, x, y) &&
                           vstd::square_ctn(prevX, prevY, x, y)) {
                    removeProxyObject(x, y);
                }
            }
        }

        if (xDiff != 0 || yDiff != 0) {
            onProxyGridResized(currentSizeX, currentSizeY);
            refreshAll();
        }
    });
}

void CProxyTargetGraphicsObject::addProxyObject(std::shared_ptr<CGui> gui, int &x, int &y) {
    std::shared_ptr<CProxyGraphicsObject> nh = std::make_shared<CProxyGraphicsObject>(x, y);
    std::shared_ptr<CLayout> layout1 = gui->getGame()->template createObject<CLayout>(proxyLayout);
    layout1->setNumericProperty("tileSize", getTileSize(this->ptr<CGameGraphicsObject>()));
    nh->setLayout(layout1);
    proxyObjects[x][y] = nh;
    addChild(nh);
}

void CProxyTargetGraphicsObject::removeProxyObject(int &x, int &y) {
    auto xIt = proxyObjects.find(x);
    if (xIt == proxyObjects.end()) {
        return;
    }
    auto yIt = xIt->second.find(y);
    if (yIt == xIt->second.end()) {
        return;
    }
    removeChild(yIt->second);
    xIt->second.erase(yIt);
    if (xIt->second.empty()) {
        proxyObjects.erase(xIt);
    }
}

void CProxyTargetGraphicsObject::refreshAll() {
    for (auto &[_x, map_x] : proxyObjects) {
        for (auto &[no, val] : map_x) {
            val->refresh();
        }
    }
}

void CProxyTargetGraphicsObject::refreshObject(int x, int y) {
    auto gui = getGui();
    int sizeX = getSizeX(gui);
    int sizeY = getSizeY(gui);
    if (x < 0 || x >= sizeX || y < 0 || y >= sizeY) {
        vstd::logger::warning("Ignoring proxy refresh outside target bounds:", x, y, "size:", sizeX, sizeY);
        return;
    }
    auto xIt = proxyObjects.find(x);
    if (xIt == proxyObjects.end()) {
        return;
    }
    auto yIt = xIt->second.find(y);
    if (yIt != xIt->second.end()) {
        yIt->second->refresh();
    }
}

int CProxyTargetGraphicsObject::getSizeX(std::shared_ptr<CGui> gui) { return 0; }

int CProxyTargetGraphicsObject::getSizeY(std::shared_ptr<CGui> gui) { return 0; }

std::list<std::shared_ptr<CGameGraphicsObject>> CProxyTargetGraphicsObject::getProxiedObjects(std::shared_ptr<CGui> gui,
                                                                                              int x, int y) {
    return {};
}

std::string CProxyTargetGraphicsObject::getProxyLayout() { return proxyLayout; }

void CProxyTargetGraphicsObject::setProxyLayout(std::string _layout) { proxyLayout = std::move(_layout); }

void CProxyTargetGraphicsObject::onProxyGridResized(int sizeX, int sizeY) {}
