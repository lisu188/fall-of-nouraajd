/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include "core/CAsync.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "gui/CGui.h"
#include "gui/object/CGameGraphicsObject.h"

namespace gui_async {
inline std::shared_ptr<CGame> gameFor(const std::shared_ptr<CGameGraphicsObject> &owner) {
    auto gui = owner->getGui();
    return gui && gui->getGame() ? gui->getGame() : owner->getGame();
}

template <typename T>
vstd::task_handle<T> spawn(const std::shared_ptr<CGameGraphicsObject> &owner, vstd::task<T> task) {
    if (auto game = gameFor(owner)) {
        return game->getContext()->spawnTask(std::move(task));
    }
    return owner->getGuiTaskGroup().spawn(std::move(task), vstd::loopScheduler(vstd::event_loop<>::instance()));
}

template <typename T> T run(const std::shared_ptr<CGameGraphicsObject> &owner, vstd::task<T> task) {
    try {
        return game_async::wait(spawn(owner, std::move(task)));
    } catch (const vstd::task_cancelled &) {
        if constexpr (!std::is_void_v<T>) {
            return T{};
        }
    }
}

template <typename Predicate, typename Reader>
vstd::task<std::invoke_result_t<Reader &>> until(Predicate ready, Reader read) {
    auto loop = vstd::event_loop<>::instance();
    if (!loop->isMainThread()) {
        co_await vstd::post(loop);
    }
    if (!std::invoke(ready)) {
        co_await vstd::until(loop, std::move(ready));
    }
    if constexpr (std::is_void_v<std::invoke_result_t<Reader &>>) {
        std::invoke(read);
    } else {
        co_return std::invoke(read);
    }
}

template <typename T, typename Predicate, typename Callback>
vstd::task<void> whenReady(std::weak_ptr<T> owner, Predicate ready, Callback callback) {
    co_await vstd::until(vstd::event_loop<>::instance(), [owner, ready = std::move(ready)]() mutable {
        auto self = owner.lock();
        if (!self) {
            return true;
        }
        auto game = gameFor(self);
        return (game && !game->getContext()->isActive()) || std::invoke(ready, self);
    });
    if (auto self = owner.lock()) {
        auto game = gameFor(self);
        if (!game || game->getContext()->isActive()) {
            std::invoke(callback, self);
        }
    }
}
} // namespace gui_async
