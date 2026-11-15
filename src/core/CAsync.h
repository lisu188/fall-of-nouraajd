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

#include "core/CGlobal.h"
#include <exception>
#include <string>

namespace game_async {
// LLVM186728 hypothesis: keep a named catch outside coroutine frames; not a proved cause of our crash.
// Call only from an active std::exception handler.
#if defined(_MSC_VER)
__declspec(noinline)
#elif defined(__GNUC__)
__attribute__((noinline))
#endif
inline std::string
activeExceptionMessage() {
    try {
        throw;
    } catch (const std::exception &error) {
        return error.what();
    }
}

enum class WaitMode { PostedWork, Frames };
struct FramePumpBudget {
    std::size_t maxReadyPasses = 1024;
    std::optional<std::chrono::steady_clock::duration> maxReadyTime = std::chrono::milliseconds(4);
};

bool runFrame(vstd::event_loop<> &loop, FramePumpBudget budget = {});

std::shared_ptr<vstd::thread_pool<16>> workerPool();

vstd::task<void> dispatch(vstd::move_only_function<void()> callback);

inline void waitForProgress(bool readyWork = false) {
    const auto yield = [readyWork] {
        if (readyWork) {
            std::this_thread::yield();
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    };
    if (Py_IsInitialized() && PyGILState_Check()) {
        pybind11::gil_scoped_release release;
        yield();
    } else {
        yield();
    }
}

// Only synchronous entry adapters pump the loop. Native coroutine callers await the task directly.
template <typename T> T wait(const vstd::task_handle<T> &handle, WaitMode mode = WaitMode::Frames) {
    auto loop = vstd::event_loop<>::instance();
    if (mode == WaitMode::Frames && loop->quitRequested()) {
        handle.requestStop();
    }
    while (!handle.finished()) {
        if (!loop->isMainThread()) {
            waitForProgress();
        } else if (mode == WaitMode::Frames && !loop->quitRequested()) {
            if (!runFrame(*loop)) {
                handle.requestStop();
            }
            if (!handle.finished()) {
                waitForProgress(loop->hasReadyWork());
            }
        } else {
            loop->runReady();
            if (!handle.finished()) {
                waitForProgress(loop->hasReadyWork());
            }
        }
    }
    return handle.get();
}

template <typename T> T run(vstd::task<T> task, WaitMode mode = WaitMode::Frames) {
    vstd::task_group group;
    return wait(group.spawn(std::move(task), vstd::loopScheduler(vstd::event_loop<>::instance())), mode);
}
} // namespace game_async
