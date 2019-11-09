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

class CLayout;

class CGameGraphicsObject : public CGameObject {
V_META(CGameGraphicsObject, CGameObject,
       V_PROPERTY(CGameGraphicsObject, std::shared_ptr<CLayout>, layout, getLayout, setLayout))

    std::list<std::pair<std::function<bool(std::shared_ptr<CGui>, SDL_Event *)>, std::function<bool(
            std::shared_ptr<CGui>, SDL_Event *) >>> eventCallbackList;
    std::set<std::shared_ptr<CGameGraphicsObject>> children;
    std::weak_ptr<CGameGraphicsObject> parent;

    std::shared_ptr<CLayout> layout;

public:
    void render(std::shared_ptr<CGui> reneder, int frameTime);

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event);

    virtual bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i);

    virtual bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y);

    virtual void renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                               std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func);

    std::shared_ptr<CGameGraphicsObject> getParent();

    std::shared_ptr<CGameGraphicsObject> getTopParent();

    void setParent(std::shared_ptr<CGameGraphicsObject> _parent);

    std::shared_ptr<CLayout> getLayout();

    void setLayout(std::shared_ptr<CLayout> layout);

    void addChild(std::shared_ptr<CGameGraphicsObject> child);

    void removeChild(std::shared_ptr<CGameGraphicsObject> child);

    void removeParent();

private:
    std::shared_ptr<SDL_Rect> getRect();
};