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

namespace vstd {
    template<typename key, typename val, val(*get_next)(), int(*get_ttl)()>
    class cache {
        std::unordered_map<key, std::pair<val, int>> _values;
    public:
        val get(key k, int time) {
            auto it = _values.find(k);
            if (it == _values.end()) {
                val ret = get_next();
                _values.insert(std::make_pair(k, std::make_pair(ret, time + get_ttl())));
                return ret;
            }
            if ((*it).second.second < time) {
                _values.erase(it);
                return get(k, time);
            }
            return (*it).second.first;
        }
    };

    template<typename key, typename val, int(*get_ttl)()>
    class cache2 {
        std::unordered_map<key, std::pair<val, int>> _values;
    public:
        val get(key k, int time, std::function<val()> cb) {
            auto it = _values.find(k);
            if (it == _values.end()) {
                val ret = cb();
                _values.insert(std::make_pair(k, std::make_pair(ret, time + get_ttl())));
                return ret;
            }
            if ((*it).second.second < time) {
                _values.erase(it);
                return get(k, time, cb);
            }
            return (*it).second.first;
        }
    };
}