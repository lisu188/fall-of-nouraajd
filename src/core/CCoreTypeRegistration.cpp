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
template <typename Value> std::set<Value> json_array_to_set(const std::shared_ptr<json> &object) {
    std::set<Value> values;
    std::ranges::transform(*object, std::inserter(values, values.end()),
                           [](const json &value) { return value.get<Value>(); });
    return values;
}

CTags json_array_to_tags(const std::shared_ptr<json> &object) {
    CTags tags;
    std::ranges::for_each(*object,
                          [&tags](const json &value) { tags.insert(CTags::fromString(value.get<std::string>())); });
    return tags;
}

template <typename Value> std::shared_ptr<json> set_to_json_array(const std::set<Value> &values) {
    auto arr = std::make_shared<json>(json::array());
    for (const auto &value : values) {
        add_arr_member(arr, value);
    }
    return arr;
}

std::shared_ptr<json> tags_to_json_array(const CTags &tags) {
    auto arr = std::make_shared<json>(json::array());
    for (CTag tag : tags) {
        add_arr_member(arr, std::string(CTags::toString(tag)));
    }
    return arr;
}

template <typename Value>
std::map<std::string, Value> json_object_to_string_key_map(const std::shared_ptr<json> &object) {
    std::map<std::string, Value> values;
    for (auto [key, value] : object->items()) {
        values.emplace(key, value.template get<Value>());
    }
    return values;
}

template <typename Value> std::map<int, Value> json_object_to_int_key_map(const std::shared_ptr<json> &object) {
    std::map<int, Value> values;
    for (auto [key, value] : object->items()) {
        values.emplace(vstd::to_int(key).first, value.template get<Value>());
    }
    return values;
}

template <typename Key, typename Value, typename KeySerializer>
std::shared_ptr<json> map_to_json_object(const std::map<Key, Value> &values, KeySerializer key_serializer) {
    auto object = std::make_shared<json>();
    for (const auto &[key, value] : values) {
        add_member(object, key_serializer(key), value);
    }
    return object;
}

void registerCustomValueTypes() {
    auto array_string_deserialize = [](std::shared_ptr<CGame>, std::shared_ptr<json> object) {
        return json_array_to_set<std::string>(object);
    };

    auto array_string_serialize = [](const std::set<std::string> &set) { return set_to_json_array(set); };

    auto tags_deserialize = [](std::shared_ptr<CGame>, std::shared_ptr<json> object) {
        return json_array_to_tags(object);
    };

    auto tags_serialize = [](const CTags &tags) { return tags_to_json_array(tags); };

    auto array_int_deserialize = [](std::shared_ptr<CGame>, std::shared_ptr<json> object) {
        return json_array_to_set<int>(object);
    };

    auto array_int_serialize = [](const std::set<int> &set) { return set_to_json_array(set); };

    auto map_string_string_deserialize = [](std::shared_ptr<CGame>, std::shared_ptr<json> object) {
        return json_object_to_string_key_map<std::string>(object);
    };

    auto map_string_string_serialize = [](const std::map<std::string, std::string> &map) {
        return map_to_json_object(map, std::identity{});
    };

    auto map_string_int_deserialize = [](std::shared_ptr<CGame>, std::shared_ptr<json> object) {
        return json_object_to_string_key_map<int>(object);
    };

    auto map_string_int_serialize = [](const std::map<std::string, int> &map) {
        return map_to_json_object(map, std::identity{});
    };

    auto map_int_string_deserialize = [](std::shared_ptr<CGame>, std::shared_ptr<json> object) {
        return json_object_to_int_key_map<std::string>(object);
    };

    auto map_int_string_serialize = [](const std::map<int, std::string> &map) {
        return map_to_json_object(map, [](int key) { return vstd::str(key); });
    };

    auto map_int_int_deserialize = [](std::shared_ptr<CGame>, std::shared_ptr<json> object) {
        return json_object_to_int_key_map<int>(object);
    };

    auto map_int_int_serialize = [](const std::map<int, int> &map) {
        return map_to_json_object(map, [](int key) { return vstd::str(key); });
    };

    CTypes::register_custom_type<std::set<std::string>>(array_string_serialize, array_string_deserialize);
    CTypes::register_custom_type<CTags>(tags_serialize, tags_deserialize);
    CTypes::register_custom_type<std::set<int>>(array_int_serialize, array_int_deserialize);
    CTypes::register_custom_type<std::map<std::string, std::string>>(map_string_string_serialize,
                                                                     map_string_string_deserialize);
    CTypes::register_custom_type<std::map<std::string, int>>(map_string_int_serialize, map_string_int_deserialize);
    CTypes::register_custom_type<std::map<int, std::string>>(map_int_string_serialize, map_int_string_deserialize);
    CTypes::register_custom_type<std::map<int, int>>(map_int_int_serialize, map_int_int_deserialize);
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
    CTypes::register_type<CListString, CGameObject>();
    CTypes::register_type<CMapStringString, CGameObject>();
    CTypes::register_type<CMapStringInt, CGameObject>();
    CTypes::register_type<CMapIntString, CGameObject>();
    CTypes::register_type<CMapIntInt, CGameObject>();

    CTypes::register_type<CSlotConfig, CGameObject>();
    CTypes::register_type<CSlot, CGameObject>();
    CTypes::register_type<CScript, CGameObject>();
}
} // namespace type_registration
