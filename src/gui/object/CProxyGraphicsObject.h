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

#include "gui/object/CGameGraphicsObject.h"


class CMapGraphicsObject;

class CProxyGraphicsObject : public CGameGraphicsObject {
V_META(CProxyGraphicsObject, CGameGraphicsObject,
       V_PROPERTY(CProxyGraphicsObject, int, x, getX, setX),
       V_PROPERTY(CProxyGraphicsObject, int, y, getY, setY)
)

    void render(std::shared_ptr<CGui> reneder, int frameTime) override;

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

private:
    int x, y;

public:
    CProxyGraphicsObject() = default;

    CProxyGraphicsObject(int x, int y);

    int getX() { return x; }

    void setX(int _x) { this->x = _x; }

    int getY() { return y; }

    void setY(int _y) { this->y = _y; }

    void refresh();
};
