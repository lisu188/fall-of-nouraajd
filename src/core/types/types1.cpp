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

extern void add_member(std::shared_ptr<Value> object, std::string key, std::string value);

extern void add_member(std::shared_ptr<Value> object, std::string key, std::shared_ptr<Value> value);

extern void add_member(std::shared_ptr<Value> object, std::string key, bool value);

extern void add_member(std::shared_ptr<Value> object, std::string key, int value);

extern void add_arr_member(std::shared_ptr<Value> object, std::string value);

extern void add_arr_member(std::shared_ptr<Value> object, std::shared_ptr<Value> value);

extern void add_arr_member(std::shared_ptr<Value> object, bool value);

extern void add_arr_member(std::shared_ptr<Value> object, int value);

namespace {
    struct register_types1 {
        register_types1() {
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CSlotConfig, CGameObject>();
                CTypes::register_type<CSlot, CGameObject>();

                CTypes::register_type<CObjectHandler, CGameObject>();
                CTypes::register_type<CEventHandler, CGameObject>();

                CTypes::register_type<CFightController, CGameObject>();
                {
                    CTypes::register_type<CPlayerFightController, CFightController, CGameObject>();
                    CTypes::register_type<CMonsterFightController, CFightController, CGameObject>();
                }

                CTypes::register_type<CGameEvent, CGameObject>();
                {
                    CTypes::register_type<CGameEventCaused, CGameEvent, CGameObject>();
                }

                CTypes::register_type<CPlugin, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CPlugin>, CPlugin, CGameObject>();
                }
                CTypes::register_type<CGame, CGameObject>();
                CTypes::register_type<CMap, CGameObject>();

                CTypes::register_type<CListInt, CGameObject>();
                CTypes::register_type<CListString, CGameObject>();

                CTypes::register_type<CMapStringString, CGameObject>();
                CTypes::register_type<CMapStringInt, CGameObject>();
                CTypes::register_type<CMapIntString, CGameObject>();
                CTypes::register_type<CMapIntInt, CGameObject>();
            }

            auto array_string_deserialize = [](std::shared_ptr<CGame> game,
                                               std::shared_ptr<Value> object) {

                std::set<std::string> objects;
                for (unsigned int i = 0; i < object->size(); i++) {
                    objects.insert((*object)[i].asString());
                }
                return objects;

            };

            auto array_string_serialize = [](std::set<std::string> set) {
                std::shared_ptr<Value> arr = std::make_shared<Value>();
                for (std::string ob:set) {
                    add_arr_member(arr, ob);
                }
                return arr;
            };

            auto array_int_deserialize = [](std::shared_ptr<CGame> game,
                                            std::shared_ptr<Value> object) {

                std::set<int> objects;
                for (unsigned int i = 0; i < object->size(); i++) {
                    objects.insert((*object)[i].asInt());
                }
                return objects;

            };

            auto array_int_serialize = [](std::set<int> set) {
                std::shared_ptr<Value> arr = std::make_shared<Value>();
                for (int ob:set) {
                    add_arr_member(arr, ob);
                }
                return arr;
            };

            auto map_string_string_deserialize = [](std::shared_ptr<CGame> game,
                                                    std::shared_ptr<Value> object) {

                std::map<std::string, std::string> objects;
                for (auto name:object->getMemberNames()) {
                    objects[name] = (*object)[name].asString();
                }
                return objects;

            };

            auto map_string_string_serialize = [](std::map<std::string, std::string> map) {
                std::shared_ptr<Value> arr = std::make_shared<Value>();
                for (auto ob:map) {
                    add_member(arr, ob.first, ob.second);
                }
                return arr;
            };

            auto map_string_int_deserialize = [](std::shared_ptr<CGame> game,
                                                 std::shared_ptr<Value> object) {

                std::map<std::string, int> objects;
                for (auto name:object->getMemberNames()) {
                    objects[name] = (*object)[name].asInt();
                }
                return objects;

            };

            auto map_string_int_serialize = [](std::map<std::string, int> map) {
                std::shared_ptr<Value> arr = std::make_shared<Value>();
                for (auto ob:map) {
                    add_member(arr, ob.first, ob.second);
                }
                return arr;
            };

            auto map_int_string_deserialize = [](std::shared_ptr<CGame> game,
                                                 std::shared_ptr<Value> object) {

                std::map<int, std::string> objects;
                for (auto name:object->getMemberNames()) {
                    objects[vstd::to_int(name).first] = (*object)[name].asString();
                }
                return objects;

            };

            auto map_int_string_serialize = [](std::map<int, std::string> map) {
                std::shared_ptr<Value> arr = std::make_shared<Value>();
                for (auto ob:map) {
                    add_member(arr, vstd::str(ob.first), ob.second);
                }
                return arr;
            };

            auto map_int_int_deserialize = [](std::shared_ptr<CGame> game,
                                              std::shared_ptr<Value> object) {

                std::map<int, int> objects;
                for (auto name:object->getMemberNames()) {
                    objects[vstd::to_int(name).first] = (*object)[name].asInt();
                }
                return objects;

            };

            auto map_int_int_serialize = [](std::map<int, int> map) {
                std::shared_ptr<Value> arr = std::make_shared<Value>();
                for (auto ob:map) {
                    add_member(arr, vstd::str(ob.first), ob.second);
                }
                return arr;
            };

            CTypes::register_custom_type<std::set<std::string >>
                    (array_string_serialize, array_string_deserialize);

            CTypes::register_custom_type<std::set<int >>(
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
    } _register_types1;
}