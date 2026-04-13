/*
 * MIT License
 *
 * Copyright (c) 2021 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#pragma once

#include <list>
#include <set>
#include <random>
#include <chrono>
#include <mutex>
#include <condition_variable>
#include <boost/pool/pool_alloc.hpp>
#include <boost/any.hpp>
#include <queue>
#include "vtraits.h"
#include "vhash.h"
#include "vcast.h"

namespace vstd {
    template<typename Container>
    auto any(Container &container) {
        return *std::find_if(container.begin(), container.end(), [](auto it) { return true; });
    }

    template<typename Container, typename Value>
    bool ctn(Container &container, Value value) {
        return container.find(value) != container.end();
    }

    template<typename Container=std::string, typename Value>
    bool ctn(std::string &container, Value value) {
        return container.find(value) != std::string::npos;
    }

    template<typename Container, typename Value, typename Comparator>
    bool ctn(Container &container, Value value, Comparator cmp) {
        for (auto x: container) {
            if (cmp(value, x)) {
                return true;
            }
        }
        return false;
    }

    template<typename Container, typename Predicate>
    bool ctn_pred(Container &container, Predicate pred) {
        return std::find_if(container.begin(), container.end(), pred) != container.end();
    }

    template<typename Container, typename Predicate>
    auto find_if(Container &container, Predicate predicate) {
        return *std::find_if(container.begin(), container.end(), predicate);
    }

    template<typename Container, typename Predicate, typename Callback>
    auto execute_if(Container &container, Predicate predicate, Callback callback) {
        if (std::find_if(container.begin(), container.end(), predicate) != container.end()) {
            callback(*std::find_if(container.begin(), container.end(), predicate));
        }
    }


    template<typename Container, typename Value, typename Comparator>
    void erase(Container &container, Value value, Comparator cmp) {
        for (auto it = container.begin(); it != container.end(); it++) {
            if (cmp(value, *it)) {
                container.erase(it);
                break;
            }
        }
    }

    template<typename Container, typename Predicate>
    void erase_if(Container &container, Predicate predicate) {
        for (auto it = container.begin(); it != container.end(); it++) {
            if (predicate(*it)) {
                container.erase(it);
                break;
            }
        }
    }

    template<typename Container>
    auto get(Container &container, int index) {
        return *std::next(container.begin(), index);
    }


    template<typename T, typename U>
    bool castable(std::shared_ptr<U> ptr) {
        return std::dynamic_pointer_cast<T>(ptr).operator bool();
    }

    template<typename A, typename B>
    auto type_pair() {
        return std::make_pair(boost::typeindex::type_id<A>(), boost::typeindex::type_id<B>());
    }

    template<typename F, typename... Args>
    std::function<typename function_traits<F>::return_type()> bind(F f, Args... args) {
        return std::bind(f, args...);
    }

    template<typename F, typename... Args>
    std::function<typename function_traits<F>::return_type()> bind(F f) {
        return f;
    }

    template<typename Range, typename Value=typename range_traits<Range>::value_type>
    std::set<Value> collect(Range r) {
        return cast<std::set<Value>>(r);
    }

    template<typename T>
    typename T::value_type pop(T &t) {
        auto x = t.front();
        t.pop();
        return x;
    }

    template<typename T>
    typename T::value_type pop_p(T &t) {
        auto x = t.top();
        t.pop();
        return x;
    }

    template<typename T>
    class list : public std::list<T> {
    public:
        template<typename U>
        void insert(U u) {
            this->push_back(u);
        }
    };

    template<typename F,
            typename ret=typename vstd::function_traits<F>::return_type,
            typename arg=typename vstd::function_traits<F>::template arg<0>::type>
    std::function<ret(arg)> make_function(F f,
                                          typename vstd::disable_if<std::is_void<arg>::value>::type * = 0) {
        return std::function<ret(arg)>(f);
    }

    template<typename F,
            typename ret=typename vstd::function_traits<F>::return_type,
            typename arg=typename vstd::function_traits<F>::template arg<0>::type>
    std::function<ret()> make_function(F f,
                                       typename vstd::enable_if<std::is_void<arg>::value>::type * = 0) {
        return std::function<ret()>(f);
    }

//TODO: use somewhere std::priority_queue<T,std::vector<T>,std::function<bool ( T,T ) >>
    template<typename T, typename Queue=std::queue<T>>
    class blocking_queue {
    private:
        std::recursive_mutex d_mutex;
        std::condition_variable_any d_condition;
        Queue d_queue;
    public:
        typedef T value_type;

        void push(T value) {
            std::unique_lock<std::recursive_mutex> lock(d_mutex);
            d_queue.push(value);
            d_condition.notify_one();
        }

        void pop(std::function<void(T)> callback) {
            T value;
            {
                std::unique_lock<std::recursive_mutex> lock(d_mutex);
                d_condition.wait(lock, [this]() {
                    return !d_queue.empty();
                });
                value = vstd::pop(d_queue);
            }
            callback(value);
        }
    };

    template<typename T=void>
    std::mt19937_64 &rng() {
        static std::mt19937_64 rng((unsigned long) std::time(nullptr));
        return rng;
    }

    template<typename T=void>
    std::uniform_real_distribution<double> &unif() {
        static std::uniform_real_distribution<double> unif(-0.5, 0.5);
        return unif;
    }

    template<typename T=void>
    double rand() {
        return unif()(rng());
    };

    template<typename T, typename U>
    int rand(T min, U max) {
        return round((unif()(rng()) + 0.5) * (max - min)) + min;
    };

    template<typename T>
    int rand(T max) {
        return rand(0, max);
    };

    template<typename Ctn>
    auto random_element(Ctn ctn) {
        auto iterator = ctn.begin();
        std::advance(iterator, vstd::rand(boost::size(ctn) - 1));
        return *iterator;
    };

    template<typename Ctn>
    auto random_components(int value, Ctn possibleComponents) {
        std::list<int> returnValue;
        while (value > 0) {
            std::set<int> possible_values;
            for (const auto &it: possibleComponents) {
                if (it <= value) {
                    possible_values.insert(it);
                }
            }
            if (possible_values.empty()) {
                break;
            }
            int pow = vstd::random_element(possible_values);
            returnValue.push_back(pow);
            value -= pow;
        }
        return returnValue;
    };

    template<typename T>
    static T *allocate(size_t size) {
        static boost::pool_allocator<T> _pool;
        return _pool.allocate(size);
    }

    template<typename T>
    static void deallocate(T *t, size_t size) {
        static boost::pool_allocator<T> _pool;
        _pool.deallocate(t, size);
    }

    template<typename T>
    typename T::value_type *as_array(T vec) {
        auto ret = vstd::allocate<typename T::value_type>(vec.size());
        std::copy(std::begin(vec), std::end(vec), ret);
        return ret;
    }

//TODO: handle return types
    template<typename T, typename C>
    static void if_not_null(T object, C callback) {
        if (object) {
            callback(object);
        }
    }

    template<typename T>
    static double percent(T object, double percent) {
        return object * (percent / 100.0);
    }

    template<typename R, typename T, typename F>
    R with(T t, F f, typename vstd::enable_if<std::is_void<R>::value>::type * = 0) {
        if (t) {
            f(t);
        }
    };

    template<typename R, typename T, typename F>
    R with(T t, F f, typename vstd::disable_if<std::is_void<R>::value>::type * = 0) {
        if (t) {
            return f(t);
        }
        return R();
    }

    template<typename A>
    bool all_equals(A) {
        return true;
    }

    template<typename A, typename B, typename...Args>
    bool all_equals(A a, B b, Args... args) {
        return a == b && all_equals(a, args...) && all_equals(b, args...);
    }

    template<typename T, typename ...Args>
    std::set<T> set(T arg, Args... args) {
        std::set<T> ret = vstd::set(args...);
        ret.insert(arg);
        return ret;
    }

    template<typename T>
    std::set<T> set(T arg) {
        std::set<T> ret;
        ret.insert(arg);
        return ret;
    }

    template<typename T, typename ...Args>
    std::list<T> as_list(T arg, Args... args) {
        std::list<T> ret = vstd::as_list(args...);
        ret.push_back(arg);
        return ret;
    }

    template<typename T>
    std::list<T> as_list(T arg) {
        std::list<T> ret;
        ret.push_back(arg);
        return ret;
    }

    template<typename T, typename U, typename V=typename T::key_type>
    auto set_difference(T &first, U &last) {
        std::set<V> to_add;
        std::set<V> to_remove;

        for (auto elem: last) {
            if (!vstd::ctn(first, elem)) {
                to_add.insert(elem);
            }
        }
        for (auto elem: first) {
            if (!vstd::ctn(last, elem)) {
                to_remove.insert(elem);
            }
        }

        return std::make_pair(to_add, to_remove);
    }

    template<typename T=void>
    auto square_ctn(auto w, auto h, auto x, auto y) {
        return x < w && y < h && !(x < 0) && !(y < 0);
    }
}
