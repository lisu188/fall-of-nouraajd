/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once

#include <stdexcept>

#include "core/CConcepts.h"
#include "core/CGlobal.h"
#include "core/CSerialization.h"
#include "object/CObject.h"

class CTypes {
  public:
    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *builders();

    static std::unordered_map<std::pair<std::type_index, std::type_index>, std::shared_ptr<CSerializerBase>> *
    serializers();

    static std::unordered_set<std::type_index> *pointer_types();

    static std::unordered_set<std::type_index> *array_types();

    static std::unordered_set<std::type_index> *map_types();

    static std::unordered_map<std::type_index,
                              std::function<void(std::shared_ptr<CGameObject>, std::string, std::any)>> *
    setters();

    static bool is_map_type(std::type_index index);

    static bool is_pointer_type(std::type_index index);

    static bool is_array_type(std::type_index index);

    template <typename T> static bool is_map_type() { return is_map_type(std::type_index(typeid(T))); }

    template <typename T> static bool is_pointer_type() { return is_pointer_type(std::type_index(typeid(T))); }

    template <typename T> static bool is_array_type() { return is_array_type(std::type_index(typeid(T))); }

    template <typename Serialized, typename Deserialized> static void register_serializer() {
        (*serializers())[vstd::type_pair<Serialized, Deserialized>()] =
            std::make_shared<CSerializer<Serialized, Deserialized>>();
    }

    template <typename T> static void register_custom_setter() {
        (*setters())[std::type_index(typeid(T))] = [](std::shared_ptr<CGameObject> object, std::string key,
                                                      std::any value) {
            object->setProperty(key, vstd::any_cast<T>(value));
        };
    }

    template <typename Serialized, typename Deserialized>
    static void
    register_custom_serializer(std::function<Serialized(Deserialized)> serialize,
                               std::function<Deserialized(std::shared_ptr<CGame>, Serialized)> deserialize) {
        (*serializers())[vstd::type_pair<Serialized, Deserialized>()] =
            std::make_shared<CCustomSerializer<Serialized, Deserialized>>(serialize, deserialize);
    }

    template <fn::MetaRegisteredGameObject T> static void register_builder() {
        (*builders())[T::static_meta()->name()] = []() { return std::make_shared<T>(); };
    }

    template <fn::GameObjectDerived T> static void register_predicate() {}

    template <fn::GameObjectDerived T> static void register_supplier() {}

    template <fn::GameObjectDerived T> static void register_consumer() {}

    template <fn::GameObjectDerived T> static void register_pointer() {}

    template <fn::GameObjectDerived T> static void register_serializer() {
        (*serializers())[vstd::type_pair<std::shared_ptr<json>, std::shared_ptr<T>>()] =
            game_object_pointer_serializer();
        (*serializers())[vstd::type_pair<std::shared_ptr<json>, std::set<std::shared_ptr<T>>>()] =
            game_object_set_serializer();
        (*serializers())[vstd::type_pair<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<T>>>()] =
            game_object_map_serializer();
    }

    template <fn::GameObjectDerived T, fn::GameObjectDerived U> static void register_cast() {}

    template <fn::GameObjectDerived T, fn::GameObjectDerived U> static void register_any_cast() {
        vstd::register_any_type<std::shared_ptr<T>, std::shared_ptr<U>>();
        vstd::register_any_type<std::set<std::shared_ptr<T>>, std::set<std::shared_ptr<U>>>();
        vstd::register_any_type<std::map<std::string, std::shared_ptr<T>>, std::map<std::string, std::shared_ptr<U>>>();
    }

    template <fn::GameObjectDerived T> static void register_derived_types() {
        pointer_types()->insert(std::type_index(typeid(std::shared_ptr<T>)));
        array_types()->insert(std::type_index(typeid(std::set<std::shared_ptr<T>>)));
        map_types()->insert(std::type_index(typeid(std::map<std::string, std::shared_ptr<T>>)));
    }

    template <fn::MetaRegisteredGameObject T, fn::GameObjectDerived U, fn::GameObjectDerived... Args>
    static void register_type() {
        static_assert(std::derived_from<T, U> && !std::same_as<T, U>, "invalid base class");
        register_type<T>();
        register_any_cast<T, U>();
        register_any_cast<U, T>();
        register_cast<U, T>();
        register_type<T, Args...>();
    }

    template <fn::MetaRegisteredGameObject T> static void register_type() {
        register_serializer<T>();
        register_builder<T>();
        register_consumer<T>();
        register_supplier<T>();
        register_predicate<T>();
        register_derived_types<T>();
        register_any_cast<T, T>();
    }

    template <typename T>
    static void register_custom_type(std::function<std::shared_ptr<json>(T)> serialize,
                                     std::function<T(std::shared_ptr<CGame>, std::shared_ptr<json>)> deserialize) {
        register_custom_serializer(serialize, deserialize);
        register_custom_setter<T>();
    }

    static void set_custom_property(std::shared_ptr<CGameObject> object, std::string key, std::any property) {
        auto propertyType = std::type_index(property.type());
        auto setter = setters()->find(propertyType);
        if (setter == setters()->end() || !setter->second) {
            throw std::runtime_error("No custom setter registered for property '" + key + "' of type '" +
                                     std::string(propertyType.name()) + "'");
        }
        setter->second(object, key, property);
    }
};
