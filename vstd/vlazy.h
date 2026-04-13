/*
 * MIT License
 *
 * Copyright (c) 2025 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#pragma once

#include <memory>
#include <type_traits>
#include <utility>

namespace vstd {
    template<typename T, typename Owner = std::shared_ptr<T>>
    class lazy {
    public:
        std::shared_ptr<T> get() {
            if (ptr) {
                return ptr;
            }
            return ptr = std::make_shared<T>();
        }

        template<typename F>
        std::shared_ptr<T> get(F &&f) {
            if (ptr) {
                return ptr;
            }
            if constexpr (std::is_invocable_r_v<std::shared_ptr<T>, F>) {
                return ptr = std::forward<F>(f)();
            } else {
                return ptr = std::make_shared<T>(std::forward<F>(f));
            }
        }

        template<typename First, typename... Rest>
        std::shared_ptr<T> get(First &&first, Rest &&... rest) {
            if (ptr) {
                return ptr;
            }
            return ptr = std::make_shared<T>(
                std::forward<First>(first), std::forward<Rest>(rest)...);
        }

        void clear() {
            ptr = nullptr;
        }

    private :
        std::shared_ptr<T> ptr;
    };
}
