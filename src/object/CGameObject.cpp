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
#include "core/CList.h"
#include "object/CGameObject.h"
#include "core/CMap.h"
#include "gui/CAnimation.h"
#include "core/CMap.h"
#include "core/CGame.h"

std::function<bool(std::shared_ptr<CGameObject>, std::shared_ptr<CGameObject>)> CGameObject::name_comparator = [](
        std::shared_ptr<CGameObject> a, std::shared_ptr<CGameObject> b) {
    return a->getType() == b->getType();
};

CGameObject::~CGameObject() {

}

CGameObject::CGameObject() {

}

std::shared_ptr<CMap> CGameObject::getMap() {
    return getGame()->getMap();
}

std::shared_ptr<CGame> CGameObject::getGame() {
    return game;
}

void CGameObject::setGame(std::shared_ptr<CGame> map) {
    this->game = map;
}

void CGameObject::setStringProperty(std::string name, std::string value) {
    this->setProperty(name, value);
}

void CGameObject::setBoolProperty(std::string name, bool value) {
    this->setProperty(name, value);
}

void CGameObject::setNumericProperty(std::string name, int value) {
    this->setProperty(name, value);
}

std::string CGameObject::getStringProperty(std::string name) {
    return this->getProperty<std::string>(name);
}

bool CGameObject::getBoolProperty(std::string name) {
    return this->getProperty<bool>(name);
}

int CGameObject::getNumericProperty(std::string name) {
    return this->getProperty<int>(name);
}

void CGameObject::incProperty(std::string name, int value) {
    this->setNumericProperty(name, this->getNumericProperty(name) + value);
}

std::string CGameObject::to_string() {
    return vstd::join({getType(), getName()}, ":");
}

std::shared_ptr<CGameObject> CGameObject::_clone() {
    return game->getObjectHandler()->clone<CGameObject>(this->ptr());
}

std::set<std::string> CGameObject::getTags() {
    return tags;
}

void CGameObject::setTags(std::set<std::string> tags) {
    CGameObject::tags = tags;
}

std::string CGameObject::getType() {
    return type;
}

void CGameObject::setType(std::string type) {
    this->type = type;
}

std::string CGameObject::getName() {
    return name;
}

void CGameObject::setName(std::string name) {
    this->name = name;
}

bool CGameObject::hasTag(std::string tag) {
    return vstd::ctn(tags, tag);
}

void CGameObject::addTag(std::string tag) {
    tags.insert(tag);
}

void CGameObject::removeTag(std::string tag) {
    tags.erase(tag);
}

std::string CGameObject::getAnimation() {
    return animation;
}

void CGameObject::setAnimation(std::string animation) {
    //TODO: implement this in AOP way
    graphicsObject.clear();
    this->animation = animation;
}

std::string CGameObject::getLabel() {
    return label;
}

void CGameObject::setLabel(std::string _label) {
    label = _label;
}

std::string CGameObject::getDescription() {
    return description;
}

void CGameObject::setDescription(std::string _description) {
    description = _description;
}


std::shared_ptr<CGameGraphicsObject> CGameObject::getGraphicsObject() {
    return graphicsObject.get([this]() {
        std::shared_ptr<CAnimation> anim = CAnimationProvider::getAnimation(getGame(), this->ptr<CGameObject>());
        for (auto[key, val] :getGame()->createObject<CMapStringInt>("mapObjectPriorities")->getValues()) {
            if (val > anim->getPriority() && this->meta()->inherits(key)) {
                anim->setPriority(val);
            }
        }
        return anim;
    });
}

void CGameObject::connect(std::string signal, std::shared_ptr<CGameObject> object, std::string slot) {
    connections.push_back(std::make_tuple(signal, object, slot));
}

bool CGameObject::hasProperty(std::string name) {
    return this->meta()->has_property<CGameObject>(name, this->ptr());
}

void CGameObject::setTypeId(std::string _typeId) {
    typeId = _typeId;
}

std::string CGameObject::getTypeId() {
    return typeId;
}