/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "object/CGameObject.h"
#include "core/CGame.h"
#include "core/CList.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CPythonOverrides.h"
#include "gui/CAnimation.h"

#include <any>
#include <map>
#include <typeindex>
#include <utility>

namespace {

using ObjectPair = std::pair<const CGameObject *, const CGameObject *>;

bool isEquivalentValueType(std::type_index type) {
    return type == std::type_index(typeid(bool)) || type == std::type_index(typeid(int)) ||
           type == std::type_index(typeid(std::string)) || type == std::type_index(typeid(CTags)) ||
           type == std::type_index(typeid(std::set<int>)) || type == std::type_index(typeid(std::set<std::string>)) ||
           type == std::type_index(typeid(std::map<int, int>)) ||
           type == std::type_index(typeid(std::map<int, std::string>)) ||
           type == std::type_index(typeid(std::map<std::string, int>)) ||
           type == std::type_index(typeid(std::map<std::string, std::string>));
}

template <typename T> bool sameAnyValue(const std::any &a, const std::any &b) {
    return std::any_cast<T>(a) == std::any_cast<T>(b);
}

bool sameEquivalentValue(const std::any &a, const std::any &b, std::type_index type) {
    try {
        if (type == std::type_index(typeid(bool))) {
            return sameAnyValue<bool>(a, b);
        }
        if (type == std::type_index(typeid(int))) {
            return sameAnyValue<int>(a, b);
        }
        if (type == std::type_index(typeid(std::string))) {
            return sameAnyValue<std::string>(a, b);
        }
        if (type == std::type_index(typeid(CTags))) {
            return sameAnyValue<CTags>(a, b);
        }
        if (type == std::type_index(typeid(std::set<int>))) {
            return sameAnyValue<std::set<int>>(a, b);
        }
        if (type == std::type_index(typeid(std::set<std::string>))) {
            return sameAnyValue<std::set<std::string>>(a, b);
        }
        if (type == std::type_index(typeid(std::map<int, int>))) {
            return sameAnyValue<std::map<int, int>>(a, b);
        }
        if (type == std::type_index(typeid(std::map<int, std::string>))) {
            return sameAnyValue<std::map<int, std::string>>(a, b);
        }
        if (type == std::type_index(typeid(std::map<std::string, int>))) {
            return sameAnyValue<std::map<std::string, int>>(a, b);
        }
        if (type == std::type_index(typeid(std::map<std::string, std::string>))) {
            return sameAnyValue<std::map<std::string, std::string>>(a, b);
        }
    } catch (const std::bad_any_cast &) {
        return false;
    }
    return false;
}

bool collectEquivalentValueProperties(const std::shared_ptr<CGameObject> &object,
                                      std::map<std::string, std::type_index> &properties) {
    bool supported = true;
    object->meta()->for_all_properties(object, [&](auto property) {
        const auto type = property->value_type();
        if (!isEquivalentValueType(type)) {
            supported = false;
            return;
        }
        properties.emplace(property->name(), type);
    });
    return supported;
}

bool equivalentValueInternal(const std::shared_ptr<CGameObject> &a, const std::shared_ptr<CGameObject> &b,
                             std::set<ObjectPair> &visited) {
    if (CGameObject::sameInstance(a, b)) {
        return true;
    }
    if (!a || !b) {
        return false;
    }
    if (!visited.insert({a.get(), b.get()}).second) {
        return true;
    }
    if (a->meta()->name() != b->meta()->name()) {
        return false;
    }

    std::map<std::string, std::type_index> aProperties;
    std::map<std::string, std::type_index> bProperties;
    if (!collectEquivalentValueProperties(a, aProperties) || !collectEquivalentValueProperties(b, bProperties) ||
        aProperties != bProperties) {
        return false;
    }

    for (const auto &[name, type] : aProperties) {
        bool sameValue = false;
        try {
            sameValue = sameEquivalentValue(a->getProperty<std::any>(name), b->getProperty<std::any>(name), type);
        } catch (const std::exception &) {
            return false;
        }
        if (!sameValue) {
            return false;
        }
    }
    return true;
}

} // namespace

std::function<bool(std::shared_ptr<CGameObject>, std::shared_ptr<CGameObject>)> CGameObject::name_comparator =
    [](std::shared_ptr<CGameObject> a, std::shared_ptr<CGameObject> b) {
        return CGameObject::sameConfiguredType(a, b);
    };

CGameObject::~CGameObject() { CPythonOverrides::release(this); }

CGameObject::CGameObject() {}

bool CGameObject::sameInstance(const std::shared_ptr<CGameObject> &a, const std::shared_ptr<CGameObject> &b) {
    return a == b;
}

bool CGameObject::sameRuntimeIdentity(const std::shared_ptr<CGameObject> &a, const std::shared_ptr<CGameObject> &b) {
    if (sameInstance(a, b)) {
        return true;
    }
    if (!a || !b) {
        return false;
    }
    auto aMap = a->owningMap.lock();
    auto bMap = b->owningMap.lock();
    if (!aMap || !bMap || aMap != bMap) {
        return false;
    }
    return !a->getName().empty() && a->getName() == b->getName();
}

bool CGameObject::sameConfiguredType(const std::shared_ptr<CGameObject> &a, const std::shared_ptr<CGameObject> &b) {
    if (sameInstance(a, b)) {
        return true;
    }
    if (!a || !b) {
        return false;
    }
    if (!a->getTypeId().empty() || !b->getTypeId().empty()) {
        return a->getTypeId() == b->getTypeId();
    }
    return a->getType() == b->getType() && a->getName() == b->getName();
}

bool CGameObject::equivalentValue(const std::shared_ptr<CGameObject> &a, const std::shared_ptr<CGameObject> &b) {
    std::set<ObjectPair> visited;
    return equivalentValueInternal(a, b, visited);
}

CGameObject::PropertyNotificationBatch::PropertyNotificationBatch(CGameObject &object) : object(object) {
    this->object.beginPropertyNotificationBatch();
}

CGameObject::PropertyNotificationBatch::~PropertyNotificationBatch() { object.endPropertyNotificationBatch(); }

std::shared_ptr<CMap> CGameObject::getMap() {
    if (auto map = owningMap.lock()) {
        return map;
    }
    auto currentGame = getGame();
    return currentGame ? currentGame->getMap() : nullptr;
}

std::shared_ptr<CGame> CGameObject::getGame() { return game.lock(); }

void CGameObject::setGame(std::shared_ptr<CGame> map) { this->game = map; }

void CGameObject::setOwningMap(std::shared_ptr<CMap> map) { this->owningMap = std::move(map); }

void CGameObject::clearOwningMap(const std::shared_ptr<CMap> &expectedMap) {
    auto map = owningMap.lock();
    if (!map || (expectedMap && map != expectedMap)) {
        return;
    }
    owningMap.reset();
}

void CGameObject::setStringProperty(std::string name, std::string value) {
    std::string previous;
    const bool traceQuestState = CPlaytestTrace::enabled() && name.starts_with("quest_state_");
    if (traceQuestState) {
        previous = getStringProperty(name);
    }
    this->setProperty(name, value);
    if (traceQuestState && previous != value) {
        json fields = {
            {"current", value},     {"object", CPlaytestTrace::objectRef(this->ptr<CGameObject>())},
            {"previous", previous}, {"quest", name.substr(std::string("quest_state_").size())},
            {"questKey", name},
        };
        CPlaytestTrace::addMapContext(fields, std::dynamic_pointer_cast<CMap>(this->ptr<CGameObject>()));
        CPlaytestTrace::record("quest_state_changed", fields);
    }
}

void CGameObject::setBoolProperty(std::string name, bool value) { this->setProperty(name, value); }

void CGameObject::setNumericProperty(std::string name, int value) { this->setProperty(name, value); }

std::string CGameObject::getStringProperty(std::string name) {
    return this->hasProperty(name) ? this->getProperty<std::string>(name) : "";
}

bool CGameObject::getBoolProperty(std::string name) { return this->hasProperty(name) && this->getProperty<bool>(name); }

int CGameObject::getNumericProperty(std::string name) {
    return this->hasProperty(name) ? this->getProperty<int>(name) : 0;
}

void CGameObject::incProperty(std::string name, int value) {
    this->setNumericProperty(name, this->getNumericProperty(name) + value);
}

std::string CGameObject::to_string() { return vstd::join({getType(), getName()}, ":"); }

std::shared_ptr<CGameObject> CGameObject::_clone() {
    auto currentGame = getGame();
    return currentGame ? currentGame->getObjectHandler()->clone<CGameObject>(this->ptr()) : nullptr;
}

CTags CGameObject::getTags() { return tags; }

void CGameObject::setTags(CTags tags) { CGameObject::tags = std::move(tags); }

std::string CGameObject::getType() { return type; }

void CGameObject::setType(std::string type) { this->type = type; }

std::string CGameObject::getName() { return name; }

void CGameObject::setName(std::string name) { this->name = name; }

bool CGameObject::hasTag(CTag tag) { return tags.contains(tag); }

bool CGameObject::hasTag(const std::string &tag) { return hasTag(CTags::fromString(tag)); }

void CGameObject::addTag(CTag tag) { tags.insert(tag); }

void CGameObject::addTag(const std::string &tag) { addTag(CTags::fromString(tag)); }

void CGameObject::removeTag(CTag tag) { tags.erase(tag); }

void CGameObject::removeTag(const std::string &tag) { removeTag(CTags::fromString(tag)); }

std::string CGameObject::getAnimation() { return animation; }

void CGameObject::setAnimation(std::string animation) {
    this->animation = std::move(animation);
    recordDirectPropertyChanged("animation");
}

std::string CGameObject::getLabel() { return label; }

void CGameObject::setLabel(std::string _label) { label = _label; }

std::string CGameObject::getDescription() { return description; }

void CGameObject::setDescription(std::string _description) { description = _description; }

std::shared_ptr<CAnimation> CGameObject::getGraphicsObject() {
    return graphicsObject.get([this]() {
        auto currentGame = getGame();
        if (!currentGame) {
            return std::shared_ptr<CAnimation>();
        }
        std::shared_ptr<CAnimation> anim = CAnimationProvider::getAnimation(currentGame, this->ptr<CGameObject>());
        if (!anim) {
            return anim;
        }
        auto priorities = currentGame->createObject<CMapStringInt>("mapObjectPriorities");
        if (!priorities) {
            return anim;
        }
        for (auto [key, val] : priorities->getValues()) {
            if (val > anim->getPriority() && this->meta()->inherits(key)) {
                anim->setPriority(val);
            }
        }
        return anim;
    });
}

void CGameObject::connect(std::string signal, std::shared_ptr<CGameObject> object, std::string slot) {
    connections.emplace_back(signal, object, slot);
}

void CGameObject::disconnect(const std::string &signal, const std::shared_ptr<CGameObject> &object,
                             const std::string &slot) {
    auto it = connections.begin();
    while (it != connections.end()) {
        auto &[connectedSignal, connectedObject, connectedSlot] = *it;
        auto target = connectedObject.lock();
        if (!target || (connectedSignal == signal && target == object && connectedSlot == slot)) {
            it = connections.erase(it);
            continue;
        }
        ++it;
    }
}

void CGameObject::notifyPropertyChanged(const std::string &name) {
    invalidateCachedPropertyState(name);
    notifyPropertyChangedWithoutInvalidation(name);
}

void CGameObject::notifyPropertyChangedWithoutInvalidation(const std::string &name) {
    signal("propertyChanged", name);
    signal(name + "Changed");
}

void CGameObject::notifyPropertiesChanged(const std::set<std::string> &names) {
    invalidateCachedPropertyState(names);
    notifyPropertiesChangedWithoutInvalidation(names);
}

void CGameObject::notifyPropertiesChangedWithoutInvalidation(const std::set<std::string> &names) {
    if (!names.empty()) {
        signal("propertiesChanged", names);
    }
}

void CGameObject::beginPropertyNotificationBatch() { ++propertyNotificationBatchDepth; }

void CGameObject::endPropertyNotificationBatch() {
    if (propertyNotificationBatchDepth <= 0) {
        return;
    }
    --propertyNotificationBatchDepth;
    if (propertyNotificationBatchDepth > 0 || batchedPropertyNotifications.empty()) {
        return;
    }
    auto names = std::move(batchedPropertyNotifications);
    batchedPropertyNotifications.clear();
    notifyPropertiesChangedWithoutInvalidation(names);
}

void CGameObject::recordPropertyChanged(const std::string &name) {
    invalidateCachedPropertyState(name);
    if (propertyNotificationBatchDepth > 0) {
        batchedPropertyNotifications.insert(name);
        return;
    }
    notifyPropertyChangedWithoutInvalidation(name);
}

void CGameObject::recordDirectPropertyChanged(const std::string &name) {
    for (const auto &suppressedName : directPropertyNotificationSuppressedNames) {
        if (suppressedName == name) {
            return;
        }
    }
    recordPropertyChanged(name);
}

void CGameObject::invalidateCachedPropertyState(const std::string &name) {
    if (name == "animation") {
        graphicsObject.clear();
    }
}

void CGameObject::invalidateCachedPropertyState(const std::set<std::string> &names) {
    if (names.contains("animation")) {
        graphicsObject.clear();
    }
}

bool CGameObject::hasProperty(std::string name) { return this->meta()->has_property<CGameObject>(name, this->ptr()); }

void CGameObject::setTypeId(std::string _typeId) { typeId = _typeId; }

std::string CGameObject::getTypeId() { return typeId; }
