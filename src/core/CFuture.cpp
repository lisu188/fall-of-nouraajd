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
#include "core/CAsync.h"

namespace game_async {
bool runFrame(vstd::event_loop<> &loop, FramePumpBudget budget) {
    const auto started = std::chrono::steady_clock::now();
    for (std::size_t pass = 0; pass < budget.maxReadyPasses; ++pass) {
        if (loop.quitRequested()) {
            return false;
        }
        if (budget.maxReadyTime && std::chrono::steady_clock::now() - started >= *budget.maxReadyTime) {
            break;
        }
        if (loop.runReady() == 0) {
            break;
        }
    }
    return !loop.quitRequested() && loop.runFrame();
}

std::shared_ptr<vstd::thread_pool<16>> workerPool() {
    static auto pool = std::make_shared<vstd::thread_pool<16>>()->start();
    return pool;
}

vstd::task<void> dispatch(std::move_only_function<void()> callback) {
    co_await vstd::post(vstd::event_loop<>::instance());
    callback();
}
} // namespace game_async

namespace vstd {
std::function<void(std::function<void()>)> get_call_later_handler() {
    return [](std::function<void()> f) { vstd::event_loop<>::instance()->invoke(f); };
}

std::function<void(std::function<void()>)> get_call_async_handler() {
    return [](std::function<void()> f) { game_async::workerPool()->execute(f); };
}

std::function<void(std::function<void()>)> get_call_now_handler() {
    return [](std::function<void()> f) { f(); };
}

std::function<void(std::function<void()>)> get_call_later_block_handler() {
    return [](std::function<void()> f) { vstd::event_loop<>::instance()->await(f); };
}

std::function<void(std::function<bool()>)> get_wait_until_handler() {
    return [](std::function<bool()> pred) {
        vstd::event_loop<>::instance()->await([pred]() {
            while (!pred()) {
                if (!game_async::runFrame(*vstd::event_loop<>::instance())) {
                    break;
                }
            }
        });
    };
}

std::function<void(std::function<bool()>, std::function<void()>)> get_call_when_handler() {
    return [](std::function<bool()> pred, std::function<void()> func) {
        vstd::event_loop<>::instance()->invoke_when(pred, func);
    };
}

std::function<void(int, std::function<void()>)> get_call_delayed_later_handler() {
    return [](int t, std::function<void()> f) { vstd::event_loop<>::instance()->delay(t, f); };
}

std::function<void(int, std::function<void()>)> get_call_delayed_async_handler() {
    return [](int t, std::function<void()> f) {
        vstd::event_loop<>::instance()->delay(t, [f]() { game_async::workerPool()->execute(f); });
    };
}
} // namespace vstd
