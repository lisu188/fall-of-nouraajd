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
#pragma once

#include "core/CList.h"
#include "gui/object/CGameGraphicsObject.h"


class CMapGraphicsObject;

class CMapGraphicsProxyObject : public CGameGraphicsObject {
V_META(CMapGraphicsProxyObject, CGameGraphicsObject,
       V_PROPERTY(CMapGraphicsProxyObject, int, x, getX, setX),
       V_PROPERTY(CMapGraphicsProxyObject, int, y, getY, setY))
public:
    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

    bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) override;

    void renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

private:
    int x, y;

public:
    CMapGraphicsProxyObject(int x, int y);

    int getX() { return x; }

    void setX(int _x) { this->x = _x; }

    int getY() { return y; }

    void setY(int _y) { this->y = _y; }
};

class CMapGraphicsObject : public CGameGraphicsObject {
V_META(CMapGraphicsObject, CGameGraphicsObject,
       V_PROPERTY(CMapGraphicsObject, std::shared_ptr<CMapStringString>, panelKeys, getPanelKeys, setPanelKeys),
       V_METHOD(CMapGraphicsObject, initialize))


public:
    CMapGraphicsObject();

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    std::shared_ptr<CMapStringString> getPanelKeys();

    void setPanelKeys(std::shared_ptr<CMapStringString> panelKeys);

    void initialize();

private:
    std::shared_ptr<CMapStringString> panelKeys;

    std::unordered_map<std::pair<int, int>, std::shared_ptr<CMapGraphicsProxyObject>> proxyObjects;

};


