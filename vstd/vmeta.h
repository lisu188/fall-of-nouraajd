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
//TODO: line 36 optimize, do not use map
#pragma once

#include <boost/any.hpp>
#include <functional>
#include <unordered_map>
#include <memory>
#include "vany.h"
#include "vbind.h"

#define V_VOID boost::typeindex::type_id<void>()

#define V_STRING(X) #X

#define V_META(CLASS, SUPER, ...) \
private: \
friend class vstd::meta; \
std::unordered_map<std::string, std::shared_ptr<vstd::property>> _dynamic_props; \
virtual std::unordered_map<std::string, std::shared_ptr<vstd::property>> &dynamic_props(){return _dynamic_props;} \
std::unordered_map<std::string, std::shared_ptr<vstd::method>> _dynamic_methods; \
virtual std::unordered_map<std::string, std::shared_ptr<vstd::method>> &dynamic_methods(){return _dynamic_methods;} \
public: \
static std::shared_ptr<vstd::meta> static_meta(){ \
    static std::shared_ptr<vstd::meta> _static_meta=std::make_shared<vstd::meta>(V_STRING(CLASS),SUPER::static_meta(),__VA_ARGS__); \
    if(!vstd::ctn(*vstd::meta::index(),_static_meta->name())){vstd::meta::index()->insert(std::make_pair(_static_meta->name(),_static_meta));} \
    return _static_meta; \
} \
virtual std::shared_ptr<vstd::meta> meta() { \
    return static_meta(); \
} \
private: \

// get number of arguments with __NARG__
#define __NARG__(...)  __NARG_I_(__VA_ARGS__,__RSEQ_N())
#define __NARG_I_(...) __ARG_N(__VA_ARGS__)
#define __ARG_N(\
      _1, _2, _3, _4, _5, _6, _7, _8, _9, _10, \
     _11, _12, _13, _14, _15, _16, _17, _18, _19, _20, \
     _21, _22, _23, _24, _25, _26, _27, _28, _29, _30, \
     _31, _32, _33, _34, _35, _36, _37, _38, _39, _40, \
     _41, _42, _43, _44, _45, _46, _47, _48, _49, _50, \
     _51, _52, _53, _54, _55, _56, _57, _58, _59, _60, \
     _61, _62, _63, N, ...) N
#define __RSEQ_N() \
     63,62,61,60,                   \
     59,58,57,56,55,54,53,52,51,50, \
     49,48,47,46,45,44,43,42,41,40, \
     39,38,37,36,35,34,33,32,31,30, \
     29,28,27,26,25,24,23,22,21,20, \
     19,18,17,16,15,14,13,12,11,10, \
     9,8,7,6,5,4,3,2,1,0

// general definition for any function name
#define _VFUNC_(name, n) name##n
#define _VFUNC(name, n) _VFUNC_(name, n)
#define VFUNC(func, ...) _VFUNC(func, __NARG__(__VA_ARGS__)) (__VA_ARGS__)

// definition for FOO
#define V_METHOD(...) VFUNC(V_METHOD, __VA_ARGS__)

#define V_PROPERTY(CLASS, TYPE, NAME, GETTER, SETTER) std::make_shared<vstd::detail::property_impl<CLASS,TYPE>>\
                                                        (V_STRING(NAME),&CLASS::GETTER,&CLASS::SETTER),        \
                                                        V_METHOD(CLASS,GETTER,TYPE),V_METHOD(CLASS,SETTER,void,TYPE)

#define V_METHOD2(CLASS, NAME) std::make_shared<vstd::detail::method_impl<CLASS,void>>(V_STRING(NAME),&CLASS::NAME)
#define V_METHOD3(CLASS, NAME, RET_TYPE) std::make_shared<vstd::detail::method_impl<CLASS,RET_TYPE>>(V_STRING(NAME),&CLASS::NAME)
#define V_METHOD4(CLASS, NAME, RET_TYPE, ...) std::make_shared<vstd::detail::method_impl<CLASS,RET_TYPE,__VA_ARGS__>>(V_STRING(NAME),&CLASS::NAME)
#define V_METHOD5(CLASS, NAME, RET_TYPE, ...) std::make_shared<vstd::detail::method_impl<CLASS,RET_TYPE,__VA_ARGS__>>(V_STRING(NAME),&CLASS::NAME)
#define V_METHOD6(CLASS, NAME, RET_TYPE, ...) std::make_shared<vstd::detail::method_impl<CLASS,RET_TYPE,__VA_ARGS__>>(V_STRING(NAME),&CLASS::NAME)

namespace vstd {
    //TODO: allow method overrides, use composite key in _methods in meta
    class method {
    public:
        virtual std::string name() = 0;

        virtual boost::any invoke(std::vector<boost::any> args) = 0;

        virtual boost::typeindex::type_index object_type() = 0;

        virtual boost::typeindex::type_index return_type() = 0;

        virtual std::list<boost::typeindex::type_index> argument_types() = 0;
    };

    class property {
    public:
        virtual std::string name() = 0;

        virtual boost::any get(boost::any object) = 0;

        virtual void set(boost::any object, boost::any value) = 0;

        virtual boost::typeindex::type_index object_type() = 0;

        virtual boost::typeindex::type_index value_type() = 0;
    };

    namespace detail {
        template<typename ObjectType, typename ReturnType, typename ...ArgumentTypes>
        class method_impl : public method {
            std::string _name;
            std::function<ReturnType(ObjectType *, ArgumentTypes...)> _func;

        public:

            template<typename Method>
            method_impl(std::string name, Method method, bool external):
                    _name(name), _func(method) {

            }

            template<typename Method>
            method_impl(std::string name, Method method) :
                    _name(name), _func(std::mem_fn(method)) {

            }

            template<typename T=ReturnType>
            method_impl(std::string name,
                        typename vstd::disable_if<vstd::is_same<T, void>::value>::type * = 0) :
                    _name(name), _func([](ObjectType *, ArgumentTypes...) {
                return ReturnType();
            }) {
            }

            template<typename T=ReturnType>
            method_impl(std::string name,
                        typename vstd::enable_if<vstd::is_same<T, void>::value>::type * = 0) :
                    _name(name), _func([](ObjectType *, ArgumentTypes...) {

            }) {
            }

            //TODO: implement arguments and return type
            boost::any invoke(std::vector<boost::any> args) override {
                return _call(_bind<0>(_func, args));
            }

            template<typename F, typename T=ReturnType>
            auto
            _call(F function, typename vstd::enable_if<vstd::is_same<T, void>::value>::type * = 0) {
                function();
                return boost::any();
            }

            template<typename F, typename T=ReturnType>
            auto
            _call(F function, typename vstd::disable_if<vstd::is_same<T, void>::value>::type * = 0) {
                return function();
            }

            template<int argNo, typename F>
            auto _bind(F function, std::vector<boost::any> args,
                       typename vstd::disable_if<
                               argNo < vstd::tuple_size<ObjectType, ArgumentTypes...>::size - 1>::type * = 0) {
                return _bind<argNo>(function, args[argNo]);
            }

            template<int argNo, typename F>
            auto _bind(F function, std::vector<boost::any> args,
                       typename vstd::enable_if<
                               argNo < vstd::tuple_size<ObjectType, ArgumentTypes...>::size - 1>::type * = 0) {
                return _bind<argNo + 1>(_bind<argNo>(function, args[argNo]), args);
            }

            template<int argNo, typename F>
            auto _bind(F function, boost::any arg, typename vstd::disable_if<argNo == 0>::type * = 0) {
                return vstd::partial::bind(function,
                                           vstd::any_cast<typename vstd::tuple_element<argNo, ObjectType, ArgumentTypes...>::type>(
                                                   arg));
            }

            template<int argNo, typename F>
            auto _bind(F function, boost::any arg, typename vstd::enable_if<argNo == 0>::type * = 0) {
                return vstd::partial::bind(function, vstd::any_cast<std::shared_ptr<ObjectType >>(arg).get());
            }


            std::string name() override {
                return _name;
            }

            boost::typeindex::type_index object_type() override {
                return boost::typeindex::type_id<ObjectType>();
            }

            boost::typeindex::type_index return_type() override {
                return boost::typeindex::type_id<ReturnType>();
            }

            std::list<boost::typeindex::type_index> argument_types() override {
                return _argument_types();
            }

            std::list<boost::typeindex::type_index> _argument_types() {
                return std::list<boost::typeindex::type_index>();
            }

            template<typename Arg, typename... Args>
            std::list<boost::typeindex::type_index> argument_types(Arg arg, Args... props) {
                std::list<boost::typeindex::type_index> ret;
                ret.insert(boost::typeindex::type_id<Arg>());
                for (boost::typeindex::type_index ind:argument_types<Args...>()) {
                    ret.push_back(ind);
                }
                return ret;
            };
        };

        template<typename ObjectType, typename PropertyType>
        class property_impl : public property {
            std::string _name;
            std::function<PropertyType(ObjectType *)> _getter;
            std::function<void(ObjectType *, PropertyType)> _setter;

        public:
            template<typename Getter, typename Setter>
            property_impl(std::string name, Getter getter, Setter setter) :
                    _name(name), _getter(std::mem_fn(getter)), _setter(std::mem_fn(setter)) {

            }

            std::string name() override {
                return _name;
            }

            boost::any get(boost::any object) override {
                return _getter(vstd::any_cast<std::shared_ptr<ObjectType>>(object).get());
            }

            void set(boost::any object, boost::any value) override {
                _setter(vstd::any_cast<std::shared_ptr<ObjectType>>(object).get(),
                        vstd::any_cast<PropertyType>(value));
            }

            boost::typeindex::type_index object_type() override {
                return boost::typeindex::type_id<ObjectType>();
            }

            boost::typeindex::type_index value_type() override {
                return boost::typeindex::type_id<PropertyType>();
            }
        };

        template<typename ObjectType, typename PropertyType>
        class dynamic_property_impl : public property {
            std::string _name;
            PropertyType _value;
        public:
            dynamic_property_impl(std::string name) : _name(name) {

            }

            std::string name() override {
                return _name;
            }

            boost::any get(boost::any object) override {
                return boost::any(_value);
            }

            void set(boost::any object, boost::any value) override {
                _value = vstd::any_cast<PropertyType>(value);
            }

            boost::typeindex::type_index object_type() override {
                return boost::typeindex::type_id<ObjectType>();
            }

            boost::typeindex::type_index value_type() override {
                return boost::typeindex::type_id<PropertyType>();
            }
        };
    }

    class meta {
    public:
        class empty {
        public:
            static std::shared_ptr<vstd::meta> static_meta() {
                return nullptr;
            }
        };

        static std::unordered_map<std::string, std::shared_ptr<meta>> *index() {
            static std::unordered_map<std::string, std::shared_ptr<meta>> _index;
            return &_index;
        };
    private:
        std::string _name;
        std::unordered_map<std::string, std::shared_ptr<property>> _props;
        std::unordered_map<std::string, std::shared_ptr<method>> _methods;
        std::shared_ptr<meta> _super;


        void _add() {

        }

        template<typename... Args>
        void _add(std::shared_ptr<property> prop, Args... props) {
            _props[prop->name()] = prop;
            _add(props...);
        };

        template<typename... Args>
        void _add(std::shared_ptr<method> meth, Args... props) {
            _methods[meth->name()] = meth;
            _add(props...);
        };

        template<typename... Args>
        void _add(vstd::meta::empty val, Args... props) {
            _add(props...);
        };

        template<typename ObjectType, typename PropertyType>
        std::shared_ptr<property> _get_property_object(std::shared_ptr<ObjectType> ob, std::string name) {
            if (vstd::ctn(_props, name)) {
                return _props[name];
            } else if (vstd::ctn(ob->dynamic_props(), name)) {
                return ob->dynamic_props()[name];
            } else if (auto super_p = _super ? _super->_get_property_object<ObjectType, PropertyType>(ob, name)
                                             : nullptr) {
                return super_p;
            }
            ob->dynamic_props()[name] = std::make_shared<detail::dynamic_property_impl<ObjectType, PropertyType>>(
                    name);
            return _get_property_object<ObjectType, PropertyType>(ob, name);
        }

        template<typename ObjectType, typename ReturnType, typename ...ArgumentTypes>
        std::shared_ptr<method> _get_method_object(std::shared_ptr<ObjectType> ob, std::string name) {
            if (vstd::ctn(_methods, name)) {
                return _methods[name];
            } else if (vstd::ctn(ob->dynamic_methods(), name)) {
                return ob->dynamic_methods()[name];
            } else if (auto super_p = _super ? _super->_get_method_object<ObjectType,
                    ReturnType, ArgumentTypes...>(ob, name) : nullptr) {
                return super_p;
            }
            //TODO: handle differently
            return std::make_shared<vstd::detail::method_impl<ObjectType, ReturnType, ArgumentTypes...>>(name);
        }

        template<typename ObjectType, typename ReturnType, typename ...ArgumentTypes, typename Function>
        void _set_method_object(std::shared_ptr<ObjectType> ob, std::string name, Function function) {
            ob->dynamic_methods()[name] = std::make_shared<vstd::detail::method_impl<ObjectType, ReturnType, ArgumentTypes...>>(
                    name,
                    function,
                    true);
        }

        template<typename PropertyCallback>
        void _for_properties(PropertyCallback propertyCallback) {
            for (auto &[name, property]:_props) {
                if (propertyCallback(property)) {
                    return;
                }
            }
            if (_super) {
                _super->_for_properties(propertyCallback);
            }
        }

    public:
        template<typename... Args>
        meta(std::string name, std::shared_ptr<meta> super, Args... props) : _name(name), _super(super) {
            _add(props...);
        }

        std::shared_ptr<meta> super() {
            return _super;
        }

        std::string name() {
            return _name;
        }

        bool inherits(std::string clas) {
            return name() == clas || (_super && _super->inherits(clas));
        }

        template<typename ObjectType, typename PropertyType>
        void set_property(std::string prop, std::shared_ptr<ObjectType> t, PropertyType p) {
            _get_property_object<ObjectType, PropertyType>(t, prop)->set(t, p);
        }

        template<typename ReturnType, typename ObjectType, typename ...ArgumentTypes>
        void invoke_method(std::string name, std::shared_ptr<ObjectType> t, ArgumentTypes... args,
                           typename vstd::enable_if<std::is_same<ReturnType, void>::value>::type * = 0) {
            _get_method_object<ObjectType, ReturnType, ArgumentTypes...>(t, name)->invoke({t, args...});
        }

        template<typename ReturnType, typename ObjectType, typename ...ArgumentTypes>
        ReturnType invoke_method(std::string name, std::shared_ptr<ObjectType> t, ArgumentTypes... args,
                                 typename vstd::disable_if<std::is_same<ReturnType, void>::value>::type * = 0) {
            return vstd::any_cast<ReturnType>(
                    _get_method_object<ObjectType, ReturnType, ArgumentTypes...>(t, name)->invoke({t, args...}));
        }

        template<typename ObjectType, typename PropertyType>
        PropertyType get_property(std::string prop, std::shared_ptr<ObjectType> t,
                                  typename vstd::disable_if<std::is_same<PropertyType, boost::any>::value>::type * = 0) {
            return vstd::any_cast<PropertyType>(
                    _get_property_object<ObjectType, PropertyType>(t, prop)->get(t));
        }

        template<typename ObjectType, typename PropertyType>
        PropertyType get_property(std::string prop, std::shared_ptr<ObjectType> t,
                                  typename vstd::enable_if<std::is_same<PropertyType, boost::any>::value>::type * = 0) {
            return _get_property_object<ObjectType, PropertyType>(t, prop)->get(t);
        }

        template<typename ObjectType, typename ReturnType, typename ...ArgumentTypes, typename Function>
        void set_method(std::string method, std::shared_ptr<ObjectType> t, Function function) {
            _set_method_object<ObjectType, ReturnType, ArgumentTypes...>(t, method, function);
        }

        template<typename ObjectType>
        boost::typeindex::type_index get_property_type(std::shared_ptr<ObjectType> ob, std::string name) {
            if (vstd::ctn(_props, name)) {
                return _props[name]->value_type();
            } else if (vstd::ctn(ob->dynamic_props(), name)) {
                return ob->dynamic_props()[name]->value_type();
            } else if (_super) {
                return _super->get_property_type<ObjectType>(ob, name);
            }
            return boost::typeindex::type_id<void>();
        }

        template<typename ObjectType>
        std::shared_ptr<std::set<std::shared_ptr<vstd::property>>> properties(std::shared_ptr<ObjectType> ob) {
            std::shared_ptr<std::set<std::shared_ptr<vstd::property>>> props = std::make_shared<std::set<std::shared_ptr<vstd::property>>>();
            auto vals = _props | boost::adaptors::map_values;
            props->insert(vals.begin(), vals.end());
            vals = ob->dynamic_props() | boost::adaptors::map_values;
            props->insert(vals.begin(), vals.end());
            if (_super) {
                auto _props = _super->properties(ob);
                props->insert(_props->begin(), _props->end());
            }
            return props;
        }

        template<typename ObjectType,
                typename PropertyCallback>
        void for_properties(std::shared_ptr<ObjectType> ob,
                            PropertyCallback propertyCallback) {
            _for_properties(propertyCallback);
            for (auto &[name, property]:   ob->dynamic_props()) {
                if (propertyCallback(property)) {
                    return;
                }
            }
        }

        template<typename ObjectType,
                typename PropertyCallback>
        void for_all_properties(std::shared_ptr<ObjectType> ob,
                                PropertyCallback propertyCallback) {
            for_properties(ob, [&](auto prop) {
                propertyCallback(prop);
                return false;
            });
        }

        template<typename ObjectType>
        bool has_property(std::string name, std::shared_ptr<ObjectType> ob) {
            bool result = false;
            for_properties(ob, [&](auto &property) {
                return result = result || property->name() == name;
            });
            return result;
        }
    };
}