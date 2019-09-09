//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#pragma once

#include "core/CGlobal.h"
#include "object/CObject.h"
#include "core/CSerialization.h"

class CTypes {
public:

    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *builders();

    static std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> *
    serializers();

    static std::unordered_set<boost::typeindex::type_index> *pointer_types();

    static std::unordered_set<boost::typeindex::type_index> *array_types();

    static std::unordered_set<boost::typeindex::type_index> *map_types();

    static std::unordered_map<boost::typeindex::type_index, std::function<void(std::shared_ptr<CGameObject>,
                                                                               std::string, boost::any)>> *setters();

    static bool is_map_type(boost::typeindex::type_index index);

    static bool is_pointer_type(boost::typeindex::type_index index);

    static bool is_array_type(boost::typeindex::type_index index);

    template<typename T>
    static bool is_map_type() {
        return is_map_type(boost::typeindex::type_id<T>());
    }

    template<typename T>
    static bool is_pointer_type() {
        return is_pointer_type(boost::typeindex::type_id<T>());
    }

    template<typename T>
    static bool is_array_type() {
        return is_array_type(boost::typeindex::type_id<T>());
    }

    template<typename Serialized, typename Deserialized>
    static void register_serializer() {
        (*serializers())[vstd::type_pair<Serialized, Deserialized>()] =
                std::make_shared<CSerializer<Serialized, Deserialized>>();
    }

    template<typename T>
    static void register_custom_setter() {
        (*setters())[boost::typeindex::type_id<T>()] = [](std::shared_ptr<CGameObject> object,
                                                          std::string key, boost::any value) {
            object->setProperty(key, vstd::any_cast<T>(value));
        };
    }


    template<typename Serialized, typename Deserialized>
    static void register_custom_serializer(std::function<Serialized(Deserialized)> serialize,
                                           std::function<Deserialized(std::shared_ptr<CGame>,
                                                                      Serialized)> deserialize) {
        (*serializers())[vstd::type_pair<Serialized, Deserialized>()] =
                std::make_shared<CCustomSerializer<Serialized, Deserialized>>(serialize, deserialize);
    }

    template<typename T>
    static void register_builder() {
        (*builders())[T::static_meta()->name()] = []() { return std::make_shared<T>(); };
    }

    template<typename T>
    static void register_predicate() {
        vstd::function_converter<bool, std::shared_ptr<T>>();
    }

    template<typename T>
    static void register_supplier() {
        vstd::function_converter<std::shared_ptr<T>>();
    }

    template<typename T>
    static void register_consumer() {
        vstd::function_converter<void, std::shared_ptr<T>>();
    }

    template<typename T>
    static void register_pointer() {
        vstd::register_pointer<T>();
    }

    template<typename T>
    static void register_serializer() {
        register_serializer<std::shared_ptr<Value>, std::shared_ptr<T>>();
        register_serializer<std::shared_ptr<Value>, std::set<std::shared_ptr<T>>>();
        register_serializer<std::shared_ptr<Value>, std::map<std::string, std::shared_ptr<T>>>();
    }

    template<typename T, typename U>
    static void register_cast() {
        vstd::implicitly_convertible_cast<std::shared_ptr<T>, std::shared_ptr<U>>();
    }

    template<typename T, typename U>
    static void register_any_cast() {
        vstd::register_any_type<std::shared_ptr<T>, std::shared_ptr<U>>();
        vstd::register_any_type<std::set<std::shared_ptr<T>>, std::set<std::shared_ptr<U>>>();
        vstd::register_any_type<std::map<std::string, std::shared_ptr<T>>, std::map<std::string, std::shared_ptr<U>>>();
    }

    template<typename T>
    static void register_derived_types() {
        pointer_types()->insert(boost::typeindex::type_id<std::shared_ptr<T>>());
        array_types()->insert(boost::typeindex::type_id<std::set<std::shared_ptr<T>>>());
        map_types()->insert(boost::typeindex::type_id<std::map<std::string, std::shared_ptr<T>>>());
    }

    template<typename T, typename U, typename... Args>
    static void register_type() {
        static_assert(vstd::is_base_of<U, T>::value && !vstd::is_same<T, U>::value, "invalid base class");
        register_type<T>();
        register_any_cast<T, U>();
        register_any_cast<U, T>();
        register_cast<U, T>();
        register_type<T, Args...>();
    }

    template<typename T>
    static void register_type() {
        register_pointer<T>();
        register_serializer<T>();
        register_builder<T>();
        register_consumer<T>();
        register_supplier<T>();
        register_predicate<T>();
        register_derived_types<T>();
        register_any_cast<T, T>();
    }

    template<typename T>
    static void register_custom_type(std::function<std::shared_ptr<Json::Value>(T)> serialize,
                                     std::function<T(std::shared_ptr<CGame>,
                                                     std::shared_ptr<Json::Value>)> deserialize) {
        register_custom_serializer(serialize, deserialize);
        register_custom_setter<T>();
    }

    static void set_custom_property(std::shared_ptr<CGameObject> object,
                                    std::string key, boost::any property) {
        (*setters())[property.type()](object, key, property);
    }
};


