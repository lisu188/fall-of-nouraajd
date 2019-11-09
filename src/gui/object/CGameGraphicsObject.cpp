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
#include "gui/panel/CGamePanel.h"
#include "CGameGraphicsObject.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"

void CGameGraphicsObject::renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime) {

}

void CGameGraphicsObject::render(std::shared_ptr<CGui> reneder, int frameTime) {
    renderObject(reneder,getRect(), frameTime);
    for (auto child:children) {
        child->renderObject(reneder, child->getRect(), frameTime);
    }
}

bool CGameGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    for (auto child:children) {
        if (child->event(gui, event)) {
            return true;
        }
    }
    for (auto callback:eventCallbackList) {
        if (callback.first(gui, event) && callback.second(gui, event)) {
            return true;
        }
    }
    if (event->type == SDL_KEYDOWN ||
        event->type == SDL_KEYUP) {
        return this->keyboardEvent(gui, (SDL_EventType) event->type, event->key.keysym.sym);
    } else if (event->type == SDL_MOUSEBUTTONDOWN ||
               event->type == SDL_MOUSEBUTTONUP) {
        std::shared_ptr<SDL_Rect> transPos = getRect();
        if (CUtil::isIn(transPos, event->button.x, event->button.y)) {
            return this->mouseEvent(gui, (SDL_EventType) event->type, event->button.x - transPos->x,
                                    event->button.y - transPos->y);
        }
    }
    return false;
}

bool CGameGraphicsObject::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    return false;
}

bool CGameGraphicsObject::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) {
    return false;
}

void
CGameGraphicsObject::registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                                           std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func) {
    eventCallbackList.emplace_back(pred, func);
}

std::shared_ptr<CLayout> CGameGraphicsObject::getLayout() {
    return layout;
}

void CGameGraphicsObject::setLayout(std::shared_ptr<CLayout> layout) {
    CGameGraphicsObject::layout = layout;
}

std::shared_ptr<SDL_Rect> CGameGraphicsObject::getRect() {
    return layout->getRect(this->ptr<CGameGraphicsObject>());
}

void CGameGraphicsObject::setParent(std::shared_ptr<CGameGraphicsObject> _parent) {
    this->parent = _parent;
    _parent->addChild(this->ptr<CGameGraphicsObject>());
}

std::shared_ptr<CGameGraphicsObject> CGameGraphicsObject::getParent() {
    return parent.lock();
}

void CGameGraphicsObject::addChild(std::shared_ptr<CGameGraphicsObject> child) {
    if (children.insert(child).second) {
        child->setParent(this->ptr<CGameGraphicsObject>());
    }
}

void CGameGraphicsObject::removeChild(std::shared_ptr<CGameGraphicsObject> child) {
    if (children.erase(child)) {
        child->removeParent();
    }
}

void CGameGraphicsObject::removeParent() {
    parent.lock()->removeChild(this->ptr<CGameGraphicsObject>());
    parent.reset();
}

std::shared_ptr<CGameGraphicsObject> CGameGraphicsObject::getTopParent() {
    if (auto _parent = getParent()) {
        return _parent->getTopParent();
    }
    return this->ptr<CGameGraphicsObject>();
}

std::set<std::shared_ptr<CGameGraphicsObject>> CGameGraphicsObject::getChildren() {
    return children;
}

void CGameGraphicsObject::setChildren(std::set<std::shared_ptr<CGameGraphicsObject>> _children) {
    for (auto child:_children) {
        addChild(child);
    }
}
