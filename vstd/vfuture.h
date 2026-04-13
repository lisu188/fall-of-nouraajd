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

#include <boost/range/adaptors.hpp>
#include <mutex>
#include <condition_variable>
#include "vutil.h"
#include "vthread.h"

namespace vstd {
    namespace detail {
        template<typename G,
                typename return_type=typename vstd::function_traits<G>::return_type,
                typename argument_type=typename vstd::function_traits<G>::first_arg>
        auto normalize(G f,
                       typename vstd::enable_if<std::is_void<return_type>::value>::type * = 0,
                       typename vstd::enable_if<std::is_void<argument_type>::value>::type * = 0) {
            return [f](void *) -> void * {
                f();
                return nullptr;
            };
        }

        template<typename G,
                typename return_type=typename vstd::function_traits<G>::return_type,
                typename argument_type=typename vstd::function_traits<G>::first_arg>
        auto normalize(G f,
                       typename vstd::disable_if<std::is_void<return_type>::value>::type * = 0,
                       typename vstd::enable_if<std::is_void<argument_type>::value>::type * = 0) {
            return [f](void *) {
                return f();
            };
        }

        template<typename G,
                typename return_type=typename vstd::function_traits<G>::return_type,
                typename argument_type=typename vstd::function_traits<G>::first_arg>
        auto normalize(G f,
                       typename vstd::enable_if<std::is_void<return_type>::value>::type * = 0,
                       typename vstd::disable_if<std::is_void<argument_type>::value>::type * = 0) {
            return [f](argument_type t) -> void * {
                f(t);
                return nullptr;
            };
        }

        template<typename G,
                typename return_type=typename vstd::function_traits<G>::return_type,
                typename argument_type=typename vstd::function_traits<G>::first_arg>
        auto normalize(G f,
                       typename vstd::disable_if<std::is_void<return_type>::value>::type * = 0,
                       typename vstd::disable_if<std::is_void<argument_type>::value>::type * = 0) {
            return f;
        }

        template<typename sig>
        struct normalized_function {
            typedef std::function<typename function_traits<decltype(normalize(std::declval<sig>()))>::return_type(
                    typename function_traits<decltype(normalize(std::declval<sig>()))>::first_arg)> type;
        };

        template<typename ret, typename arg>
        struct function_type {
            typedef std::function<ret(arg)> type;
        };

        template<typename ret>
        struct function_type<ret, void> {
            typedef std::function<ret()> type;
        };

        template<typename return_type,
                typename argument_type>
        class ccall : public std::enable_shared_from_this<ccall<return_type, argument_type>> {
            typedef typename function_type<return_type, argument_type>::type function_target;
            typedef typename normalized_function<function_target>::type normalized_target;
            typedef std::function<void(typename function_traits<normalized_target>::return_type)> on_result;

            volatile bool completed = false;
            std::recursive_mutex mutex;
            std::condition_variable_any _condition;
            return_type *result = _new<return_type>();
            argument_type *argument = _new<argument_type>();

            template<typename X>
            X *_new(typename vstd::disable_if<vstd::is_same<X, void>::value>::type * = 0) {
                return new X();
            }

            template<typename X>
            X *_new(typename vstd::enable_if<vstd::is_same<X, void>::value>::type * = 0) {
                return nullptr;
            }

            template<typename X>
            void _delete(typename vstd::disable_if<vstd::is_same<X, void>::value>::type * = 0) {
                delete result;
            }

            template<typename X>
            void _delete(typename vstd::enable_if<vstd::is_same<X, void>::value>::type * = 0) {

            }

        public:

            template<typename F, typename G>
            ccall(F func, G caller) :
                    _target(normalize(func)),
                    _caller(caller) {

            }

            ~ccall() {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                _delete<return_type>();
            }

            template<typename X=argument_type>
            argument_type getArgument(typename vstd::disable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                return *argument;
            }

            template<typename X=argument_type>
            void *getArgument(typename vstd::enable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                return nullptr;
            }

            template<typename X=argument_type>
            void setArgument(X x, typename vstd::disable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                *argument = x;
            }

            template<typename X=argument_type>
            void setArgument(void *, typename vstd::enable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                argument = nullptr;
            }

            template<typename X=return_type>
            void setResult(X t, typename vstd::disable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                *result = t;
                completed = true;
                if (_on_result) {
                    _on_result(t);
                }
                _condition.notify_all();
            }

            template<typename X=return_type>
            X getResult(typename vstd::disable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                _condition.wait(lock, [this]() { return completed; });
                return *result;
            }

            template<typename X=return_type>
            void setResult(typename vstd::enable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                completed = true;
                if (_on_result) {
                    _on_result(nullptr);
                }
                _condition.notify_all();
            }

            template<typename X=return_type>
            void *getResult(typename vstd::enable_if<vstd::is_same<X, void>::value>::type * = 0) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                _condition.wait(lock, [this]() { return completed; });
                return nullptr;
            }

            void call() {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                auto self = this->shared_from_this();
                vstd::functional::call(_caller, [self]() {
                    self->setResult(vstd::functional::call(self->_target, self->getArgument()));
                });
            }

            void onResult(on_result cb) {
                std::unique_lock<std::recursive_mutex> lock(mutex);
                if (completed) {
                    cb(getResult());
                } else {
                    _on_result = cb;
                }
            }

        private:

            normalized_target _target;

            on_result _on_result;

            std::function<void(std::function<void()>)> _caller;
        };
    }

    namespace detail {
        template<typename func>
        auto make_async(func f) {
            return std::make_shared<ccall<typename function_traits<func>::return_type,
                    typename function_traits<func>::first_arg>>(
                    f, call_async<std::function<void() >>);
        }

        template<typename func>
        auto make_later(func f) {
            return std::make_shared<ccall<typename function_traits<func>::return_type,
                    typename function_traits<func>::first_arg>>(
                    f, call_later<std::function<void() >>);
        }

        template<typename func>
        auto make_now(func f) {
            return std::make_shared<ccall<typename function_traits<func>::return_type,
                    typename function_traits<func>::first_arg>>(
                    f, call_now<std::function<void() >>);
        }
    }

    template<typename return_type,
            typename argument_type>
    class future : public std::enable_shared_from_this<future<return_type, argument_type>> {
    public:
        typedef typename detail::function_type<return_type, argument_type>::type function;

        explicit future(std::shared_ptr<detail::ccall<return_type, argument_type>> call, bool start = true) :
                _call(call) {
            if (start) {
                _call->call();
            }
        }

        auto get() {
            return _call->getResult();
        }

        template<typename G>
        auto thenLater(G g) {
            return chain_call(detail::make_later(g));
        }

        template<typename G>
        auto thenAsync(G g) {
            return chain_call(detail::make_async(g));
        }

    private:
        std::shared_ptr<detail::ccall<return_type, argument_type>> _call;

        template<typename _return_type, typename _first_arg>
        auto chain_call(std::shared_ptr<detail::ccall<_return_type, _first_arg>> _new_call) {
            auto _self = this->shared_from_this();
            _self->_call->onResult([_new_call](auto arg) {
                _new_call->setArgument(arg);
                _new_call->call();
            });
            return std::make_shared<future<_return_type, _first_arg>>(_new_call, false);
        }
    };

    namespace detail {
        template<typename return_type, typename first_arg>
        auto make_future(std::shared_ptr<detail::ccall<return_type, first_arg>> call) {
            return std::make_shared<vstd::future<return_type, first_arg>>(call);
        }
    }

    template<typename Func>
    auto later(Func f) {
        return detail::make_future(detail::make_later(vstd::make_function(f)));
    }

    template<typename Func>
    auto async(Func f) {
        return detail::make_future(detail::make_async(vstd::make_function(f)));
    }

    template<typename Func>
    auto now(Func f) {
        return detail::make_future(detail::make_now(vstd::make_function(f)));
    }

    template<typename F, typename Arg=typename vstd::function_traits<F>::template arg<0>::type>
    auto wrap_later(F f) {
        return [f](Arg a) {
            return later(vstd::bind(f, a));
        };
    }

    template<typename F, typename Arg=typename vstd::function_traits<F>::template arg<0>::type>
    auto wrap_async(F f) {
        return [f](Arg a) {
            return async(vstd::bind(f, a));
        };
    }

    template<typename Range>
    auto join(Range range) {
        return async([range]() {
            return collect(collect(range) |
                           boost::adaptors::transformed([](auto future) {
                               return future->get();
                           }));
        });
    }
}
