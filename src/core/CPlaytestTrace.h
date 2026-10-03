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
#pragma once

#include "core/CJson.h"
#include "core/CUtil.h"

#include <cstddef>
#include <memory>
#include <set>
#include <string>
#include <vector>

class CCreature;
class CGameObject;
class CItem;
class CMap;

class CPlaytestTrace {
  public:
    static void configureFromEnvironment();
    static void configure(bool enabled, const std::string &outputTarget = "", std::size_t maxRecords = 1000);
    static bool enabled();
    static void clear();
    static std::vector<std::string> records();
    static std::vector<std::string> drain();
    static void record(const std::string &event, json fields = json::object());
    static void recordJson(const std::string &event, const std::string &fieldsJson);

    static json coords(Coords coords);
    static json objectRef(const std::shared_ptr<CGameObject> &object);
    static json objectRefs(const std::vector<std::shared_ptr<CCreature>> &objects);
    static json itemRefs(const std::set<std::shared_ptr<CItem>> &items);
    static void addMapContext(json &fields, const std::shared_ptr<CMap> &map);
};
