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
#include "handler/CHandler.h"


std::string CGameEvent::Type::onEnter = "onEnter";
std::string CGameEvent::Type::onTurn = "onTurn";
std::string CGameEvent::Type::onCreate = "onCreate";
std::string CGameEvent::Type::onDestroy = "onDestroy";
std::string CGameEvent::Type::onLeave = "onLeave";
std::string CGameEvent::Type::onUse = "onUse";
std::string CGameEvent::Type::onEquip = "onEquip";
std::string CGameEvent::Type::onUnequip = "onUnequip";


void CEventHandler::gameEvent(std::shared_ptr<CMapObject> object, std::shared_ptr<CGameEvent> event) const {
//TODO: maybe add reflection
    if (event->getType() == CGameEvent::Type::onEnter) {
        vstd::cast<Visitable>(object)->onEnter(event);
    } else if (event->getType() == CGameEvent::Type::onLeave) {
        vstd::cast<Visitable>(object)->onLeave(event);
    } else if (event->getType() == CGameEvent::Type::onTurn) {
        vstd::cast<Turnable>(object)->onTurn(event);
    } else if (event->getType() == CGameEvent::Type::onDestroy) {
        vstd::cast<Creatable>(object)->onDestroy(event);
    } else if (event->getType() == CGameEvent::Type::onCreate) {
        vstd::cast<Creatable>(object)->onCreate(event);
    } else if (event->getType() == CGameEvent::Type::onUse) {
        vstd::cast<Usable>(object)->onUse(event);
    } else if (event->getType() == CGameEvent::Type::onEquip) {
        vstd::cast<Wearable>(object)->onEquip(event);
    } else if (event->getType() == CGameEvent::Type::onUnequip) {
        vstd::cast<Wearable>(object)->onUnequip(event);
    } else {
        vstd::logger::fatal("Unrecognized event type:", event->getType());
    }

    auto range = triggers.equal_range(std::make_pair(object->getName(), event->getType()));
    std::for_each(
            range.first,
            range.second,
            [object, event](TriggerMap::value_type x) {
                x.second->trigger(object, event);
            }
    );
}

void CEventHandler::registerTrigger(std::shared_ptr<CTrigger> trigger) {
    triggers.insert(std::make_pair(std::make_pair(trigger->getObject(), trigger->getEvent()), trigger));
}

std::set<std::shared_ptr<CTrigger>> CEventHandler::getTriggers() {
    std::set<std::shared_ptr<CTrigger>> triggers;
    for (auto trigger: this->triggers | boost::adaptors::map_values) {
        triggers.insert(trigger);
    }
    return triggers;
}

CGameEvent::CGameEvent(std::string type) : type(type) {

}

std::string CGameEvent::getType() const {
    return type;
}

std::shared_ptr<CGameObject> CGameEventCaused::getCause() const {
    return cause;
}

CGameEventCaused::CGameEventCaused(std::string type, std::shared_ptr<CGameObject> cause) : CGameEvent(type),
                                                                                           cause(cause) {

}

CGameEvent::CGameEvent() {

}

CGameEventCaused::CGameEventCaused() {

}