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

class CGameGraphicsObject : public CGameObject {
V_META(CGameGraphicsObject, CGameObject,
       V_PROPERTY(CGameGraphicsObject, int, width, getWidth, setWidth),
       V_PROPERTY(CGameGraphicsObject, int, height, getHeight, setHeight),
       V_PROPERTY(CGameGraphicsObject, int, x, getX, setX),
       V_PROPERTY(CGameGraphicsObject, int, y, getY, setY))

    std::list<std::pair<std::function<bool(std::shared_ptr<CGui>, SDL_Event *)>, std::function<bool(
            std::shared_ptr<CGui>, SDL_Event *) >>> eventCallbackList;
    std::set<std::shared_ptr<CGameGraphicsObject>> children;
    std::weak_ptr<CGameGraphicsObject> parent;


public:
    void render(std::shared_ptr<CGui> reneder, int frameTime);

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event);

    virtual bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i);

    virtual bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y);

    virtual void renderObject(std::shared_ptr<CGui> reneder, int frameTime);

    void registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                               std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func);


    std::shared_ptr<CGameGraphicsObject> getParent() {
        return parent.lock();
    }

    void setParent(std::shared_ptr<CGameGraphicsObject> _parent) {
        this->parent = _parent;
    }

    int getWidth() {
        return width;
    }

    void setWidth(int _width) {
        width = _width;
    }

    int getHeight() {
        return height;
    }

    void setHeight(int _height) {
        height = _height;
    }

    int getX() {
        return x;
    }

    void setX(int _x) {
        x = _x;
    }

    int getY() {
        return y;
    }

    void setY(int _y) {
        y = _y;
    }

    virtual std::shared_ptr<SDL_Rect> getRect() {
        return RECT(
                parent.lock() ? parent.lock()->getX() + getX() : getX(),
                parent.lock() ? parent.lock()->getY() + getY() : getY(),
                width,
                height);
    }

private:
    int width = 0;
    int height = 0;
    int x = 0;
    int y = 0;
};