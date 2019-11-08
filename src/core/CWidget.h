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

class CGui;

class CWidget : public CGameObject {
V_META(CWidget, CGameObject,
       V_PROPERTY(CWidget, int, x, getX, setX),
       V_PROPERTY(CWidget, int, y, getY, setY),
       V_PROPERTY(CWidget, int, w, getW, setW),
       V_PROPERTY(CWidget, int, h, getH, setH),
       V_PROPERTY(CWidget, std::string, render, getRender, setRender),
       V_PROPERTY(CWidget, std::string, click, getClick, setClick))
public:
    CWidget() = default;

    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<SDL_Rect> pRect);

private:
    int x = 0,
            y = 0,
            w = 0,
            h = 0;

    std::string render;
    std::string click;
public:
    virtual void renderObject(std::shared_ptr<CGui> reneder, int frameTime) override;

    virtual bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) override;


    std::string getClick();

    void setClick(std::string click);

    std::string getRender();

    void setRender(std::string draw);

    int getX();

    void setX(int x);

    int getY();

    void setY(int y);

    int getW();

    void setW(int w);

    int getH();

    void setH(int h);


};