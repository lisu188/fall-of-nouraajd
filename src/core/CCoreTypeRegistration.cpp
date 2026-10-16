/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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
#include "core/CTypeRegistration.h"
#include "core/CGame.h"
#include "core/CList.h"
#include "core/CMap.h"
#include "core/CPlugin.h"
#include "core/CSerialization.h"
#include "core/CSlotConfig.h"
#include "core/CScript.h"
#include "core/CStats.h"
#include "core/CTags.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"

#include <algorithm>
#include <functional>
#include <iterator>

namespace {
template <typename Value> std::set<Value> json_array_to_set(const json &object) {
    std::set<Value> values;
    std::ranges::transform(object, std::inserter(values, values.end()),
                           [](const json &value) { return value.get<Value>(); });
    return values;
}

CTags json_array_to_tags(const json &object) {
    CTags tags;
    std::ranges::for_each(object,
                          [&tags](const json &value) { tags.insert(CTags::fromString(value.get<std::string>())); });
    return tags;
}

template <typename Value> json set_to_json_array(const std::set<Value> &values) {
    auto arr = json::array();
    for (const auto &value : values) {
        arr[arr.size()] = value;
    }
    return arr;
}

json tags_to_json_array(const CTags &tags) {
    auto arr = json::array();
    for (CTag tag : tags) {
        arr[arr.size()] = std::string(CTags::toString(tag));
    }
    return arr;
}

template <typename Value> std::map<std::string, Value> json_object_to_string_key_map(const json &object) {
    std::map<std::string, Value> values;
    for (auto [key, value] : object.items()) {
        values.emplace(key, value.template get<Value>());
    }
    return values;
}

template <typename Value> std::map<int, Value> json_object_to_int_key_map(const json &object) {
    std::map<int, Value> values;
    for (auto [key, value] : object.items()) {
        if (key.empty()) {
            vstd::logger::warning("Skipping empty integer map key");
            continue;
        }
        auto parsed = vstd::to_int(key);
        if (!parsed.second) {
            vstd::logger::warning("Skipping invalid integer map key:", key);
            continue;
        }
        values.emplace(parsed.first, value.template get<Value>());
    }
    return values;
}

template <typename Key, typename Value, typename KeySerializer>
json map_to_json_object(const std::map<Key, Value> &values, KeySerializer key_serializer) {
    json object;
    for (const auto &[key, value] : values) {
        object[key_serializer(key)] = value;
    }
    return object;
}

void registerCustomValueTypes() {
    auto array_string_deserialize = [](const std::shared_ptr<CGame> &, const json &object) {
        return json_array_to_set<std::string>(object);
    };

    auto array_string_serialize = [](const std::set<std::string> &set) { return set_to_json_array(set); };

    auto list_string_deserialize =
        [](const std::shared_ptr<CGame> &, const json &object,
           CSerializationReadContext &context) -> CSerializationResult<std::list<std::string>> {
        if (!object.is_array()) {
            return std::unexpected(CSerializationError{CSerializationErrorCode::TypeMismatch, context.source(),
                                                       context.path(), context.objectType(),
                                                       "Expected an array for an ordered string list"});
        }
        std::list<std::string> values;
        std::size_t index = 0;
        for (const auto &value : object) {
            CSerializationReadContext::PropertyScope entryScope(context, "[" + std::to_string(index++) + "]", {}, true);
            if (!value.is_string()) {
                return std::unexpected(CSerializationError{CSerializationErrorCode::TypeMismatch, context.source(),
                                                           context.path(), context.objectType(),
                                                           "Expected a string in an ordered string list"});
            }
            values.push_back(value.get<std::string>());
        }
        return values;
    };

    auto list_string_serialize = [](const std::list<std::string> &values) {
        auto array = json::array();
        for (const auto &value : values)
            array[array.size()] = value;
        return array;
    };

    auto tags_deserialize = [](const std::shared_ptr<CGame> &, const json &object) {
        return json_array_to_tags(object);
    };

    auto tags_serialize = [](const CTags &tags) { return tags_to_json_array(tags); };

    auto array_int_deserialize = [](const std::shared_ptr<CGame> &, const json &object) {
        return json_array_to_set<int>(object);
    };

    auto array_int_serialize = [](const std::set<int> &set) { return set_to_json_array(set); };

    auto map_string_string_deserialize = [](const std::shared_ptr<CGame> &, const json &object) {
        return json_object_to_string_key_map<std::string>(object);
    };

    auto map_string_string_serialize = [](const std::map<std::string, std::string> &map) {
        return map_to_json_object(map, std::identity{});
    };

    auto map_string_int_deserialize = [](const std::shared_ptr<CGame> &, const json &object) {
        return json_object_to_string_key_map<int>(object);
    };

    auto map_string_int_serialize = [](const std::map<std::string, int> &map) {
        return map_to_json_object(map, std::identity{});
    };

    auto map_int_string_deserialize = [](const std::shared_ptr<CGame> &, const json &object) {
        return json_object_to_int_key_map<std::string>(object);
    };

    auto map_int_string_serialize = [](const std::map<int, std::string> &map) {
        return map_to_json_object(map, [](int key) { return vstd::str(key); });
    };

    auto map_int_int_deserialize = [](const std::shared_ptr<CGame> &, const json &object) {
        return json_object_to_int_key_map<int>(object);
    };

    auto map_int_int_serialize = [](const std::map<int, int> &map) {
        return map_to_json_object(map, [](int key) { return vstd::str(key); });
    };

    CTypes::registerJsonType<std::set<std::string>>(array_string_serialize, array_string_deserialize);
    CTypes::registerJsonType<std::list<std::string>>(list_string_serialize, list_string_deserialize);
    CTypes::registerJsonType<CTags>(tags_serialize, tags_deserialize);
    CTypes::registerJsonType<std::set<int>>(array_int_serialize, array_int_deserialize);
    CTypes::registerJsonType<std::map<std::string, std::string>>(map_string_string_serialize,
                                                                 map_string_string_deserialize);
    CTypes::registerJsonType<std::map<std::string, int>>(map_string_int_serialize, map_string_int_deserialize);
    CTypes::registerJsonType<std::map<int, std::string>>(map_int_string_serialize, map_int_string_deserialize);
    CTypes::registerJsonType<std::map<int, int>>(map_int_int_serialize, map_int_int_deserialize);
}
} // namespace

namespace type_registration {
void registerCoreTypes() {
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CGame, CGameObject>();
    CTypes::register_type<CMap, CGameObject>();
    CTypes::register_type<CPlugin, CGameObject>();
    CTypes::register_type<CNativeContentPlugin, CPlugin, CGameObject>();
    CTypes::register_type<CWrapper<CPlugin>, CPlugin, CGameObject>();

    CTypes::register_type<CStats, CGameObject>();
    CTypes::register_type<CDamage, CGameObject>();

    registerCustomValueTypes();

    CTypes::register_type<CListInt, CGameObject>();
    CTypes::registerPrimitiveType<CListInt, std::set<int>>();
    CTypes::register_type<CListString, CGameObject>();
    CTypes::registerPrimitiveType<CListString, std::set<std::string>>();
    CTypes::register_type<CMapStringString, CGameObject>();
    CTypes::registerPrimitiveType<CMapStringString, std::map<std::string, std::string>>();
    CTypes::register_type<CMapStringInt, CGameObject>();
    CTypes::registerPrimitiveType<CMapStringInt, std::map<std::string, int>>();
    CTypes::register_type<CMapIntString, CGameObject>();
    CTypes::registerPrimitiveType<CMapIntString, std::map<int, std::string>>();
    CTypes::register_type<CMapIntInt, CGameObject>();
    CTypes::registerPrimitiveType<CMapIntInt, std::map<int, int>>();

    CTypes::register_type<CSlotConfig, CGameObject>();
    CTypes::register_type<CSlot, CGameObject>();
    CTypes::register_type<CScript, CGameObject>();
}
} // namespace type_registration
