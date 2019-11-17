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
    auto proxied = vstd::cast<CProxyTargetGraphicsObject>(getParent())->getProxiedObjects(gui, x, y);
    std::set<std::shared_ptr<CGameGraphicsObject>,
            priority_comparator> proxied_sorted(proxied.begin(),
                                                proxied.end());
    for (auto child:proxied_sorted) {
        child->setParent(this->ptr<CGameGraphicsObject>());
        child->render(gui, frameTime);
        child->removeParent();
    }
}

bool CProxyGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    auto proxied = vstd::cast<CProxyTargetGraphicsObject>(getParent())->getProxiedObjects(gui, x, y);
    std::set<std::shared_ptr<CGameGraphicsObject>,
            reverse_priority_comparator> proxied_sorted(proxied.begin(),
                                                        proxied.end());
    for (auto child:proxied_sorted) {
        child->setParent(this->ptr<CGameGraphicsObject>());
        bool eventConsumed = child->event(gui, event);
        child->removeParent();
        if (eventConsumed) {
            return true;
        }
    }
    return false;
}
