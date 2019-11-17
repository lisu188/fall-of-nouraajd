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

//TODO: generify
struct priority_comparator {
    bool operator()(
            std::shared_ptr<CGameGraphicsObject> a, std::shared_ptr<CGameGraphicsObject> b);
};

struct reverse_priority_comparator {
    bool operator()(
            std::shared_ptr<CGameGraphicsObject> a, std::shared_ptr<CGameGraphicsObject> b);
};

class CGameGraphicsObject : public CGameObject {
    friend class CGui;

    friend class CProxyGraphicsObject;

V_META(CGameGraphicsObject, CGameObject,
       V_PROPERTY(CGameGraphicsObject, int, priority, getPriority, setPriority),
       V_PROPERTY(CGameGraphicsObject, std::shared_ptr<CLayout>, layout, getLayout, setLayout),
       V_PROPERTY(CGameGraphicsObject,
                  std::set<std::shared_ptr<CGameGraphicsObject>>, children, getChildren, setChildren))

    std::list<std::pair<std::function<bool(std::shared_ptr<CGui>, SDL_Event *)>, std::function<bool(
            std::shared_ptr<CGui>, SDL_Event *) >>> eventCallbackList;

    std::list<std::function<void(std::shared_ptr<CGui>, int)>> renderCallbackList;

    std::set<std::shared_ptr<CGameGraphicsObject>> children;
    std::weak_ptr<CGameGraphicsObject> parent;

    std::shared_ptr<CLayout> layout;
    int priority = 0;
public:

    int getPriority();

    void setPriority(int priority);

    std::set<std::shared_ptr<CGameGraphicsObject>> getChildren();

    void setChildren(std::set<std::shared_ptr<CGameGraphicsObject>> _children);

    virtual bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i);

    virtual bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y);

    virtual void renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                               std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func);

    void registerRenderCallback(std::function<void(std::shared_ptr<CGui>, int)> cb);

    std::shared_ptr<CGameGraphicsObject> getParent();

    std::shared_ptr<CGameGraphicsObject> getTopParent();

    void setParent(std::shared_ptr<CGameGraphicsObject> _parent);

    std::shared_ptr<CLayout> getLayout();

    void setLayout(std::shared_ptr<CLayout> layout);

    void addChild(std::shared_ptr<CGameGraphicsObject> child);

    void pushChild(std::shared_ptr<CGameGraphicsObject> child);

    void removeChild(std::shared_ptr<CGameGraphicsObject> child);

    void removeParent();

private:
    virtual void render(std::shared_ptr<CGui> reneder, int frameTime);

    virtual bool event(std::shared_ptr<CGui> gui, SDL_Event *event);

    int getTopPriority();

    std::shared_ptr<SDL_Rect> getRect();
};

