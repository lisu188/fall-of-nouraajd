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
#include "CTrigger.h"
#include "core/CPythonOverrides.h"
#include "handler/CEventHandler.h"
#include "core/CAsync.h"
#include "core/CGame.h"
#include "core/CGameContext.h"

CTrigger::CTrigger() {}

void CTrigger::trigger(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "trigger"); !override.is_none()) {
        PY_SAFE(override(object, event); return;)
    }
}

vstd::task<void> CTrigger::triggerAsync(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) {
    return [](std::shared_ptr<CTrigger> self, std::shared_ptr<CGameObject> object,
              std::shared_ptr<CGameEvent> event) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        self->trigger(std::move(object), std::move(event));
    }(this->ptr<CTrigger>(), std::move(object), std::move(event));
}

std::string CTrigger::getObject() { return object; }

void CTrigger::setObject(std::string object) { CTrigger::object = object; }

std::string CTrigger::getEvent() { return event; }

void CTrigger::setEvent(std::string event) { CTrigger::event = event; }

void CCustomTrigger::trigger(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) {
    if (_triggerAsync) {
        auto task = triggerAsync(object, std::move(event));
        if (auto game = object ? object->getGame() : nullptr) {
            game_async::wait(game->getContext()->spawnTask(std::move(task)));
        } else {
            game_async::run(std::move(task));
        }
    } else {
        _trigger(std::move(object), std::move(event));
    }
}

vstd::task<void> CCustomTrigger::triggerAsync(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) {
    return [](decltype(_trigger) callback, decltype(_triggerAsync) asyncCallback, std::shared_ptr<CGameObject> object,
              std::shared_ptr<CGameEvent> event) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        if (asyncCallback) {
            co_await asyncCallback(std::move(object), std::move(event));
        } else {
            callback(std::move(object), std::move(event));
        }
    }(_trigger, _triggerAsync, std::move(object), std::move(event));
}
