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

#include "core/CGame.h"
#include "core/CLoader.h"
#include "core/CTypes.h"
#include "object/CMapObject.h"
#include "test_harness.h"
#include "veventloop.h"

#include <cstddef>
#include <memory>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr int MAP_LOAD_OBJECT_COUNT = 32;
constexpr int MAP_LOAD_PROPERTY_COUNT = 8;

class MapLoadNotificationProbe : public CMapObject {
    V_META(MapLoadNotificationProbe, CMapObject,
           V_METHOD(MapLoadNotificationProbe, onPropertyChanged, void, std::string),
           V_METHOD(MapLoadNotificationProbe, onPropertiesChanged, void, std::set<std::string>))

  public:
    void onPropertyChanged(std::string) { ++property_changed_calls; }

    void onPropertiesChanged(std::set<std::string> property_names) {
        ++properties_changed_calls;
        changed_property_batches.push_back(std::move(property_names));
    }

    int property_changed_calls = 0;
    int properties_changed_calls = 0;
    std::vector<std::set<std::string>> changed_property_batches;
};

void drain_event_loop() {
    auto loop = vstd::event_loop<>::instance();
    for (int i = 0; i < 5; ++i) {
        loop->run();
    }
}

void connect_notifications(const std::shared_ptr<MapLoadNotificationProbe> &object) {
    object->connect("propertyChanged", object, "onPropertyChanged");
    object->connect("propertiesChanged", object, "onPropertiesChanged");
}

json make_observed_object_json(int index) {
    json object = json::object();
    object["type"] = "MapLoadNotificationProbe";
    object["name"] = "observedObject" + std::to_string(index);
    object["width"] = 16;
    object["height"] = 16;
    object["x"] = 16 * (index % 8);
    object["y"] = 16 * (index / 8);

    auto &properties = object["properties"];
    properties["label"] = "observed";
    properties["description"] = "bulk-loaded";
    properties["threat"] = index;
    properties["rank"] = index % 4;
    properties["active"] = true;
    properties["phase"] = "load";
    properties["score"] = index * 3;
    properties["visible"] = false;
    return object;
}

std::shared_ptr<json> make_map_json() {
    auto map_config = std::make_shared<json>(json::object());
    json layer = json::object();
    layer["type"] = "objectgroup";
    layer["properties"]["level"] = 0;
    layer["objects"] = json::array();
    for (int i = 0; i < MAP_LOAD_OBJECT_COUNT; ++i) {
        layer["objects"][layer["objects"].size()] = make_observed_object_json(i);
    }
    (*map_config)["layers"] = json::array({layer});
    return map_config;
}

void test_map_load_property_notifications_are_bounded_per_object() {
    CTypes::register_type_metadata<MapLoadNotificationProbe, CMapObject, CGameObject>();

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);

    std::vector<std::shared_ptr<MapLoadNotificationProbe>> objects;
    objects.reserve(MAP_LOAD_OBJECT_COUNT);
    for (int i = 0; i < MAP_LOAD_OBJECT_COUNT; ++i) {
        auto object = std::make_shared<MapLoadNotificationProbe>();
        connect_notifications(object);
        objects.push_back(object);
    }

    std::size_t next_object = 0;
    game->getObjectHandler()->registerType("MapLoadNotificationProbe", [&objects, &next_object]() {
        if (next_object >= objects.size()) {
            return std::make_shared<MapLoadNotificationProbe>();
        }
        return objects[next_object++];
    });

    CMapLoader::loadFromTmx(map, make_map_json());
    drain_event_loop();

    int property_changed_calls = 0;
    int properties_changed_calls = 0;
    int changed_property_names = 0;
    for (const auto &object : objects) {
        property_changed_calls += object->property_changed_calls;
        properties_changed_calls += object->properties_changed_calls;
        for (const auto &batch : object->changed_property_batches) {
            changed_property_names += static_cast<int>(batch.size());
        }
    }

    expect_true(next_object == objects.size(), "map load should instantiate every observed object");
    expect_true(map->getObjects().size() == static_cast<std::size_t>(MAP_LOAD_OBJECT_COUNT),
                "map load should add every observed object to the map");
    expect_true(property_changed_calls == 0,
                "bulk map object property load should suppress per-property notifications");
    expect_true(properties_changed_calls == MAP_LOAD_OBJECT_COUNT,
                "bulk map object property load should emit one batch notification per object");
    expect_true(changed_property_names == MAP_LOAD_OBJECT_COUNT * MAP_LOAD_PROPERTY_COUNT,
                "bulk map object property load should preserve every changed property name in batches");
}

} // namespace

void run_serialization_performance_tests() { test_map_load_property_notifications_are_bounded_per_object(); }
