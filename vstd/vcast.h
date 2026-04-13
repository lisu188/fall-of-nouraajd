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

namespace vstd {
    template<typename T, typename U>
    T cast(U ptr,
           typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type * = 0,
           typename vstd::disable_if<vstd::is_shared_ptr<U>::value>::type * = 0,
           typename vstd::disable_if<vstd::is_container<T>::value>::type * = 0,
           typename vstd::disable_if<vstd::is_range<U>::value>::type * = 0,
           typename vstd::disable_if<vstd::is_pair<T>::value>::type * = 0,
           typename vstd::disable_if<vstd::is_pair<U>::value>::type * = 0) {
        return ptr;
    }

    template<typename T, typename U>
    std::shared_ptr<T> cast(U ptr,
                            typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type * = 0,
                            typename vstd::enable_if<vstd::is_shared_ptr<U>::value>::type * = 0) {
        return std::dynamic_pointer_cast<T>(ptr);
    }

    template<typename T, typename U>
    T cast(U ptr,
           typename vstd::enable_if<vstd::is_shared_ptr<T>::value>::type * = 0,
           typename vstd::enable_if<vstd::is_shared_ptr<U>::value>::type * = 0) {
        return cast<typename T::element_type>(ptr);
    }

    template<typename T, typename U>
    T cast(U ptr,
           typename std::enable_if<vstd::is_pair<T>::value>::type * = 0,
           typename std::enable_if<vstd::is_pair<U>::value>::type * = 0) {
        return std::make_pair(cast<typename T::first_type>(ptr.first), cast<typename T::second_type>(ptr.second));
    }

    template<typename T, typename U>
    T cast(U c,
           typename std::enable_if<vstd::is_container<T>::value>::type * = 0,
           typename std::enable_if<vstd::is_range<U>::value>::type * = 0) {
        T t;
        for (auto x:c) {
            t.insert(cast<typename T::value_type>(x));
        }
        return t;
    }
}
