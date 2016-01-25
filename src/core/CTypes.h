#pragma once

#include "core/CGlobal.h"
#include "object/CObject.h"


class CTypes {
public:

    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *builders();

    static std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> *serializers();

    static std::unordered_set<boost::typeindex::type_index> *pointer_types();

    static std::unordered_set<boost::typeindex::type_index> *array_types();

    static std::unordered_set<boost::typeindex::type_index> *map_types();

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
        register_serializer<T>();
        register_builder<T>();
        register_consumer<T>();
        register_supplier<T>();
        register_predicate<T>();
        register_derived_types<T>();
        register_any_cast<T, T>();
    }
};


