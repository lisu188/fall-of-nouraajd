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
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "core/CScript.h"
#include "gui/CTextureCache.h"

void CGameGraphicsObject::renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime) {

}

void CGameGraphicsObject::render(std::shared_ptr<CGui> reneder, int frameTime) {
    if (isVisible()) {
        renderBackground(reneder, getRect(), frameTime);
        renderObject(reneder, getRect(), frameTime);
        std::set<std::shared_ptr<CGameGraphicsObject>,
                priority_comparator> children_sorted(children.begin(),
                                                     children.end());
        for (auto child:children_sorted) {
            child->render(reneder, frameTime);
        }
    }
}

bool CGameGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (isVisible()) {
        std::set<std::shared_ptr<CGameGraphicsObject>,
                reverse_priority_comparator> children_reversed(children.begin(),
                                                               children.end());
        for (auto child:children_reversed) {
            if (child->event(gui, event)) {
                return true;
            }
        }
        for (auto callback:eventCallbackList) {//TODO:remove, replace with other event
            if (callback.first(gui, this->ptr<CGameGraphicsObject>(), event) &&
                callback.second(gui, this->ptr<CGameGraphicsObject>(), event)) {
                return true;
            }
        }
        if (event->type == SDL_KEYDOWN ||
            event->type == SDL_KEYUP) {
            return this->keyboardEvent(gui, (SDL_EventType) event->type, event->key.keysym.sym);
        } else if (event->type == SDL_MOUSEBUTTONDOWN ||
                   event->type == SDL_MOUSEBUTTONUP) {
            std::shared_ptr<SDL_Rect> transPos = getRect();
            if (CUtil::isIn(transPos, event->button.x, event->button.y) || modal) {
                return this->mouseEvent(gui, (SDL_EventType) event->type,
                                        event->button.button,
                                        event->button.x - transPos->x,
                                        event->button.y - transPos->y);
            }
        }
        //TODO: check if we are not consuming too many events
        return modal;
    }
    return false;
}

bool CGameGraphicsObject::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    return false;
}

bool CGameGraphicsObject::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) {
    return false;
}

void
CGameGraphicsObject::registerEventCallback(
        std::function<bool(std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *)> pred,
        std::function<bool(std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *)> func) {
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
    if (parent.lock() != _parent) {
        this->parent = _parent;
        _parent->addChild(this->ptr<CGameGraphicsObject>());
    }
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
    if (parent.lock()) {
        parent.lock()->removeChild(this->ptr<CGameGraphicsObject>());
        parent.reset();
    }
}

std::shared_ptr<CGameGraphicsObject> CGameGraphicsObject::getTopParent() {
    if (auto _parent = getParent()) {
        return _parent->getTopParent();
    }
    return this->ptr<CGameGraphicsObject>();
}

std::set<std::shared_ptr<CGameGraphicsObject>> CGameGraphicsObject::getChildren() {
    return vstd::cast<std::set<std::shared_ptr<CGameGraphicsObject>>>(children);
}

void CGameGraphicsObject::setChildren(std::set<std::shared_ptr<CGameGraphicsObject>> _children) {
    //TODO: doChecks if some of children are already present
    children.clear();
    for (auto child:_children) {
        addChild(child);
    }
}

int CGameGraphicsObject::getPriority() {
    return priority;
}

void CGameGraphicsObject::setPriority(int priority) {
    this->priority = priority;
}

int CGameGraphicsObject::getTopPriority() {
    auto iterator = std::max_element(
            children.begin(), children.end(), priority_comparator());
    if (iterator != children.end()) {
        return (*iterator)->getPriority();
    }
    return -1;
}

void CGameGraphicsObject::pushChild(std::shared_ptr<CGameGraphicsObject> child) {
    child->setPriority(getTopPriority() + 1);
    addChild(child);
}

std::shared_ptr<CGui> CGameGraphicsObject::getGui() {
    return vstd::cast<CGui>(getTopParent());
}

bool CGameGraphicsObject::getModal() {
    return modal;
}

void CGameGraphicsObject::setModal(bool _modal) {
    modal = _modal;
}

std::shared_ptr<CGameGraphicsObject> CGameGraphicsObject::findChild(std::string type) {
    for (auto child:getChildren()) {
        if (auto found = child->findChild(type)) {
            return found;
        }
        if (child->getType() == type) {
            return child;
        }
    }
    return nullptr;
}


std::shared_ptr<CGameGraphicsObject> CGameGraphicsObject::findChild(std::shared_ptr<CGameGraphicsObject> toFind) {
    for (auto child:getChildren()) {
        if (auto found = child->findChild(toFind)) {
            return found;
        }
        if (child == toFind) {
            return child;
        }
    }
    return nullptr;
}

std::shared_ptr<CScript> CGameGraphicsObject::getVisible() {
    return visible;
}

void CGameGraphicsObject::setVisible(std::shared_ptr<CScript> visible) {
    CGameGraphicsObject::visible = visible;
}

bool CGameGraphicsObject::isVisible() {
    return !visible || visible->invoke<CGameObject>(getGame(), this->ptr<CGameObject>()) != nullptr;
}

void CGameGraphicsObject::renderBackground(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int time) {
    if (!background.empty()) {
        SDL_SAFE(SDL_RenderCopy(gui->getRenderer(),
                                gui->getTextureCache()->getTexture(background), nullptr, rect.get()));
    }
}

std::string CGameGraphicsObject::getBackground() {
    return background;
}

void CGameGraphicsObject::setBackground(std::string _background) {
    background = _background;
}

bool priority_comparator::operator()(std::shared_ptr<CGameGraphicsObject> a,
                                     std::shared_ptr<CGameGraphicsObject> b) const {
    if (a->getPriority() == b->getPriority()) {
        return a < b;
    }
    return a->getPriority() < b->getPriority();
}

bool reverse_priority_comparator::operator()(std::shared_ptr<CGameGraphicsObject> a,
                                             std::shared_ptr<CGameGraphicsObject> b) const {
    return priority_comparator()(b, a);
}
int CGameGraphicsObject::getTileSize(
        std::shared_ptr<CGameGraphicsObject> object) {
    if (object->hasProperty("tileSize")) {
        return object->getNumericProperty("tileSize");
    }
    return getTileSize(object->getParent());
}