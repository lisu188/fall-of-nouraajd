// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#include <chrono>
#include <coroutine>
#include <exception>
#include <expected>
#include <future>
#include <memory>
#include <type_traits>
#include <utility>

#include "vmove_only_function.h"
#include "vtask.h"
#include "vthreadpool.h"

#if __cplusplus <= 202302L
#error "The Android game requires C++26 without a language-standard fallback."
#endif

template <typename... Types> using SelectedType = Types...[1];
static_assert(std::is_same_v<SelectedType<int, const long &>, const long &>);
static_assert(!std::is_copy_constructible_v<vstd::move_only_function<int()>>);
static_assert(std::is_nothrow_move_constructible_v<vstd::move_only_function<int()>>);

struct ProbeTask {
    struct promise_type {
        ProbeTask get_return_object() { return {}; }
        std::suspend_never initial_suspend() noexcept { return {}; }
        std::suspend_never final_suspend() noexcept { return {}; }
        void return_void() noexcept {}
        void unhandled_exception() { std::terminate(); }
    };
    ProbeTask() = default;
    ProbeTask(const ProbeTask &) = delete("The coroutine probe has one owner");
};

ProbeTask runCallback(vstd::move_only_function<void()> callback) {
    callback();
    co_return;
}

int main() {
    std::expected<int, int> result = 0;
    vstd::move_only_function<int()> callback = [value = std::make_unique<int>(7)] { return *value; };
    vstd::move_only_function<int()> moved;
    moved = std::move(callback);
    if (callback || !moved || moved() != 7) {
        return 1;
    }
    moved = nullptr;
    if (moved) {
        return 2;
    }
    runCallback([value = std::make_unique<int>(11), &result] { result = *value; });
    if (result.value() != 11) {
        return 3;
    }
    vstd::scheduler scheduler;
    if (!scheduler.dispatch([value = std::make_unique<int>(17), &result] { result = *value; }) || result != 17) {
        return 4;
    }
    std::promise<int> completed;
    auto future = completed.get_future();
    auto pool = std::make_shared<vstd::thread_pool<1>>()->start();
    if (!pool->submit([value = std::make_unique<int>(23), completion = std::move(completed)]() mutable {
            completion.set_value(*value);
        })) {
        return 5;
    }
    if (future.wait_for(std::chrono::seconds(5)) != std::future_status::ready) {
        return 6;
    }
    const auto value = future.get();
    pool->stop();
    return value == 23 ? 0 : 7;
}
