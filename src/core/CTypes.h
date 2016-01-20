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
        function_converter<bool, std::shared_ptr<T>>();
    }

    template<typename T>
    static void register_supplier() {
        function_converter<std::shared_ptr<T>>();
    }

    template<typename T>
    static void register_consumer() {
        function_converter<std::shared_ptr<T>>();
    }

    template<typename T, typename U=CGameObject>
    static void register_cast() {
        implicitly_convertible_cast<std::shared_ptr<U>, std::shared_ptr<T>>();
    }

    template<typename T>
    static void register_serializer() {
        register_serializer<std::shared_ptr<Value>, std::shared_ptr<T>>();
        register_serializer<std::shared_ptr<Value>, std::set<std::shared_ptr<T>>>();
        register_serializer<std::shared_ptr<Value>, std::map<std::string, std::shared_ptr<T>>>();
    }

    template<typename T>
    static void register_type() {
        static_assert(vstd::is_base_of<CGameObject, T>::value, "invalid base class");
        register_serializer<T>();
        register_builder<T>();
        register_consumer<T>();
        register_supplier<T>();
        register_predicate<T>();
        register_cast<T>();
    }
};


