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
#include "vfunctional.h"

namespace vstd {
    template<int a, int x>
    struct power {
        enum {
            value = a * power<a, x - 1>::value
        };
    };

    template<int a>
    struct power<a, 0> {
        enum {
            value = 1
        };
    };

    template<typename T>
    struct hasher {
        template<typename U=T>
        static std::size_t hash(U u,
                                typename vstd::disable_if<vstd::is_pair<U>::value>::type * = 0,
                                typename vstd::disable_if<vstd::is_enum<U>::value>::type * = 0) {
            return std::hash<U>()(u);
        }

        template<typename U=T>
        static std::size_t hash(U u,
                                typename vstd::disable_if<vstd::is_pair<U>::value>::type * = 0,
                                typename vstd::enable_if<vstd::is_enum<U>::value>::type * = 0) {
            return hasher<int>::hash(static_cast<int> ( u ));
        }
    };

    template<typename T>
    std::size_t hash_combine(T t) {
        return hasher<T>::hash(t);
    }

    template<typename F, typename G, typename ...T>
    std::size_t hash_combine(F f, G g, T... args) {
        return power<31, sizeof... (args) + 1>::value *
               hash_combine(f) +
               hash_combine(g, args...);
    }
}

namespace std {
    template<>
    struct hash<std::pair<int, int>> {
        std::size_t operator()(const std::pair<int, int> &pair) const {
            return vstd::hash_combine(pair.first, pair.second);
        }
    };

    template<>
    struct hash<std::pair<std::string, int>> {
        std::size_t operator()(const std::pair<std::string, int> &pair) const {
            return vstd::hash_combine(pair.first, pair.second);
        }
    };

    template<>
    struct hash<std::pair<std::string, std::string>> {
        std::size_t operator()(const std::pair<std::string, std::string> &pair) const {
            return vstd::hash_combine(pair.first, pair.second);
        }
    };

    template<>
    struct hash<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>> {
        std::size_t operator()(
                const std::pair<boost::typeindex::type_index, boost::typeindex::type_index> &pair) const {
            return vstd::hash_combine(pair.first, pair.second);
        }
    };

    template<>
    struct hash<boost::typeindex::type_index> {
        std::size_t operator()(const boost::typeindex::type_index &ind) const {
            return ind.hash_code();
        }
    };
}