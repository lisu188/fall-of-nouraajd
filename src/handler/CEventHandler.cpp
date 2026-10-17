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
#include "handler/CHandler.h"
#include "core/CAsync.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"

std::string CGameEvent::CType::onEnter = "onEnter";
std::string CGameEvent::CType::onTurn = "onTurn";
std::string CGameEvent::CType::onCreate = "onCreate";
std::string CGameEvent::CType::onDestroy = "onDestroy";
std::string CGameEvent::CType::onLeave = "onLeave";
std::string CGameEvent::CType::onUse = "onUse";
std::string CGameEvent::CType::onEquip = "onEquip";
std::string CGameEvent::CType::onUnequip = "onUnequip";

namespace {
vstd::task<bool> invokeObjectFlowAsync(std::shared_ptr<CGameObject> object, std::string method,
                                       std::vector<std::shared_ptr<CGameObject>> arguments,
                                       std::weak_ptr<CGame> weakGame,
                                       std::shared_ptr<std::move_only_function<void()>> commit = {},
                                       std::shared_ptr<std::move_only_function<void()>> prepareCommit = {}) {
    try {
        auto flow = CScriptHandler::createObjectFlow(object, method, arguments, weakGame, {}, commit, prepareCommit);
        if (!flow) {
            co_return false;
        }
        auto game = weakGame.lock();
        if (!game) {
            throw std::runtime_error("Cannot run a script event after its game has been destroyed.");
        }
        auto gui = game->getGuiHandler();
        game.reset();
        co_await gui->runScriptFlowAsync(std::move(flow));
    } catch (const vstd::task_cancelled &) {
        throw;
    } catch (const vstd::scheduler_rejected &) {
        throw;
    } catch (const std::exception &error) {
        vstd::logger::error("Script event flow failed:", method, error.what());
    }
    co_return true;
}

json captureObjectEntry(const std::shared_ptr<CMapObject> &object, const std::shared_ptr<CGameEvent> &event) {
    json entry_fields;
    if (object && event && CPlaytestTrace::enabled() && event->getType() == CGameEvent::CType::onEnter) {
        auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
        auto cause = caused ? std::dynamic_pointer_cast<CMapObject>(caused->getCause()) : nullptr;
        auto map = object->getMap();
        if (map && cause && cause->getMap() == map && object->getCoords() == cause->getCoords() &&
            map->getObjectByName(object->getName()) == object && map->getObjectByName(cause->getName()) == cause) {
            entry_fields = {{"target", CPlaytestTrace::objectRef(object)},
                            {"cause", CPlaytestTrace::objectRef(cause)},
                            {"targetCoords", CPlaytestTrace::coords(object->getCoords())},
                            {"causeCoords", CPlaytestTrace::coords(cause->getCoords())}};
            CPlaytestTrace::addMapContext(entry_fields, map);
        }
    }
    return entry_fields;
}

void dispatchObjectEvent(const std::shared_ptr<CMapObject> &object, const std::shared_ptr<CGameEvent> &event) {
    if (!object || !event) {
        return;
    }
    // TODO: maybe add reflection
    if (event->getType() == CGameEvent::CType::onEnter) {
        if (auto visitable = vstd::cast<CVisitable>(object)) {
            visitable->onEnter(event);
        }
    } else if (event->getType() == CGameEvent::CType::onLeave) {
        if (auto visitable = vstd::cast<CVisitable>(object)) {
            visitable->onLeave(event);
        }
    } else if (event->getType() == CGameEvent::CType::onTurn) {
        if (auto turnable = vstd::cast<CTurnable>(object)) {
            turnable->onTurn(event);
        }
    } else if (event->getType() == CGameEvent::CType::onDestroy) {
        if (auto creatable = vstd::cast<CCreatable>(object)) {
            creatable->onDestroy(event);
        }
    } else if (event->getType() == CGameEvent::CType::onCreate) {
        if (auto creatable = vstd::cast<CCreatable>(object)) {
            creatable->onCreate(event);
        }
    } else if (event->getType() == CGameEvent::CType::onUse) {
        if (auto usable = vstd::cast<CUsable>(object)) {
            usable->onUse(event);
        }
    } else if (event->getType() == CGameEvent::CType::onEquip) {
        if (auto wearable = vstd::cast<CWearable>(object)) {
            wearable->onEquip(event);
        }
    } else if (event->getType() == CGameEvent::CType::onUnequip) {
        if (auto wearable = vstd::cast<CWearable>(object)) {
            wearable->onUnequip(event);
        }
    } else {
        vstd::logger::fatal("Unrecognized event type:", event->getType());
    }
}
} // namespace

void CEventHandler::gameEvent(std::shared_ptr<CMapObject> object, std::shared_ptr<CGameEvent> event) const {
    if (!object || !event) {
        return;
    }
    auto entry_fields = captureObjectEntry(object, event);
    dispatchObjectEvent(object, event);
    auto range = triggers.equal_range(std::make_pair(object->getName(), event->getType()));
    std::for_each(range.first, range.second,
                  [object, event](TriggerMap::value_type x) { x.second->trigger(object, event); });
    if (!entry_fields.is_null()) {
        CPlaytestTrace::record("object_entered", std::move(entry_fields));
    }
}

vstd::task<void> CEventHandler::gameEventAsync(std::shared_ptr<CMapObject> object, std::shared_ptr<CGameEvent> event,
                                               std::shared_ptr<std::move_only_function<void()>> commit,
                                               std::shared_ptr<std::move_only_function<void()>> prepareCommit) {
    return [](std::shared_ptr<CEventHandler> self, std::shared_ptr<CMapObject> object,
              std::shared_ptr<CGameEvent> event, std::shared_ptr<std::move_only_function<void()>> commit,
              std::shared_ptr<std::move_only_function<void()>> prepareCommit) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        if (!object || !event) {
            co_return;
        }
        const auto stop = co_await vstd::thisTaskStopToken();
        auto owner = object->getGame();
        auto context = owner ? owner->getContext() : nullptr;
        std::weak_ptr<CGame> game = owner;
        owner.reset();
        const auto checkActive = [&] {
            if (stop.stop_requested() || (context && !context->isActive())) {
                throw vstd::task_cancelled();
            }
        };
        checkActive();
        auto entry_fields = captureObjectEntry(object, event);
        std::vector<std::shared_ptr<CGameObject>> arguments{event};
        auto objectCommit = event->getType() == CGameEvent::CType::onUse ? commit : nullptr;
        if (!(co_await invokeObjectFlowAsync(object, event->getType() + "Flow", std::move(arguments), game,
                                             objectCommit, prepareCommit))) {
            if (auto visitable = vstd::cast<CVisitable>(object);
                visitable && event->getType() == CGameEvent::CType::onEnter) {
                co_await visitable->onEnterAsync(event);
            } else {
                checkActive();
                if (objectCommit && prepareCommit) {
                    (*prepareCommit)();
                }
                checkActive();
                dispatchObjectEvent(object, event);
                if (objectCommit) {
                    (*objectCommit)();
                }
            }
        }
        checkActive();
        // Object hooks can register triggers; take the observer snapshot after they finish.
        auto range = self->triggers.equal_range(std::make_pair(object->getName(), event->getType()));
        std::vector<std::shared_ptr<CTrigger>> snapshot;
        for (auto it = range.first; it != range.second; ++it) {
            snapshot.push_back(it->second);
        }
        for (const auto &trigger : snapshot) {
            checkActive();
            if (!trigger) {
                continue;
            }
            std::vector<std::shared_ptr<CGameObject>> arguments{object, event};
            if (!(co_await invokeObjectFlowAsync(trigger, "triggerFlow", std::move(arguments), game))) {
                co_await trigger->triggerAsync(object, event);
            }
            checkActive();
        }
        if (!entry_fields.is_null()) {
            CPlaytestTrace::record("object_entered", std::move(entry_fields));
        }
    }(this->ptr<CEventHandler>(), std::move(object), std::move(event), std::move(commit), std::move(prepareCommit));
}

vstd::task<void> CEventHandler::tileStepAsync(std::shared_ptr<CTile> tile, std::shared_ptr<CCreature> creature) {
    auto loop = vstd::event_loop<>::instance();
    if (!loop->isMainThread()) {
        co_await vstd::post(loop);
    }
    if (!tile || !creature) {
        co_return;
    }
    const auto stop = co_await vstd::thisTaskStopToken();
    auto owner = creature->getGame();
    auto context = owner ? owner->getContext() : nullptr;
    std::weak_ptr<CGame> game = owner;
    owner.reset();
    const auto checkActive = [&] {
        if (stop.stop_requested() || (context && !context->isActive())) {
            throw vstd::task_cancelled();
        }
    };
    checkActive();
    std::vector<std::shared_ptr<CGameObject>> arguments{creature};
    if (!(co_await invokeObjectFlowAsync(tile, "onStepFlow", std::move(arguments), game))) {
        tile->onStep(creature);
    }
    checkActive();
}

void CEventHandler::registerTrigger(std::shared_ptr<CTrigger> trigger) {
    if (!trigger) {
        vstd::logger::warning("Ignoring null trigger registration");
        return;
    }
    const auto key = std::make_pair(trigger->getObject(), trigger->getEvent());
    auto range = triggers.equal_range(key);
    for (auto it = range.first; it != range.second; ++it) {
        const auto &existing = it->second;
        if (!existing) {
            continue;
        }
        const bool sameIdentity =
            CGameObject::sameInstance(existing, trigger) ||
            (existing->getType() == trigger->getType() && CGameObject::sameConfiguredType(existing, trigger) &&
             existing->getName() == trigger->getName());
        if (sameIdentity) {
            vstd::logger::debug("Ignoring duplicate trigger registration:", trigger->getTypeId(), trigger->getObject(),
                                trigger->getEvent());
            return;
        }
    }
    triggers.insert(std::make_pair(key, trigger));
}

std::set<std::shared_ptr<CTrigger>> CEventHandler::getTriggers() {
    std::set<std::shared_ptr<CTrigger>> triggers;
    for (auto trigger : this->triggers | std::views::values) {
        triggers.insert(trigger);
    }
    return triggers;
}

CGameEvent::CGameEvent(std::string type) : type(type) {}

std::string CGameEvent::getType() const { return type; }

std::shared_ptr<CGameObject> CGameEventCaused::getCause() const { return cause; }

CGameEventCaused::CGameEventCaused(std::string type, std::shared_ptr<CGameObject> cause)
    : CGameEvent(type), cause(cause) {}

CGameEvent::CGameEvent() {}

CGameEventCaused::CGameEventCaused() {}
