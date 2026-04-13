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

#include <mutex>

#include "vfuture.h"

namespace vstd {
    template<typename T>
    class chain {
        std::shared_ptr<vstd::future<void, void>> _future = vstd::async([]() {});
        std::recursive_mutex _lock;
        std::function<void(T)> _cb;
    public:
        chain(std::function<void(T)> cb) : _cb(cb) {}

        void invoke_async(T t) {
            std::unique_lock<std::recursive_mutex> lock(_lock);
            _future = _future->thenAsync(vstd::bind(_cb, t));
        }

        void invoke_later(T t) {
            std::unique_lock<std::recursive_mutex> lock(_lock);
            _future = _future->thenLater(vstd::bind(_cb, t));
        }

        std::shared_ptr<vstd::future<void, void>> terminate() {
            std::unique_lock<std::recursive_mutex> lock(_lock);
            return _future;
        };
    };
}