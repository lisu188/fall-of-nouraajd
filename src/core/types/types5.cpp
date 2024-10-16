/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/panel/CGameQuestPanel.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "core/CController.h"
#include "core/CList.h"
#include "core/CScript.h"
#include "handler/CRngHandler.h"

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::string &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::shared_ptr<json> &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, bool value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, int value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::string &value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::shared_ptr<json> &value);

extern void add_arr_member(const std::shared_ptr<json> &object, bool value);

extern void add_arr_member(const std::shared_ptr<json> &object, int value);

namespace {
    struct register_types5 {
        register_types5() {
            auto array_string_deserialize = [](std::shared_ptr<CGame> game,
                                               std::shared_ptr<json> object) {
                std::set<std::string> objects;
                for (unsigned int i = 0; i < object->size(); i++) {
                    objects.insert((*object)[i].get<std::string>());
                }
                return objects;
            };

            auto array_string_serialize = [](std::set<std::string> set) {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (std::string ob: set) {
                    add_arr_member(arr, ob);
                }
                return arr;
            };

            auto array_int_deserialize = [](std::shared_ptr<CGame> game,
                                            std::shared_ptr<json> object) {
                std::set<int> objects;
                for (unsigned int i = 0; i < object->size(); i++) {
                    objects.insert((*object)[i].get<int>());
                }
                return objects;
            };

            auto array_int_serialize = [](std::set<int> set) {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (int ob: set) {
                    add_arr_member(arr, ob);
                }
                return arr;
            };

            auto map_string_string_deserialize = [](std::shared_ptr<CGame> game,
                                                    std::shared_ptr<json> object) {
                std::map<std::string, std::string> objects;
                for (auto [key, value]: object->items()) {
                    objects[key] = value.get<std::string>();
                }
                return objects;
            };

            auto map_string_string_serialize = [](std::map<std::string, std::string> map) {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob: map) {
                    add_member(arr, ob.first, ob.second);
                }
                return arr;
            };

            auto map_string_int_deserialize = [](std::shared_ptr<CGame> game,
                                                 std::shared_ptr<json> object) {
                std::map<std::string, int> objects;
                for (auto [key, value]: object->items()) {
                    objects[key] = value.get<int>();
                }
                return objects;
            };

            auto map_string_int_serialize = [](std::map<std::string, int> map) {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob: map) {
                    add_member(arr, ob.first, ob.second);
                }
                return arr;
            };

            auto map_int_string_deserialize = [](std::shared_ptr<CGame> game,
                                                 std::shared_ptr<json> object) {
                std::map<int, std::string> objects;
                for (auto [key, value]: object->items()) {
                    objects[vstd::to_int(key).first] = value.get<std::string>();
                }
                return objects;
            };

            auto map_int_string_serialize = [](std::map<int, std::string> map) {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob: map) {
                    add_member(arr, vstd::str(ob.first), ob.second);
                }
                return arr;
            };

            auto map_int_int_deserialize = [](std::shared_ptr<CGame> game,
                                              std::shared_ptr<json> object) {
                std::map<int, int> objects;
                for (auto [key, value]: object->items()) {
                    objects[vstd::to_int(key).first] = value.get<int>();
                }
                return objects;
            };

            auto map_int_int_serialize = [](std::map<int, int> map) {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob: map) {
                    add_member(arr, vstd::str(ob.first), ob.second);
                }
                return arr;
            };

            CTypes::register_custom_type<std::set<std::string> >
                    (array_string_serialize, array_string_deserialize);

            CTypes::register_custom_type<std::set<int> >(
                array_int_serialize, array_int_deserialize);

            CTypes::register_custom_type<std::map<std::string, std::string> >(
                map_string_string_serialize, map_string_string_deserialize);

            CTypes::register_custom_type<std::map<std::string, int> >(
                map_string_int_serialize, map_string_int_deserialize);

            CTypes::register_custom_type<std::map<int, std::string> >(
                map_int_string_serialize, map_int_string_deserialize);

            CTypes::register_custom_type<std::map<int, int> >(
                map_int_int_serialize, map_int_int_deserialize);
        }
    } _register_types5;
}
