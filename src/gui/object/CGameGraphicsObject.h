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
       V_PROPERTY(CGameGraphicsObject, int, height, getHeight, setHeight))

    std::list<std::pair<std::function<bool(std::shared_ptr<CGui>, SDL_Event *)>, std::function<bool(
            std::shared_ptr<CGui>, SDL_Event *) >>> eventCallbackList;
    std::set<std::shared_ptr<CGameGraphicsObject>> children;
    std::weak_ptr<CGameGraphicsObject> parent;

public:
    virtual void render(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> pos, int frameTime);

    virtual bool event(std::shared_ptr<CGui> gui, SDL_Event *event);

    void registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                               std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func);

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

private:
    int width = 0;
    int height = 0;

    std::pair<int, int> translatePos(std::shared_ptr<CGui> gui, int x, int y);

protected:
    virtual std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<SDL_Rect> pos) {
        //TODO: useBoxInBox
        //TODO: this is centered!
        return RECT(
                pos->x + pos->w / 2 - this->width / 2,
                pos->y + pos->h / 2 - this->height / 2,
                width,
                height);
    }
};