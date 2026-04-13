/*
 * MIT License
 *
 * Copyright (c) 2019 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#pragma once

#include "vdefines.h"
#include "vtraits.h"
#include "vutil.h"
#include "vthreadpool.h"

namespace vstd {
    extern std::function<void(std::function<void()>)> get_call_later_handler();

    extern std::function<void(std::function<void()>)> get_call_async_handler();

    extern std::function<void(std::function<void()>)> get_call_now_handler();

    extern std::function<void(std::function<void()>)> get_call_later_block_handler();

    extern std::function<void(std::function<bool()>)> get_wait_until_handler();

    extern std::function<void(std::function<bool()>, std::function<void()>)> get_call_when_handler();

    extern std::function<void(int, std::function<void()>)> get_call_delayed_async_handler();

    extern std::function<void(int, std::function<void()>)> get_call_delayed_later_handler();

    template<typename Function, typename... Arguments>
    void call_later(Function target, Arguments... args) {
        get_call_later_handler()(vstd::bind(target, args...));
    }

    template<typename Function, typename... Arguments>
    void call_async(Function target, Arguments... args) {
        get_call_async_handler()(vstd::bind(target, args...));
    }

    template<typename Function, typename... Arguments>
    void call_now(Function target, Arguments... args) {
        get_call_now_handler()(vstd::bind(target, args...));
    }

    template<typename Function, typename... Arguments>
    void call_later_block(Function target, Arguments... args) {
        get_call_later_block_handler()(vstd::bind(target, args...));
    }


    template<typename Predicate>
    void wait_until(Predicate pred) {
        get_wait_until_handler()(pred);
    }

    template<typename Predicate, typename Function, typename... Arguments>
    void call_when(Predicate pred, Function func, Arguments... params) {
        get_call_when_handler()(pred,vstd::bind(func, params...));
    }

    template<typename Function, typename... Arguments>
    void call_delayed_async(int millis, Function target, Arguments... args) {
        get_call_delayed_async_handler()(millis, vstd::bind(target, args...));
    }

    template<typename Function, typename... Arguments>
    void call_delayed_later(int millis, Function target, Arguments... args) {
        get_call_delayed_later_handler()(millis, vstd::bind(target, args...));
    }
}
