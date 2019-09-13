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


#include "object/CGameObject.h"

class CWidget : public CGameObject {
V_META(CWidget, CGameObject,
       V_PROPERTY(CWidget, int, x, getX, setX),
       V_PROPERTY(CWidget, int, y, getY, setY),
       V_PROPERTY(CWidget, int, w, getW, setW),
       V_PROPERTY(CWidget, int, h, getH, setH))
public:
    CWidget() = default;

private:
    int x = 0,
            y = 0,
            w = 0,
            h = 0;
public:
    int getX();

    void setX(int x);

    int getY();

    void setY(int y);

    int getW();

    void setW(int w);

    int getH();

    void setH(int h);


};