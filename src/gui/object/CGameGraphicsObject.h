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

class CProxyGraphicsObject;

class CProxyTargetGraphicsObject;

class CScript;

class CGameGraphicsObject;

//TODO: generify
struct priority_comparator {
    bool operator()(
            const std::shared_ptr<CGameGraphicsObject> &a, const std::shared_ptr<CGameGraphicsObject> &b) const;
};

class CGameGraphicsObject : public CGameObject {
    //TODO: replace with interceptor
    friend class CGui;

    friend class CProxyGraphicsObject;

    friend class CProxyTargetGraphicsObject;

V_META(CGameGraphicsObject, CGameObject,
       V_PROPERTY(CGameGraphicsObject, int, priority, getPriority, setPriority),
       V_PROPERTY(CGameGraphicsObject, std::shared_ptr<CLayout>, layout, getLayout, setLayout),
       V_PROPERTY(CGameGraphicsObject,
                  std::set<std::shared_ptr<CGameGraphicsObject>>, children, getChildren, setChildren),
       V_PROPERTY(CGameGraphicsObject, bool, modal, getModal, setModal),
       V_PROPERTY(CGameGraphicsObject, std::shared_ptr<CScript>, visible, getVisible, setVisible))

    std::list<std::pair<std::function<bool(std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>,
                                           SDL_Event *)>, std::function<bool(
            std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *) >>> eventCallbackList;

    std::set<std::shared_ptr<CGameGraphicsObject>, priority_comparator> children;
    std::weak_ptr<CGameGraphicsObject> parent;

    std::shared_ptr<CLayout> layout;
    int priority = 0;

public:
    int getPriority();

    void setPriority(int priority);

    std::set<std::shared_ptr<CGameGraphicsObject>> getChildren();

    void setChildren(std::set<std::shared_ptr<CGameGraphicsObject>> _children);

    virtual bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i);

    virtual bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y);

    virtual void renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void registerEventCallback(
            std::function<bool(std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *)> pred,
            std::function<bool(std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *)> func);

    //TODO: add posibility to search for parent with type or name
    std::shared_ptr<CGameGraphicsObject> getParent();

    std::shared_ptr<CGameGraphicsObject> getTopParent();

    void setParent(std::shared_ptr<CGameGraphicsObject> _parent);

    std::shared_ptr<CLayout> getLayout();

    void setLayout(std::shared_ptr<CLayout> layout);

    void addChild(const std::shared_ptr<CGameGraphicsObject> &child);

    void pushChild(const std::shared_ptr<CGameGraphicsObject> &child);

    void removeChild(const std::shared_ptr<CGameGraphicsObject> &child);

    //TODO: more flexible
    std::shared_ptr<CGameGraphicsObject> findChild(const std::string &type);

    std::shared_ptr<CGameGraphicsObject> findChild(const std::shared_ptr<CGameGraphicsObject> &type);

    void removeParent();

    std::shared_ptr<CGui> getGui();

    bool getModal();

    void setModal(bool _modal);

    std::shared_ptr<CScript> getVisible();

    void setVisible(std::shared_ptr<CScript> hidden);

    bool isVisible();

    std::string getBackground();

    void setBackground(std::string _background);

    int getTileSize(const std::shared_ptr<CGameGraphicsObject> &object);

private:
    virtual void render(std::shared_ptr<CGui> reneder, int frameTime);

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event);

    int getTopPriority();

    std::shared_ptr<SDL_Rect> getRect();

    std::shared_ptr<CScript> visible;

    void renderBackground(std::shared_ptr<CGui> sharedPtr, std::shared_ptr<SDL_Rect> rect, int time);

    std::string background;

    bool modal = false;
};

