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
V_META(CLayout, CGameObject,
       V_PROPERTY(CLayout, std::string, w, getW, setW),
       V_PROPERTY(CLayout, std::string, h, getH, setH),
       V_PROPERTY(CLayout, std::string, x, getX, setX),
       V_PROPERTY(CLayout, std::string, y, getY, setY),
       V_PROPERTY(CLayout, std::string, vertical, getVertical, setVertical),
       V_PROPERTY(CLayout, std::string, horizontal, getHorizontal, setHorizontal))
public:
    virtual std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object);

private:

    enum TYPE {
        SIMPLE, PERCENT
    };

    std::pair<TYPE, int> parseValue(std::shared_ptr<CGameGraphicsObject> object, std::string value);

    int parseValue(std::pair<TYPE, int> value, int parentValue);

    int parseValue(std::shared_ptr<CGameGraphicsObject> object, std::string value, int parentValue);

protected:
    static std::shared_ptr<SDL_Rect> getParentRect(std::shared_ptr<CGameGraphicsObject> object);

public:
    std::string getW();

    void setW(std::string _width);

    std::string getH();

    void setH(std::string _height);

    std::string getX();

    void setX(std::string _x);

    std::string getY();

    void setY(std::string _y);

    std::string getVertical();

    void setVertical(std::string vertical);

    std::string getHorizontal();

    void setHorizontal(std::string horizontal);

private:
    std::string w = "0";
    std::string h = "0";
    std::string x = "0";
    std::string y = "0";
    std::string vertical;
    std::string horizontal;
};

class CCenteredLayout : public CLayout {
V_META(CCenteredLayout, CLayout, vstd::meta::empty())
public:
    CCenteredLayout();
};

class CParentLayout : public CLayout {
V_META(CParentLayout, CLayout, vstd::meta::empty())
public:
    CParentLayout();
};

//TODO: remove
class CProxyGraphicsLayout : public CLayout {
V_META(CProxyGraphicsLayout, CLayout,
       V_PROPERTY(CProxyGraphicsLayout, int, tileSize, getTileSize, setTileSize))
public:
    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) override;

    int getTileSize();

    void setTileSize(int _tileSize);

private:
    int tileSize;
};
