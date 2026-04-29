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
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/object/CProxyTargetGraphicsObject.h"

#include <set>

namespace {
bool hasSameProxyChildren(const std::list<std::shared_ptr<CGameGraphicsObject>> &objects,
                          const std::set<std::shared_ptr<CGameGraphicsObject>, priority_comparator> &children) {
    if (objects.size() != children.size()) {
        return false;
    }
    for (const auto &object : objects) {
        auto current = children.find(object);
        if (current == children.end() || (*current)->getPriority() != object->getPriority() ||
            (*current)->meta()->name() != object->meta()->name()) {
            return false;
        }
    }
    return true;
}
} // namespace

CProxyGraphicsObject::CProxyGraphicsObject(int x, int y) : x(x), y(y) {}

void CProxyGraphicsObject::refresh() {
    vstd::with<void>(getGui(), [this](auto gui) {
        auto target = vstd::cast<CProxyTargetGraphicsObject>(getParent());
        auto objects = target->getProxiedObjects(gui, x, y);

        if (hasSameProxyChildren(objects, children)) {
            return;
        }

        setChildren(std::set<std::shared_ptr<CGameGraphicsObject>>(objects.begin(), objects.end()));
    });
}
