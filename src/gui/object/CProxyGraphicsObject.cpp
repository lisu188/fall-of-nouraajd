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
    vstd::cast<CProxyTargetGraphicsObject>(getParent())->renderProxyObject(gui, rect, frameTime, x, y);
}

CProxyGraphicsObject::CProxyGraphicsObject(int x, int y) : x(x), y(y) {

}

CProxyGraphicsObject::CProxyGraphicsObject() {

}