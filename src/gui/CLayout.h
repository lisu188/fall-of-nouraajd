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
#include "gui/object/CGameGraphicsObject.h"

class CLayout : public CGameObject {
V_META(CLayout, CGameObject, vstd::meta::empty())
public:
    virtual std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object);

protected:

    static std::shared_ptr<SDL_Rect> getParentRect(std::shared_ptr<CGameGraphicsObject> object);

};

class CSimpleLayout : public CLayout {
V_META(CSimpleLayout, CLayout,
       V_PROPERTY(CSimpleLayout, int, width, getWidth, setWidth),
       V_PROPERTY(CSimpleLayout, int, height, getHeight, setHeight),
       V_PROPERTY(CSimpleLayout, int, x, getX, setX),
       V_PROPERTY(CSimpleLayout, int, y, getY, setY))
public:
    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) override;


    int getWidth();

    void setWidth(int _width);

    int getHeight();

    void setHeight(int _height);

    int getX();

    void setX(int _x);

    int getY();

    void setY(int _y);

private:
    int width = 0;
    int height = 0;
    int x = 0;
    int y = 0;
};


class CCenteredLayout : public CLayout {
V_META(CCenteredLayout, CLayout,
       V_PROPERTY(CCenteredLayout, int, width, getWidth, setWidth),
       V_PROPERTY(CCenteredLayout, int, height, getHeight, setHeight))
public:
    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) override;

    int getWidth();

    void setWidth(int _width);

    int getHeight();

    void setHeight(int _height);

private:
    int width = 0;
    int height = 0;
};

class CPercentLayout : public CLayout {
V_META(CPercentLayout, CLayout,
       V_PROPERTY(CPercentLayout, int, x, getX, setX),
       V_PROPERTY(CPercentLayout, int, y, getY, setY),
       V_PROPERTY(CPercentLayout, int, w, getW, setW),
       V_PROPERTY(CPercentLayout, int, h, getH, setH))
public:
    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) override;

    int getX();

    void setX(int x);

    int getY();

    void setY(int y);

    int getW();

    void setW(int w);

    int getH();

    void setH(int h);

private:
    int x = 0,
            y = 0,
            w = 0,
            h = 0;
};

class CParentLayout : public CLayout {
V_META(CParentLayout, CLayout, vstd::meta::empty())
public:
    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) {
        return getParentRect(object);
    }
};

class CMapGraphicsProxyLayout : public CLayout {
V_META(CMapGraphicsProxyLayout, CLayout, vstd::meta::empty())
public:
    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) override;
};
