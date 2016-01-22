#pragma once

#include "core/CGlobal.h"
#include "object/CObject.h"


class CTypes {
public:
    static void initialize();

    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *builders();

    static std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> *serializers();

    template<typename Serialized, typename Deserialized>
    static void register_serializer() {
        (*serializers())[vstd::type_pair<Serialized, Deserialized>()] =
                std::make_shared<CSerializer<Serialized, Deserialized>>();
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
        vstd::function_converter<std::shared_ptr<T>>();
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
        vstd::implicitly_convertible_cast<std::set<std::shared_ptr<T>>, std::set<std::shared_ptr<U>>>();
        vstd::implicitly_convertible_cast<std::map<std::string, std::shared_ptr<T>>, std::map<std::string, std::shared_ptr<U>>>();
    }

    template<typename T, typename U>
    static void register_any_cast() {
        vstd::register_any_type<std::shared_ptr<T>, std::shared_ptr<U>>();
        vstd::register_any_type<std::set<std::shared_ptr<T>>, std::set<std::shared_ptr<U>>>();
        vstd::register_any_type<std::map<std::string, std::shared_ptr<T>>, std::map<std::string, std::shared_ptr<U>>>();
    }

    template<typename T, typename U=T, typename... BASES>
    static void register_type() {
        static_assert(vstd::is_base_of<U, T>::value, "invalid base class");
        register_serializer<T>();
        register_builder<T>();
        register_consumer<T>();
        register_supplier<T>();
        register_predicate<T>();
        register_cast<T, U>();
        register_any_cast<T, U>();
        register_cast<U, T>();
        register_any_cast<U, T>();
        register_type<T, BASES...>();
    }
};


