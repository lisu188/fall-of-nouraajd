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

#include <boost/python.hpp>
#include "vcast.h"

namespace vstd {
    namespace detail {
        template<typename Ret, typename... Args>
        struct builder {
            static void build(PyObject *obj_ptr, boost::python::converter::rvalue_from_python_stage1_data *data) {
                help(obj_ptr, data);
            }

            template<typename R=Ret>
            static void help(PyObject *obj_ptr,
                             boost::python::converter::rvalue_from_python_stage1_data *data,
                             typename vstd::disable_if<vstd::is_shared_ptr<R>::value>::type * = 0) {
                void *storage = ((boost::python::converter::rvalue_from_python_storage
                        <std::function<R(Args...) >> *) data)->storage.bytes;
                boost::python::object func =
                        boost::python::object(boost::python::handle<>(
                                boost::python::borrowed(
                                        boost::python::incref(obj_ptr))));
                new(storage) std::function<R(Args...)>([func](Args... args) {
                    return boost::python::extract<R>(
                            boost::python::incref(func(args...).ptr()));
                });
                data->convertible = storage;
            }

            template<typename R=Ret>
            static void help(PyObject *obj_ptr,
                             boost::python::converter::rvalue_from_python_stage1_data *data,
                             typename vstd::enable_if<vstd::is_shared_ptr<R>::value>::type * = 0) {
                typedef typename R::element_type *ptr_type;
                void *storage = ((boost::python::converter::rvalue_from_python_storage
                        <std::function<R(Args...) >> *) data)->storage.bytes;
                boost::python::object func = boost::python::object(
                        boost::python::handle<>(boost::python::borrowed(
                                boost::python::incref(obj_ptr))));
                new(storage) std::function<R(Args...)>([func](Args... args) {
                    return R(vstd::functional::call(
                            boost::python::extract<ptr_type>(
                                    boost::python::incref(func(args...).ptr()))));
                });
                data->convertible = storage;
            }
        };

        template<typename... Args>
        struct builder<void, Args...> {
            static void build(PyObject *obj_ptr,
                              boost::python::converter::rvalue_from_python_stage1_data *data) {
                void *storage = ((boost::python::converter::rvalue_from_python_storage
                        <std::function<void(Args...) >> *) data)->storage.bytes;
                boost::python::object func = boost::python::object(
                        boost::python::handle<>(
                                boost::python::borrowed(
                                        boost::python::incref(obj_ptr))));
                new(storage) std::function<void(Args...)>([func](Args... args) {
                    func(args...);
                });
                data->convertible = storage;
            }
        };

        template<typename... Args>
        struct builder<bool, Args...> {
            static void build(PyObject *obj_ptr,
                              boost::python::converter::rvalue_from_python_stage1_data *data) {
                void *storage = ((boost::python::converter::rvalue_from_python_storage
                        <std::function<bool(Args...) >> *) data)->storage.bytes;
                boost::python::object func = boost::python::object(
                        boost::python::handle<>(
                                boost::python::borrowed(
                                        boost::python::incref(obj_ptr))));
                new(storage) std::function<bool(Args...)>([func](Args... args) {
                    return func(args...).ptr() == Py_True;
                });
                data->convertible = storage;
            }
        };

        template<class Source, class Target>
        struct implicit_cast {

            static void *convertible(PyObject *obj) {
                return boost::python::converter::implicit_rvalue_convertible_from_python(obj,
                                                                                         boost::python::converter::registered<Source>::converters)
                       ? obj : 0;
            }

            static void construct(PyObject *obj,
                                  boost::python::converter::rvalue_from_python_stage1_data *data) {
                void *storage = ((boost::python::converter::rvalue_from_python_storage<Target> *) data)->storage.bytes;

                boost::python::arg_from_python<Source> get_source(obj);
                bool convertible = get_source.convertible();
                BOOST_VERIFY (convertible);

                new(storage) Target(vstd::cast<Target>(get_source()));

                data->convertible = storage;
            }
        };
    }

    namespace detail {
        template<typename Ret, typename... Args>
        struct function_converter {
            function_converter() {
                boost::python::converter::registry::push_back(
                        [](PyObject *obj_ptr) -> void * {
                            if (PyCallable_Check(obj_ptr)) { return obj_ptr; }
                            return nullptr;
                        },
                        detail::builder<Ret, Args...>::build,
                        boost::python::type_id<std::function<Ret(Args...) >>());
            }
        };

        template<typename T>
        struct register_pointer {
            register_pointer() {
                boost::python::register_ptr_to_python<std::shared_ptr<T> >();
            }
        };

    }

    template<typename Ret, typename... Args>
    struct function_converter {
        function_converter() {
            static detail::function_converter<Ret, Args...> _dummy;
        }
    };

    template<typename T>
    void register_pointer() {
        static detail::register_pointer<T> _dummy;
    }

    namespace detail {

        template<class Source, class Target>
        struct implicitly_convertible_cast {
            implicitly_convertible_cast(boost::type<Source> * = 0, boost::type<Target> * = 0) {
                boost::python::converter::registry::push_back(
                        &detail::implicit_cast<Source, Target>::convertible,
                        &detail::implicit_cast<Source, Target>::construct,
                        boost::python::type_id<Target>(),
                        &boost::python::converter::expected_from_python_type_direct<Source>::get_pytype);
            }
        };
    }

    template<class Source, class Target>
    void implicitly_convertible_cast() {
        static detail::implicitly_convertible_cast<Source, Target> _dummy;
    }
}