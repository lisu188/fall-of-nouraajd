/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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

#include "core/CJsonUtil.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CList.h"
#include "core/CMap.h"
#include "core/CPathFinder.h"
#include "core/CPlaytestTrace.h"
#include "core/CSaveFormat.h"
#include "core/CSerialization.h"
#include "core/CScript.h"
#include "core/CTags.h"
#include "core/CTypes.h"
#include "core/CUtil.h"
#include "gui/CSdlResources.h"
#include "object/CCreature.h"
#include "object/CGameObject.h"
#include "object/CItem.h"
#include "test_harness.h"
#include "vutil.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>

namespace {

template <typename Func> void expect_runtime_error(Func func, const char *message) {
    bool threw = false;
    try {
        func();
    } catch (const std::runtime_error &) {
        threw = true;
    }
    expect_true(threw, message);
}

struct TagProbe {
    CTags tags;

    bool hasTag(CTag tag) { return tags.contains(tag); }
};

struct ConceptCanStep {
    bool operator()(const Coords &) const { return true; }
};

struct ConceptWaypoint {
    std::optional<Coords> operator()(const Coords &) const { return std::nullopt; }
};

struct ConceptNeighbors {
    std::vector<Coords> operator()(const Coords &coords) const { return default_neighbors(coords); }
};

struct ConceptDistance {
    double operator()(const Coords &from, const Coords &to) const { return from.getDist(to); }
};

struct ConceptStepCost {
    int operator()(const Coords &, const Coords &) const { return 1; }
};

class PropertyChangeProbe : public CGameObject {
    V_META(PropertyChangeProbe, CGameObject, V_METHOD(PropertyChangeProbe, onPropertyChanged, void, std::string),
           V_METHOD(PropertyChangeProbe, onPropertiesChanged, void, std::set<std::string>),
           V_METHOD(PropertyChangeProbe, onLabelChanged), V_METHOD(PropertyChangeProbe, onThreatChanged))

  public:
    void onPropertyChanged(std::string property_name) { changed_properties.push_back(property_name); }

    void onPropertiesChanged(std::set<std::string> property_names) {
        changed_property_batches.push_back(property_names);
    }

    void onLabelChanged() { ++label_changed_calls; }

    void onThreatChanged() { ++threat_changed_calls; }

    std::vector<std::string> changed_properties;
    std::vector<std::set<std::string>> changed_property_batches;
    int label_changed_calls = 0;
    int threat_changed_calls = 0;
};

class PrimitiveSerializationHolder : public CGameObject {
    V_META(PrimitiveSerializationHolder, CGameObject,
           V_PROPERTY(PrimitiveSerializationHolder, std::shared_ptr<CListString>, listValues, getListValues,
                      setListValues),
           V_PROPERTY(PrimitiveSerializationHolder, std::shared_ptr<CMapStringString>, mapValues, getMapValues,
                      setMapValues))

  public:
    std::shared_ptr<CListString> getListValues() { return listValues; }

    void setListValues(std::shared_ptr<CListString> value) { listValues = value; }

    std::shared_ptr<CMapStringString> getMapValues() { return mapValues; }

    void setMapValues(std::shared_ptr<CMapStringString> value) { mapValues = value; }

  private:
    std::shared_ptr<CListString> listValues;
    std::shared_ptr<CMapStringString> mapValues;
};

void drain_event_loop() {
    auto loop = vstd::event_loop<>::instance();
    for (int i = 0; i < 5; ++i) {
        loop->run();
    }
}

static_assert(fn::PathPassability<ConceptCanStep>);
static_assert(fn::PathWaypoint<ConceptWaypoint>);
static_assert(fn::PathNeighbors<ConceptNeighbors>);
static_assert(fn::PathDistance<ConceptDistance>);
static_assert(fn::PathStepCost<ConceptStepCost>);
static_assert(std::is_const_v<std::remove_reference_t<decltype(ZERO)>>);
static_assert(EAST + SOUTH == Coords(1, 1, 0));
static_assert(UP - DOWN == Coords(0, 0, 2));

void test_string_deserialization_preserves_empty_and_whitespace() {
    auto empty_value = CSerialization::coerceStringProperty(std::type_index(typeid(std::string)), "");
    expect_true(std::holds_alternative<std::string>(empty_value) && std::get<std::string>(empty_value).empty(),
                "string deserialization should preserve intentionally empty strings");

    auto blank_value = CSerialization::coerceStringProperty(std::type_index(typeid(std::string)), "   ");
    expect_true(std::holds_alternative<std::string>(blank_value) && std::get<std::string>(blank_value) == "   ",
                "string deserialization should preserve whitespace-only strings");
}

void test_string_deserialization_coerces_non_string_targets() {
    auto numeric_value = CSerialization::coerceStringProperty(std::type_index(typeid(int)), "42");
    expect_true(std::holds_alternative<int>(numeric_value) && std::get<int>(numeric_value) == 42,
                "numeric string deserialization should preserve numeric coercion for numeric targets");

    auto bool_value = CSerialization::coerceStringProperty(std::type_index(typeid(bool)), "true");
    expect_true(std::holds_alternative<bool>(bool_value) && std::get<bool>(bool_value),
                "boolean string deserialization should preserve boolean coercion for boolean targets");
}

void test_happy_path_add_and_distance() {
    Coords sum = Coords(2, 3, 0) + Coords(1, -1, 0);
    Coords diff = Coords(4, 2, 1) - Coords(1, 5, -2);
    expect_true(sum == Coords(3, 2, 0), "Coords::operator+ should add each component");
    expect_true(diff == Coords(3, -3, 3), "Coords::operator- should subtract each component");
    expect_true((*Coords(6, 7, 8)) == Coords(6, 7, 8), "Coords::operator* should return same coordinates");
    expect_true(Coords(0, 0, 0).getDist(Coords(3, 4, 0)) == 5.0,
                "Coords::getDist should compute Euclidean distance in XY plane");
}

void test_edge_case_adjacent_or_same() {
    Coords origin(7, 7, 0);
    expect_true(origin.adjacentOrSame(origin), "adjacentOrSame should accept identical coordinates");
    expect_true(origin.same(origin), "same should return true for same coordinates");
    expect_true(origin.adjacent(Coords(8, 7, 0)), "adjacent should allow cardinal neighbors");
    expect_true(!origin.adjacent(Coords(8, 8, 0)), "adjacent should reject diagonal neighbors");
    expect_true(!origin.adjacent(Coords(7, 7, 1)), "adjacent should ignore Z-only movement");
}

void test_comparison_and_ordering() {
    expect_true(Coords(1, 2, 3) < Coords(1, 3, 0), "operator< should compare y when x is equal");
    expect_true(Coords(1, 2, 3) < Coords(1, 2, 4), "operator< should compare z when x and y are equal");
    expect_true(!(Coords(2, 0, 0) < Coords(1, 99, 99)), "operator< should reject larger x values");
    expect_true(Coords(2, 0, 0) > Coords(1, 99, 99), "operator> should invert operator< for non-equal values");
    expect_true(!(Coords(1, 2, 3) > Coords(1, 2, 3)), "operator> should reject equal coordinates");
    expect_true(Coords(1, 2, 3) != Coords(1, 2, 4), "operator!= should detect different coordinates");
}

void test_direction_mapping() {
    expect_true(CUtil::getDirection(ZERO) == Coords::Direction::ZERO, "getDirection should detect ZERO direction");
    expect_true(CUtil::getDirection(EAST) == Coords::Direction::EAST, "getDirection should detect EAST direction");
    expect_true(CUtil::getDirection(WEST) == Coords::Direction::WEST, "getDirection should detect WEST direction");
    expect_true(CUtil::getDirection(NORTH) == Coords::Direction::NORTH, "getDirection should detect NORTH direction");
    expect_true(CUtil::getDirection(SOUTH) == Coords::Direction::SOUTH, "getDirection should detect SOUTH direction");
    expect_true(CUtil::getDirection(UP) == Coords::Direction::UP, "getDirection should detect UP direction");
    expect_true(CUtil::getDirection(DOWN) == Coords::Direction::DOWN, "getDirection should detect DOWN direction");
    expect_true(CUtil::getDirection(Coords(2, 1, 0)) == Coords::Direction::UNDEFINED,
                "getDirection should return UNDEFINED for unsupported vectors");
}

void test_rect_bounds_inclusion() {
    auto rect = CUtil::rect(10, 20, 30, 40);
    auto bounds = CUtil::bounds(rect);
    auto centered = CUtil::boxInBox(CUtil::rect(0, 0, 10, 10), CUtil::rect(0, 0, 4, 6));
    auto centered_at = CUtil::centeredRect(50, 40, 10, 6);

    expect_true(bounds->x == 10 && bounds->y == 40 && bounds->w == 20 && bounds->h == 60,
                "bounds should return left, right, top and bottom values");
    expect_true(centered->x == 3 && centered->y == 2 && centered->w == 4 && centered->h == 6,
                "boxInBox should center the inner box");
    expect_true(centered_at->x == 45 && centered_at->y == 37 && centered_at->w == 10 && centered_at->h == 6,
                "centeredRect should position a rectangle around its center point");

    expect_true(CUtil::isIn(rect, 10, 20), "isIn should include lower bounds");
    expect_true(CUtil::isIn(rect, 40, 60), "isIn should include upper bounds");
    expect_true(!CUtil::isIn(rect, 9, 20), "isIn should reject x outside left bound");
    expect_true(!CUtil::isIn(rect, 41, 20), "isIn should reject x outside right bound");
    expect_true(!CUtil::isIn(rect, 10, 61), "isIn should reject y outside bottom bound");
}

void test_boundary_invalid_key_parsing() {
    expect_true(CUtil::parseKey(SDLK_0) == 0, "parseKey should parse zero");
    expect_true(CUtil::parseKey(SDLK_1) == 1, "parseKey should parse one");
    expect_true(CUtil::parseKey(SDLK_2) == 2, "parseKey should parse two");
    expect_true(CUtil::parseKey(SDLK_3) == 3, "parseKey should parse three");
    expect_true(CUtil::parseKey(SDLK_4) == 4, "parseKey should parse four");
    expect_true(CUtil::parseKey(SDLK_5) == 5, "parseKey should parse five");
    expect_true(CUtil::parseKey(SDLK_6) == 6, "parseKey should parse six");
    expect_true(CUtil::parseKey(SDLK_7) == 7, "parseKey should parse seven");
    expect_true(CUtil::parseKey(SDLK_8) == 8, "parseKey should parse eight");
    expect_true(CUtil::parseKey(SDLK_9) == 9, "parseKey should parse a supported digit key");
    expect_true(CUtil::parseKey(SDLK_F1) == -1, "parseKey should reject unsupported keys");
}

void test_near_coords_helpers() {
    auto neighbors = near_coords(Coords(4, 5, 0));
    expect_true(neighbors.size() == 4, "near_coords should return four cardinal neighbors");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(5, 5, 0)) != neighbors.end(),
                "near_coords should include east neighbor");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(3, 5, 0)) != neighbors.end(),
                "near_coords should include west neighbor");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(4, 6, 0)) != neighbors.end(),
                "near_coords should include south neighbor");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(4, 4, 0)) != neighbors.end(),
                "near_coords should include north neighbor");

    auto neighbors_with_self = near_coords_with(Coords(4, 5, 0));
    expect_true(neighbors_with_self.size() == 5, "near_coords_with should include origin and four neighbors");
    expect_true(std::find(neighbors_with_self.begin(), neighbors_with_self.end(), Coords(4, 5, 0)) !=
                    neighbors_with_self.end(),
                "near_coords_with should include origin");
}

void test_pathfinder_find_path_without_obstacles() {
    auto can_step = [](const Coords &coords) {
        return coords.x >= 0 && coords.x <= 2 && coords.y >= 0 && coords.y <= 2 && coords.z == 0;
    };
    auto no_waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(path.size() == 2, "findPath should include each next step until goal");
    expect_true(path.front() == Coords(1, 0, 0), "findPath should return first move toward goal");
    expect_true(path.back() == Coords(2, 0, 0), "findPath should end on goal");

    auto next_step = CPathFinder::findNextStep(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(next_step->get() == Coords(1, 0, 0), "findNextStep should return the first optimal neighbor");
}

void test_pathfinder_waypoint_and_blocked_goal() {
    auto can_step = [](const Coords &coords) { return coords == Coords(0, 0, 0); };
    auto no_waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(path.size() == 1, "findPath should return only start when goal is unreachable");
    expect_true(path.front() == Coords(0, 0, 0), "findPath should remain on start if no route exists");
}

void test_pathfinder_returns_start_when_passable_goal_has_no_route() {
    auto can_step = [](const Coords &coords) { return coords == Coords(0, 0, 0) || coords == Coords(2, 0, 0); };
    auto no_waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };
    auto no_neighbors = [](const Coords &) { return std::vector<Coords>{}; };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint, no_neighbors);
    expect_true(path.size() == 1 && path.front() == Coords(0, 0, 0),
                "findPath should remain on start when a passable goal cannot be reached");
}

void test_pathfinder_caches_passability_checks() {
    std::map<Coords, int> calls;
    auto can_step = [&calls](const Coords &coords) {
        calls[coords]++;
        return coords == Coords(0, 0, 0) || coords == Coords(1, 0, 0) || coords == Coords(2, 0, 0);
    };
    auto no_waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };
    auto duplicate_neighbors = [](const Coords &coords) {
        if (coords == Coords(0, 0, 0)) {
            return std::vector<Coords>{Coords(1, 0, 0), Coords(1, 0, 0)};
        }
        if (coords == Coords(1, 0, 0)) {
            return std::vector<Coords>{Coords(2, 0, 0)};
        }
        return std::vector<Coords>{};
    };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint, duplicate_neighbors);
    expect_true(path.size() == 2, "findPath should follow the duplicate-neighbor route");
    expect_true(path.front() == Coords(1, 0, 0), "findPath should still include the first route step");
    expect_true(path.back() == Coords(2, 0, 0), "findPath should still end on the goal");
    expect_true(calls[Coords(1, 0, 0)] == 1, "findPath should cache repeated passability checks");
}

void test_pathfinder_waypoint_override() {
    auto can_step = [](const Coords &coords) {
        return coords.y == 0 && coords.x >= 0 && coords.x <= 2 && coords.z == 0;
    };
    auto forced_waypoint = [](const Coords &coords) -> std::optional<Coords> {
        if (coords == Coords(0, 0, 0)) {
            return Coords(2, 0, 0);
        }
        return std::nullopt;
    };
    auto next_step = CPathFinder::findNextStep(Coords(0, 0, 0), Coords(2, 0, 0), can_step, forced_waypoint);
    expect_true(next_step->get() == Coords(2, 0, 0), "findNextStep should allow waypoint override when available");
}

void test_pathfinder_crosses_levels_through_explicit_waypoint() {
    auto can_step = [](const Coords &coords) {
        return coords == Coords(0, 0, 0) || coords == Coords(1, 0, 0) || coords == Coords(1, 0, 1) ||
               coords == Coords(2, 0, 1);
    };
    auto stair_waypoint = [](const Coords &coords) -> std::optional<Coords> {
        if (coords == Coords(1, 0, 0)) {
            return Coords(1, 0, 1);
        }
        return std::nullopt;
    };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 1), can_step, stair_waypoint);
    expect_true(path.size() == 3, "cross-level waypoint path should include stair landing and goal");
    expect_true(path[0] == Coords(1, 0, 0), "cross-level path should first move to the connector");
    expect_true(path[1] == Coords(1, 0, 1), "cross-level path should then move to the connector landing");
    expect_true(path[2] == Coords(2, 0, 1), "cross-level path should finish on the target level");
}

int wrap_axis(int value, int bound) {
    int size = bound + 1;
    int normalized = value % size;
    if (normalized < 0) {
        normalized += size;
    }
    return normalized;
}

Coords normalize_toroidal(Coords coords, int x_bound, int y_bound) {
    return Coords(wrap_axis(coords.x, x_bound), wrap_axis(coords.y, y_bound), coords.z);
}

std::vector<Coords> toroidal_neighbors(const Coords &coords, int x_bound, int y_bound) {
    std::set<Coords> unique;
    for (const auto &neighbor : near_coords(coords)) {
        unique.insert(normalize_toroidal(neighbor, x_bound, y_bound));
    }
    return {unique.begin(), unique.end()};
}

double toroidal_distance(const Coords &a, const Coords &b, int x_bound, int y_bound) {
    int width = x_bound + 1;
    int height = y_bound + 1;
    int dx = std::abs(a.x - b.x);
    int dy = std::abs(a.y - b.y);
    dx = std::min(dx, width - dx);
    dy = std::min(dy, height - dy);
    return std::sqrt(dx * dx + dy * dy);
}

void test_toroidal_pathfinder_prefers_wrapped_route() {
    constexpr int x_bound = 25;
    constexpr int y_bound = 25;
    auto can_step = [=](const Coords &coords) {
        Coords normalized = normalize_toroidal(coords, x_bound, y_bound);
        return normalized.z == 0 && normalized.y == 0;
    };
    auto no_waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };
    auto neighbors = [=](const Coords &coords) { return toroidal_neighbors(coords, x_bound, y_bound); };
    auto distance = [=](const Coords &a, const Coords &b) {
        return toroidal_distance(normalize_toroidal(a, x_bound, y_bound), normalize_toroidal(b, x_bound, y_bound),
                                 x_bound, y_bound);
    };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(25, 0, 0), can_step, no_waypoint, neighbors, distance);
    expect_true(path.size() == 1, "Toroidal path should use the wrapped one-step route");
    expect_true(path.front() == Coords(25, 0, 0), "Toroidal path should wrap west-to-east in one move");

    auto next_step =
        CPathFinder::findNextStep(Coords(0, 0, 0), Coords(25, 0, 0), can_step, no_waypoint, neighbors, distance);
    expect_true(next_step->get() == Coords(25, 0, 0), "Toroidal next step should choose the wrapped edge tile");
}

void test_toroidal_pathfinder_wraps_on_both_axes() {
    constexpr int x_bound = 25;
    constexpr int y_bound = 25;
    auto can_step = [=](const Coords &coords) {
        Coords normalized = normalize_toroidal(coords, x_bound, y_bound);
        return normalized.z == 0;
    };
    auto no_waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };
    auto neighbors = [=](const Coords &coords) { return toroidal_neighbors(coords, x_bound, y_bound); };
    auto distance = [=](const Coords &a, const Coords &b) {
        return toroidal_distance(normalize_toroidal(a, x_bound, y_bound), normalize_toroidal(b, x_bound, y_bound),
                                 x_bound, y_bound);
    };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(25, 25, 0), can_step, no_waypoint, neighbors, distance);
    expect_true(path.size() == 2, "Toroidal path should wrap independently on both axes");
    expect_true(path.front() == Coords(0, 25, 0) || path.front() == Coords(25, 0, 0),
                "Toroidal path should take a wrapped step on one axis first");
    expect_true(path.back() == Coords(25, 25, 0), "Toroidal path should end at the wrapped goal coordinate");
}

void test_json_parse_expected_success_and_failure() {
    expect_true(CJsonUtil::preview_json("line\nnext\tend\r") == "line next end ",
                "preview_json should normalize control whitespace");
    expect_true(CJsonUtil::preview_json("") == "<empty>", "preview_json should mark empty source text");

    json ref = {{"ref", "GroundTile"}};
    json ref_with_properties = {{"ref", "GroundTile"}, {"properties", json::object()}};
    json invalid_ref = {{"ref", "GroundTile"}, {"class", "CTile"}, {"properties", json::object()}};
    json type = {{"class", "CTile"}};
    json type_with_properties = {{"class", "CTile"}, {"properties", json::object()}};
    json invalid_type = {{"ref", "GroundTile"}, {"class", "CTile"}, {"properties", json::object()}};
    json not_object = json::array();
    json *null_json = nullptr;

    expect_true(CJsonUtil::isRef(&ref), "single ref objects should be detected as references");
    expect_true(CJsonUtil::isRef(&ref_with_properties), "ref objects may include properties");
    expect_true(!CJsonUtil::isRef(&invalid_ref), "larger ref-like objects should not be accepted as references");
    expect_true(!CJsonUtil::isRef(&not_object), "non-object json should not be accepted as references");
    expect_true(!CJsonUtil::isRef(null_json), "null json should not be accepted as references");

    expect_true(CJsonUtil::isType(&type), "single class objects should be detected as type definitions");
    expect_true(CJsonUtil::isType(&type_with_properties), "type definitions may include properties");
    expect_true(!CJsonUtil::isType(&invalid_type), "larger type-like objects should not be accepted as types");
    expect_true(!CJsonUtil::isType(&not_object), "non-object json should not be accepted as types");
    expect_true(!CJsonUtil::isType(null_json), "null json should not be accepted as types");

    json object_map = {{"floor", ref}, {"wall", type}};
    json invalid_map = {{"floor", 1}};
    expect_true(CJsonUtil::isMap(&object_map), "maps of object configs should be detected as object maps");
    expect_true(!CJsonUtil::isMap(&invalid_map), "maps containing non-object values should be rejected");
    expect_true(!CJsonUtil::isMap(&not_object), "non-object json should not be accepted as maps");
    expect_true(!CJsonUtil::isMap(null_json), "null json should not be accepted as maps");

    auto parsed = CJsonUtil::parse_expected("{\"value\": 3}", "unit-json");
    expect_true(parsed.has_value() && (*parsed)->at("value").get<int>() == 3,
                "parse_expected should return parsed json on success");

    auto failed = CJsonUtil::parse_expected("{", "unit-json-error");
    expect_true(!failed.has_value(), "parse_expected should expose malformed json as an expected error");
    if (!failed) {
        expect_true(failed.error().source == "unit-json-error", "parse_expected error should retain source context");
        expect_true(failed.error().preview == "{", "parse_expected error should retain a compact preview");
    }
    auto duplicate_key = CJsonUtil::parse_expected(R"({"value": 1, "value": 2})", "unit-json-duplicate");
    expect_true(!duplicate_key.has_value(), "parse_expected should reject duplicate object keys");
    expect_true(CJsonUtil::from_string("{", "unit-json-wrapper") == nullptr,
                "from_string should keep the public nullptr behavior on parse failure");
}

void test_json_parse_dump_and_type_helpers() {
    const auto parsed = json::parse(
        R"({"array":["line\nnext",18446744073709551615,1.5,true,false,null],"empty":{},"name":"nouraajd"})");
    expect_true(parsed.is_object(), "parsed JSON document should be an object");
    expect_true(parsed.size() == 3, "object size should count parsed keys");
    expect_true(parsed.count("array") == 1, "count should report existing object keys");
    expect_true(parsed.count("missing") == 0, "count should reject missing object keys");
    expect_true(parsed["array"].is_array(), "parsed array should keep array type");
    expect_true(parsed["array"].size() == 6, "parsed array should keep every entry");
    expect_true(parsed["array"][0].get<std::string>() == "line\nnext", "parsed string should preserve escapes");
    expect_true(parsed["array"][1].get<unsigned long long>() == 18446744073709551615ull,
                "parsed unsigned integer should keep full uint64 range");
    expect_true(parsed["array"][2].get<double>() == 1.5, "parsed floating point value should keep precision");
    expect_true(parsed["array"][3].get<bool>(), "parsed true value should keep boolean type");
    expect_true(!parsed["array"][4].get<bool>(), "parsed false value should keep boolean type");
    expect_true(parsed["array"][5].is_null(), "parsed null should keep null type");
    expect_true(parsed["missing"].is_null(), "missing object lookup should return null value");
    expect_true(parsed["array"][99].is_null(), "missing array lookup should return null value");
    expect_true(parsed.value("name", std::string("fallback")) == "nouraajd",
                "value should return typed object members");
    expect_true(parsed.value("missing", std::string("fallback")) == "fallback",
                "value should use fallback for missing members");
    expect_true(parsed.value("array", std::string("fallback")) == "fallback",
                "value should use fallback for type mismatches");

    json constructed;
    constructed["quote"] = "a\"b\\c\b\f\n\r\t";
    constructed["number"] = -7;
    constructed["unsigned"] = 7u;
    constructed["double"] = 2.25;
    constructed["nan"] = std::numeric_limits<double>::quiet_NaN();
    constructed["items"] = json::array({nullptr, "tail"});
    constructed["items"][4] = "expanded";
    constructed.erase("missing");

    const auto compact = constructed.dump();
    expect_true(compact.find(R"("quote":"a\"b\\c\b\f\n\r\t")") != std::string::npos,
                "compact dump should escape strings");
    expect_true(compact.find(R"("nan":null)") != std::string::npos,
                "compact dump should serialize non-finite numbers as null");
    expect_true(compact.find(R"("items":[null,"tail",null,null,"expanded"])") != std::string::npos,
                "compact dump should serialize expanded arrays");

    const auto pretty = constructed.dump(2);
    expect_true(pretty.find("\n  \"items\": [") != std::string::npos, "pretty dump should indent objects");
    expect_true(pretty.find("\n    \"expanded\"") != std::string::npos, "pretty dump should indent arrays");

    expect_true(json(nullptr).dump() == "null", "null JSON should dump as null");
    expect_true(json("text").size() == 4, "string size should report character count");
    bool missing_key_threw = false;
    try {
        parsed.at("missing");
    } catch (const std::out_of_range &) {
        missing_key_threw = true;
    }
    expect_true(missing_key_threw, "object at() should reject missing keys");

    bool non_array_threw = false;
    try {
        parsed["name"].at(std::size_t{0});
    } catch (const std::out_of_range &) {
        non_array_threw = true;
    }
    expect_true(non_array_threw, "array at() should reject non-array values");
    expect_runtime_error([&]() { parsed["name"].get<int>(); }, "integer get should reject string values");
}

void test_sdl_raii_alias_owns_surface() {
    auto surface = fn::sdl::SurfacePtr(SDL_CreateRGBSurfaceWithFormat(0, 2, 2, 32, SDL_PIXELFORMAT_RGBA32));
    expect_true(surface != nullptr, "SurfacePtr should own SDL surfaces created by SDL");
    if (!surface) {
        return;
    }

    auto color = SDL_MapRGBA(surface->format, 1, 2, 3, 4);
    SDL_FillRect(surface.get(), nullptr, color);
    Uint8 r = 0;
    Uint8 g = 0;
    Uint8 b = 0;
    Uint8 a = 0;
    SDL_GetRGBA(color, surface->format, &r, &g, &b, &a);
    expect_true(r == 1 && g == 2 && b == 3 && a == 4, "SurfacePtr should provide raw non-owning access via get");
}

void test_tag_round_trip_and_ordering() {
    for (const auto &tag : CTags::all()) {
        auto text = CTags::toString(tag);
        expect_true(CTags::fromString(text) == tag, "Tag conversion should round-trip between enum and string");
    }

    CTags tags;
    tags.insert(CTag::Quest);
    tags.insert(CTag::Buff);
    tags.insert(CTag::Quest);
    expect_true(tags.contains(CTag::Buff), "CTags should report contained tags");
    expect_true(tags.contains(CTag::Quest), "CTags should deduplicate repeated inserts");
    expect_true(tags.size() == 2, "CTags should keep unique enum values only");

    const auto names = tags.toStrings();
    expect_true(names.size() == 2 && names[0] == "buff" && names[1] == "quest",
                "CTags should emit canonical strings in deterministic order");
}

void test_unknown_tag_rejection() {
    bool threw = false;
    try {
        (void)CTags::fromString("unknown_tag");
    } catch (const std::invalid_argument &) {
        threw = true;
    }
    expect_true(threw, "Unknown tag strings should be rejected explicitly");
}

void test_tag_mutation_iteration_and_range_helpers() {
    CTags tags{CTag::Quest, CTag::Buff};
    tags.erase(CTag::Quest);
    expect_true(!tags.contains(CTag::Quest), "CTags::erase should remove an existing tag");
    expect_true(!tags.empty(), "CTags should remain non-empty when another tag is present");
    expect_true(tags.values().count(CTag::Buff) == 1, "CTags::values should expose contained tags");
    expect_true(tags.begin() != tags.end(), "CTags iterators should span contained tags");
    expect_true(tags == CTags{CTag::Buff}, "CTags equality should compare stored tag values");

    bool invalid_enum_threw = false;
    try {
        (void)CTags::toString(static_cast<CTag>(999));
    } catch (const std::invalid_argument &) {
        invalid_enum_threw = true;
    }
    expect_true(invalid_enum_threw, "Unknown tag enum values should be rejected explicitly");

    auto tagged = std::make_shared<TagProbe>();
    tagged->tags.insert(CTag::Heal);
    std::vector<std::shared_ptr<TagProbe>> probes{tagged, std::make_shared<TagProbe>()};
    expect_true(CTags::isTagPresent(probes, CTag::Heal), "isTagPresent should find a matching tag");
    expect_true(!CTags::isTagPresent(probes, CTag::Wand), "isTagPresent should reject absent tags");
}

void test_property_setters_emit_change_signals() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto object = std::make_shared<CGameObject>();
    auto probe = std::make_shared<PropertyChangeProbe>();

    object->connect("propertyChanged", probe, "onPropertyChanged");
    object->connect("labelChanged", probe, "onLabelChanged");
    object->connect("threatChanged", probe, "onThreatChanged");

    object->setStringProperty("label", "Alert");
    object->setNumericProperty("threat", 7);

    drain_event_loop();

    expect_true((probe->changed_properties == std::vector<std::string>{"label", "threat"}),
                "propertyChanged should include string and numeric property names");
    expect_true(probe->changed_property_batches.empty(), "ordinary property setters should not emit batch signals");
    expect_true(probe->label_changed_calls == 1, "setStringProperty should emit the property-specific signal");
    expect_true(probe->threat_changed_calls == 1, "setNumericProperty should emit the property-specific signal");
}

template <typename T, typename ValueType> bool has_primitive_value_type() {
    auto value_type = CTypes::primitiveValueType<T>();
    return CTypes::isPrimitiveType<T>() && value_type.has_value() &&
           value_type.value() == std::type_index(typeid(ValueType));
}

void test_reviewed_value_wrappers_have_explicit_primitive_metadata() {
    expect_true(has_primitive_value_type<CListString, std::set<std::string>>(),
                "CListString should be an explicitly registered string-set primitive wrapper");
    expect_true(has_primitive_value_type<CListInt, std::set<int>>(),
                "CListInt should be an explicitly registered integer-set primitive wrapper");
    expect_true(has_primitive_value_type<CMapStringString, std::map<std::string, std::string>>(),
                "CMapStringString should be an explicitly registered string-string map primitive wrapper");
    expect_true(has_primitive_value_type<CMapStringInt, std::map<std::string, int>>(),
                "CMapStringInt should be an explicitly registered string-integer map primitive wrapper");
    expect_true(has_primitive_value_type<CMapIntString, std::map<int, std::string>>(),
                "CMapIntString should be an explicitly registered integer-string map primitive wrapper");
    expect_true(has_primitive_value_type<CMapIntInt, std::map<int, int>>(),
                "CMapIntInt should be an explicitly registered integer-integer map primitive wrapper");

    expect_true(CTypes::primitiveTypes()->size() == 6, "only reviewed value wrappers should be primitive types");
    expect_true(!CTypes::isPrimitiveType<CScript>(), "single-property CScript should not be primitive by shape");
    expect_true(!CTypes::primitiveValueType<CScript>().has_value(), "CScript should not have primitive value metadata");
    expect_true(!CTypes::isPrimitiveType<CStats>(), "multi-property value-like objects should not be primitive");
}

void test_nested_primitive_wrappers_serialize_direct_values_and_round_trip() {
    CTypes::register_type_metadata<PrimitiveSerializationHolder, CGameObject>();

    auto game = std::make_shared<CGame>();
    game->getObjectHandler()->registerType(PrimitiveSerializationHolder::static_meta()->name(),
                                           []() { return std::make_shared<PrimitiveSerializationHolder>(); });
    game->getObjectHandler()->registerType(CListString::static_meta()->name(),
                                           []() { return std::make_shared<CListString>(); });
    game->getObjectHandler()->registerType(CListInt::static_meta()->name(),
                                           []() { return std::make_shared<CListInt>(); });
    game->getObjectHandler()->registerType(CMapStringString::static_meta()->name(),
                                           []() { return std::make_shared<CMapStringString>(); });
    game->getObjectHandler()->registerType(CMapStringInt::static_meta()->name(),
                                           []() { return std::make_shared<CMapStringInt>(); });
    game->getObjectHandler()->registerType(CMapIntString::static_meta()->name(),
                                           []() { return std::make_shared<CMapIntString>(); });
    game->getObjectHandler()->registerType(CMapIntInt::static_meta()->name(),
                                           []() { return std::make_shared<CMapIntInt>(); });

    auto list_values = std::make_shared<CListString>();
    list_values->setValues({"north", "south"});
    auto map_values = std::make_shared<CMapStringString>();
    map_values->setValues({{"confirm", "enter"}, {"inventory", "i"}});
    auto int_list_values = std::make_shared<CListInt>();
    int_list_values->setValues({2, 3, 5});
    auto int_string_map_values = std::make_shared<CMapIntString>();
    int_string_map_values->setValues({{7, "seven"}, {11, "eleven"}});
    auto int_int_map_values = std::make_shared<CMapIntInt>();
    int_int_map_values->setValues({{13, 169}, {17, 289}});

    auto holder = std::make_shared<PrimitiveSerializationHolder>();
    holder->setGame(game);
    holder->setListValues(list_values);
    holder->setMapValues(map_values);

    auto serialized = CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(holder);
    auto properties = &(*serialized)["properties"];
    auto serialized_list =
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(list_values);

    expect_true((*properties)["listValues"].is_array(),
                "nested CListString properties should serialize as their direct JSON array values");
    expect_true((*properties)["listValues"].size() == 2,
                "nested CListString direct values should preserve all entries");
    expect_true((*properties)["mapValues"].is_object() && !CJsonUtil::isObject(&(*properties)["mapValues"]),
                "nested CMapStringString properties should serialize as their direct JSON object values");
    expect_true((*properties)["mapValues"]["inventory"].get<std::string>() == "i",
                "nested CMapStringString direct values should preserve key-value entries");
    expect_true((*serialized_list)["class"].get<std::string>() == CListString::static_meta()->name() &&
                    (*serialized_list)["properties"].contains("values"),
                "top-level primitive wrappers should keep their object identity");

    auto round_trip = std::dynamic_pointer_cast<PrimitiveSerializationHolder>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game, serialized));

    expect_true(round_trip && round_trip->getListValues(),
                "direct CListString JSON values should deserialize back into the primitive wrapper property");
    expect_true(round_trip && round_trip->getMapValues(),
                "direct CMapStringString JSON values should deserialize back into the primitive wrapper property");
    expect_true(round_trip->getListValues()->getValues() == std::set<std::string>({"north", "south"}),
                "CListString primitive wrapper values should round-trip through direct nested JSON");
    expect_true(round_trip->getMapValues()->getValues() ==
                    std::map<std::string, std::string>({{"confirm", "enter"}, {"inventory", "i"}}),
                "CMapStringString primitive wrapper values should round-trip through direct nested JSON");

    auto reserved_key_map_values = std::make_shared<CMapStringString>();
    reserved_key_map_values->setValues({{"ref", "north"}});
    holder->setMapValues(reserved_key_map_values);

    auto serialized_reserved_map =
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(holder);
    auto reserved_map_properties = &(*serialized_reserved_map)["properties"];

    expect_true(CJsonUtil::isObject(&(*reserved_map_properties)["mapValues"]),
                "single-entry flattened maps can have object-config-shaped keys");

    auto reserved_map_round_trip = std::dynamic_pointer_cast<PrimitiveSerializationHolder>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game,
                                                                                              serialized_reserved_map));

    expect_true(reserved_map_round_trip && reserved_map_round_trip->getMapValues() &&
                    reserved_map_round_trip->getMapValues()->getValues() ==
                        std::map<std::string, std::string>({{"ref", "north"}}),
                "CMapStringString flattened values named ref should deserialize as primitive map entries");

    auto panel_keys_config = std::make_shared<json>();
    (*panel_keys_config)["class"] = CMapStringString::static_meta()->name();
    (*panel_keys_config)["properties"]["values"] = {{"i", "inventoryPanel"}, {"j", "questPanel"}};
    game->getObjectHandler()->registerConfig("panelKeys", panel_keys_config);

    auto holder_with_ref_config = std::make_shared<json>();
    (*holder_with_ref_config)["class"] = PrimitiveSerializationHolder::static_meta()->name();
    (*holder_with_ref_config)["properties"]["mapValues"]["ref"] = "panelKeys";

    auto ref_round_trip = std::dynamic_pointer_cast<PrimitiveSerializationHolder>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game,
                                                                                              holder_with_ref_config));

    expect_true(ref_round_trip && ref_round_trip->getMapValues() &&
                    ref_round_trip->getMapValues()->getValues() ==
                        std::map<std::string, std::string>({{"i", "inventoryPanel"}, {"j", "questPanel"}}),
                "CMapStringString object refs should resolve to the referenced primitive wrapper");

    auto serialized_int_list =
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(int_list_values);
    auto int_list_round_trip = std::dynamic_pointer_cast<CListInt>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game,
                                                                                              serialized_int_list));
    expect_true(int_list_round_trip && int_list_round_trip->getValues() == std::set<int>({2, 3, 5}),
                "CListInt should round-trip integer sets through primitive JSON arrays");

    auto serialized_int_string_map =
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(int_string_map_values);
    auto int_string_map_round_trip = std::dynamic_pointer_cast<CMapIntString>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
            game, serialized_int_string_map));
    expect_true(int_string_map_round_trip && int_string_map_round_trip->getValues() ==
                                                 std::map<int, std::string>({{7, "seven"}, {11, "eleven"}}),
                "CMapIntString should round-trip integer keys through string-keyed JSON objects");

    auto serialized_int_int_map =
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(int_int_map_values);
    auto int_int_map_round_trip = std::dynamic_pointer_cast<CMapIntInt>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game,
                                                                                              serialized_int_int_map));
    expect_true(int_int_map_round_trip &&
                    int_int_map_round_trip->getValues() == std::map<int, int>({{13, 169}, {17, 289}}),
                "CMapIntInt should round-trip integer keys and values through string-keyed JSON objects");

    auto string_int_map_values = std::make_shared<CMapStringInt>();
    string_int_map_values->setValues({{"one", 1}, {"two", 2}});
    auto serialized_string_int_map =
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(string_int_map_values);
    auto string_int_map_round_trip = std::dynamic_pointer_cast<CMapStringInt>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
            game, serialized_string_int_map));
    expect_true(string_int_map_round_trip &&
                    string_int_map_round_trip->getValues() == std::map<std::string, int>({{"one", 1}, {"two", 2}}),
                "CMapStringInt should round-trip string keys and integer values");

    auto invalid_int_key_config = std::make_shared<json>();
    (*invalid_int_key_config)["class"] = CMapIntString::static_meta()->name();
    (*invalid_int_key_config)["properties"]["values"] = {{"", "empty"}, {"bad", "ignored"}, {"23", "kept"}};
    auto invalid_int_key_round_trip = std::dynamic_pointer_cast<CMapIntString>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game,
                                                                                              invalid_int_key_config));
    expect_true(invalid_int_key_round_trip &&
                    invalid_int_key_round_trip->getValues() == std::map<int, std::string>({{23, "kept"}}),
                "integer-key maps should skip empty and unparsable JSON object keys");
}

void test_nested_property_notification_batches_emit_one_deterministic_signal() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto object = std::make_shared<CGameObject>();
    auto probe = std::make_shared<PropertyChangeProbe>();

    object->connect("propertyChanged", probe, "onPropertyChanged");
    object->connect("propertiesChanged", probe, "onPropertiesChanged");
    object->connect("labelChanged", probe, "onLabelChanged");
    object->connect("threatChanged", probe, "onThreatChanged");

    {
        CGameObject::PropertyNotificationBatch outerBatch(*object);
        object->setStringProperty("label", "Alert");
        {
            CGameObject::PropertyNotificationBatch innerBatch(*object);
            object->setNumericProperty("threat", 7);
            object->setStringProperty("label", "Updated");
        }
    }

    drain_event_loop();

    const std::vector<std::set<std::string>> expected_batches{{"label", "threat"}};
    expect_true(probe->changed_properties.empty(), "batched property changes should suppress per-field notifications");
    expect_true(probe->changed_property_batches == expected_batches,
                "nested property batches should emit one sorted unique-name batch");
    expect_true(probe->label_changed_calls == 0, "batched string changes should suppress property-specific signals");
    expect_true(probe->threat_changed_calls == 0, "batched numeric changes should suppress property-specific signals");
}

void test_object_deserialization_batches_property_notifications() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto game = std::make_shared<CGame>();
    auto object = std::make_shared<CGameObject>();
    auto probe = std::make_shared<PropertyChangeProbe>();

    object->connect("propertyChanged", probe, "onPropertyChanged");
    object->connect("propertiesChanged", probe, "onPropertiesChanged");
    object->connect("labelChanged", probe, "onLabelChanged");
    object->connect("threatChanged", probe, "onThreatChanged");
    game->getObjectHandler()->registerType("ObservedObject", [object]() { return object; });

    auto config = std::make_shared<json>();
    (*config)["class"] = "ObservedObject";
    (*config)["properties"]["description"] = "deserialized";
    (*config)["properties"]["label"] = "Alert";
    (*config)["properties"]["threat"] = 7;

    auto deserialized =
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game, config);
    drain_event_loop();

    const std::vector<std::set<std::string>> expected_batches{{"description", "label", "threat"}};
    expect_true(deserialized == object, "test setup should deserialize the pre-connected observed object");
    expect_true(probe->changed_properties.empty(),
                "deserialization should not emit one propertyChanged signal per configured field");
    expect_true(probe->changed_property_batches == expected_batches,
                "deserialization should emit one consolidated property batch with all changed fields");
    expect_true(probe->label_changed_calls == 0, "deserialization batches should suppress field-specific signals");
    expect_true(probe->threat_changed_calls == 0, "deserialization batches should suppress dynamic field signals");
}

void test_object_clone_batches_property_notifications() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto game = std::make_shared<CGame>();
    auto source = std::make_shared<CGameObject>();
    source->setGame(game);
    source->setType("ObservedCloneObject");
    source->setStringProperty("description", "source");
    source->setStringProperty("label", "Alert");
    source->setNumericProperty("threat", 7);

    auto clone_target = std::make_shared<CGameObject>();
    auto probe = std::make_shared<PropertyChangeProbe>();
    clone_target->connect("propertyChanged", probe, "onPropertyChanged");
    clone_target->connect("propertiesChanged", probe, "onPropertiesChanged");
    clone_target->connect("labelChanged", probe, "onLabelChanged");
    clone_target->connect("threatChanged", probe, "onThreatChanged");
    game->getObjectHandler()->registerType("ObservedCloneObject", [clone_target]() { return clone_target; });

    auto clone = source->clone<CGameObject>();
    drain_event_loop();

    expect_true(clone == clone_target, "clone should use the registered pre-connected clone target");
    expect_true(probe->changed_properties.empty(), "clone should not emit one propertyChanged signal per cloned field");
    expect_true(probe->changed_property_batches.size() == 1,
                "clone should emit one consolidated property batch through deserialization");
    expect_true(probe->changed_property_batches.front().contains("description") &&
                    probe->changed_property_batches.front().contains("label") &&
                    probe->changed_property_batches.front().contains("threat"),
                "clone property batch should include all cloned fields changed by the test");
    expect_true(probe->label_changed_calls == 0, "clone batches should suppress field-specific signals");
    expect_true(probe->threat_changed_calls == 0, "clone batches should suppress dynamic field signals");
}

void test_game_context_owns_distinct_gui_handlers_per_game() {
    auto first_game = std::make_shared<CGame>();
    auto second_game = std::make_shared<CGame>();

    auto first_context_handler = first_game->getContext()->getGuiHandler();
    auto first_game_handler = first_game->getGuiHandler();
    auto second_game_handler = second_game->getGuiHandler();

    expect_true(first_context_handler == first_game_handler,
                "CGame::getGuiHandler should return the handler owned by CGameContext");
    expect_true(first_game_handler != second_game_handler,
                "separate CGame instances should receive distinct GUI handlers");
}

void test_game_context_rejects_services_without_owner_game() {
    auto context = std::make_shared<CGameContext>(std::shared_ptr<CGame>());

    expect_runtime_error([&]() { context->getGuiHandler(); },
                         "CGuiHandler creation should require an active owning game");
    expect_runtime_error([&]() { context->getRngHandler(); },
                         "CRngHandler creation should require an active owning game");
}

void test_game_context_transition_generation_helpers_and_shutdown() {
    auto game = std::make_shared<CGame>();
    auto context = game->getContext();
    expect_true(context->isActive(), "new game context should start active");

    auto initial_generation = context->getTransitionGeneration();
    auto captured_generation = context->captureTransitionGeneration();
    expect_true(captured_generation == initial_generation,
                "capturing transition generation should return the current generation");
    expect_true(context->isTransitionGenerationCurrent(captured_generation),
                "freshly captured transition generation should be current");

    auto advanced_generation = context->advanceTransitionGeneration();
    expect_true(advanced_generation == initial_generation + 1,
                "advancing transition generation should increment monotonically");
    expect_true(context->getTransitionGeneration() == advanced_generation,
                "reading transition generation should return the advanced value");
    expect_true(!context->isTransitionGenerationCurrent(captured_generation),
                "captured transition generation should become stale after an advance");

    auto shutdown_generation = context->captureTransitionGeneration();
    game.reset();
    expect_true(!context->isActive(), "destroying the owning game should mark the context inactive");
    expect_true(context->getTransitionGeneration() == shutdown_generation + 1,
                "destroying the owning game should advance transition generation");
    expect_true(!context->isTransitionGenerationCurrent(shutdown_generation),
                "shutdown should make previously captured transition generation stale");
}

void test_playtest_trace_records_and_helper_payloads() {
    CPlaytestTrace::configure(false);
    CPlaytestTrace::record("ignored");
    expect_true(CPlaytestTrace::records().empty(), "disabled playtest trace should ignore records");

    CPlaytestTrace::configure(true, "", 1);
    CPlaytestTrace::recordJson("trace_payload", R"({"value": 7})");
    CPlaytestTrace::recordJson("trace_non_object_payload", R"([1, 2])");
    CPlaytestTrace::recordJson("trace_after_truncation", "");

    auto records = CPlaytestTrace::records();
    expect_true(records.size() == 2, "trace should retain one record plus one truncation marker");
    auto first = json::parse(records.front());
    auto second = json::parse(records.back());
    expect_true(first["event"].get<std::string>() == "trace_payload" && first["value"].get<int>() == 7,
                "recordJson should preserve object payload fields");
    expect_true(second["event"].get<std::string>() == "trace_truncated" && second["truncated"].get<bool>(),
                "trace should add a single truncation marker after maxRecords");

    auto drained = CPlaytestTrace::drain();
    expect_true(drained.size() == 2 && CPlaytestTrace::records().empty(),
                "drain should return and clear buffered trace records");

    CPlaytestTrace::configure(true);
    CPlaytestTrace::clear();
    expect_true(CPlaytestTrace::records().empty(), "clear should reset trace records");

    auto object = std::make_shared<CGameObject>();
    object->setName("traceObject");
    object->setType("CGameObject");
    auto ref = CPlaytestTrace::objectRef(object);
    expect_true(ref["name"].get<std::string>() == "traceObject" && ref["type"].get<std::string>() == "CGameObject",
                "objectRef should serialize stable object identity");

    auto creature = std::make_shared<CCreature>();
    creature->setName("traceCreature");
    auto creature_ref = CPlaytestTrace::objectRef(creature);
    expect_true(!creature_ref["isPlayer"].get<bool>(), "creature trace refs should include player classification");
    expect_true(CPlaytestTrace::objectRefs({creature}).size() == 1, "objectRefs should serialize creature lists");

    auto item = std::make_shared<CItem>();
    item->setName("traceItem");
    expect_true(CPlaytestTrace::itemRefs({item}).size() == 1, "itemRefs should serialize item sets");
    expect_true(CPlaytestTrace::objectRef(nullptr).is_null(), "objectRef should preserve null objects");

    json fields = json::object();
    CPlaytestTrace::addMapContext(fields, nullptr);
    expect_true(fields.empty(), "addMapContext should ignore null maps");

    auto map = std::make_shared<CMap>();
    map->setName("traceMapObject");
    map->setTurn(42);
    CPlaytestTrace::addMapContext(fields, map);
    expect_true(fields["map"].get<std::string>() == "traceMapObject" && fields["turn"].get<int>() == 42,
                "addMapContext should serialize map identity and turn");

    CPlaytestTrace::configure(false);
}

void test_delayed_future_handlers_run_through_event_loop() {
    auto loop = vstd::event_loop<>::instance();
    const int previous_fps = loop->getFps();
    loop->setFps(1000);

    std::atomic<int> later_calls = 0;
    std::atomic<int> async_calls = 0;
    vstd::call_delayed_later(1, [&]() { later_calls.fetch_add(1); });
    vstd::call_delayed_async(1, [&]() { async_calls.fetch_add(1); });

    for (int i = 0; i < 200 && (later_calls.load() == 0 || async_calls.load() == 0); ++i) {
        SDL_Delay(2);
        loop->run();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    loop->setFps(previous_fps);
    expect_true(later_calls.load() == 1, "call_delayed_later should run a delayed event-loop callback");
    expect_true(async_calls.load() == 1, "call_delayed_async should run a delayed async callback");
}

void test_script_rejects_executable_expressions() {
    expect_true(CScript::isSafeAccessorExpression("self.getGui().getGame().getMap().getPlayer()"),
                "safe accessor validation should accept existing panel refresh target expressions");
    expect_true(CScript::isSafeAccessorExpression(" self.getParent().getMarket() "),
                "safe accessor validation should trim existing accessor expressions");
    expect_true(!CScript::isSafeAccessorExpression("(__import__('os').system('id > /tmp/pwned'), self)[1]"),
                "safe accessor validation should reject Python side-effect expressions");
    expect_true(!CScript::isSafeAccessorExpression("self.getGui().getGame().getMap().getPlayer().__class__"),
                "safe accessor validation should reject attribute access without a zero-argument call");
    expect_true(!CScript::isSafeAccessorExpression("self.getGui(__import__('os'))"),
                "safe accessor validation should reject method arguments");
    expect_true(!CScript::isSafeAccessorExpression("game.getMap()"),
                "safe accessor validation should only allow expressions rooted at self");
}

std::shared_ptr<json> make_save_snapshot(std::string map_name = "test") {
    auto snapshot = std::make_shared<json>();
    (*snapshot)["class"] = "CMap";
    (*snapshot)["properties"] = json::object();
    (*snapshot)["properties"]["mapName"] = std::move(map_name);
    return snapshot;
}

bool save_snapshot_has_map(const std::shared_ptr<json> &snapshot, const std::string &map_name) {
    return snapshot && snapshot->is_object() && snapshot->contains("class") &&
           (*snapshot)["class"].get<std::string>() == "CMap" && snapshot->contains("properties") &&
           (*snapshot)["properties"].is_object() && (*snapshot)["properties"].contains("mapName") &&
           (*snapshot)["properties"]["mapName"].get<std::string>() == map_name;
}

void test_save_format_codec_validation() {
    auto snapshot = make_save_snapshot();
    auto envelope = CSaveFormat::buildEnvelope(snapshot, "test");
    expect_true(envelope.has_value(), "save format should build a valid envelope");
    expect_true((*envelope)->at("format").get<std::string>() == CSaveFormat::FORMAT,
                "save envelope should use the canonical format marker");
    expect_true((*envelope)->at("schemaVersion").get<int>() == CSaveFormat::SCHEMA_VERSION,
                "save envelope should use the canonical schema version");

    auto decoded = CSaveFormat::decodeDocument(*envelope);
    expect_true(
        decoded.has_value() && decoded->mapName == "test" && decoded->encoding == CSaveFormat::Encoding::Versioned &&
            decoded->snapshot.get() == &(*envelope)->at("snapshot") && save_snapshot_has_map(decoded->snapshot, "test"),
        "save migration registry should no-op current schema envelopes");

    const auto legacy_before = snapshot->dump();
    auto legacy = CSaveFormat::decodeDocument(snapshot);
    expect_true(legacy.has_value() && legacy->mapName == "test" && legacy->encoding == CSaveFormat::Encoding::Legacy &&
                    save_snapshot_has_map(legacy->snapshot, "test") && snapshot->dump() == legacy_before,
                "save migration registry should migrate legacy snapshots without mutating the source");
    expect_true(!CSaveFormat::decodeDocument(make_save_snapshot("../test")).has_value(),
                "save format should reject legacy snapshots with invalid map names");

    auto wrong_format = std::make_shared<json>(**envelope);
    (*wrong_format)["format"] = "other";
    expect_true(!CSaveFormat::decodeDocument(wrong_format).has_value(), "save format should reject unknown formats");

    auto missing_schema = std::make_shared<json>(**envelope);
    missing_schema->erase("schemaVersion");
    expect_true(!CSaveFormat::decodeDocument(missing_schema).has_value(),
                "save format should reject envelopes without schemaVersion");

    auto old_schema = std::make_shared<json>(**envelope);
    (*old_schema)["schemaVersion"] = 0;
    const auto old_schema_before = old_schema->dump();
    auto old_schema_decoded = CSaveFormat::decodeDocument(old_schema);
    expect_true(old_schema_decoded.has_value() && old_schema_decoded->mapName == "test" &&
                    old_schema_decoded->encoding == CSaveFormat::Encoding::Versioned &&
                    save_snapshot_has_map(old_schema_decoded->snapshot, "test") &&
                    old_schema->dump() == old_schema_before,
                "save migration registry should migrate old schema envelopes without mutating the source");

    auto future_schema = std::make_shared<json>(**envelope);
    (*future_schema)["schemaVersion"] = CSaveFormat::SCHEMA_VERSION + 1;
    const auto future_schema_before = future_schema->dump();
    expect_true(!CSaveFormat::decodeDocument(future_schema).has_value() &&
                    future_schema->dump() == future_schema_before,
                "save migration registry should reject future schema versions without mutating the source");

    auto invalid_map = std::make_shared<json>(**envelope);
    (*invalid_map)["mapName"] = "../test";
    expect_true(!CSaveFormat::decodeDocument(invalid_map).has_value(), "save format should reject invalid map names");

    auto missing_snapshot = std::make_shared<json>(**envelope);
    missing_snapshot->erase("snapshot");
    expect_true(!CSaveFormat::decodeDocument(missing_snapshot).has_value(),
                "save format should reject envelopes without snapshots");

    auto wrong_class = std::make_shared<json>(**envelope);
    (*wrong_class)["snapshot"]["class"] = "CCreature";
    expect_true(!CSaveFormat::decodeDocument(wrong_class).has_value(), "save format should reject non-map snapshots");

    auto mismatched_map = std::make_shared<json>(**envelope);
    (*mismatched_map)["snapshot"]["properties"]["mapName"] = "empty";
    expect_true(!CSaveFormat::decodeDocument(mismatched_map).has_value(),
                "save format should reject envelope/snapshot map mismatches");

    expect_true(CSaveFormat::isValidSlotName("slot-1_ok.json"), "save format should allow safe slot names");
    expect_true(!CSaveFormat::isValidSlotName(".hidden"), "save format should reject hidden slot names");
    expect_true(CSaveFormat::primarySlotFromFilename("slot.json") == std::optional<std::string>("slot"),
                "save format should extract primary slot names");
    expect_true(CSaveFormat::backupSlotFromFilename("slot.json.bak") == std::optional<std::string>("slot"),
                "save format should extract backup slot names");
    expect_true(!CSaveFormat::backupSlotFromFilename("slot.txt.bak").has_value(),
                "save format should reject backups without json primaries");
    expect_true(!CSaveFormat::backupSlotFromFilename(".hidden.json.bak").has_value(),
                "save format should reject hidden backup slot names");

    expect_true(!CSaveFormat::buildEnvelope(std::make_shared<json>(json::object()), "test").has_value(),
                "save format should reject envelopes built from non-map snapshots");
    expect_true(!CSaveFormat::buildEnvelope(snapshot, "other").has_value(),
                "save format should reject envelopes when snapshot and active map names differ");
    expect_true(!CSaveFormat::buildEnvelope(make_save_snapshot("../test"), "../test").has_value(),
                "save format should reject envelopes with invalid map names");
}

void test_serialization_collection_and_error_helpers() {
    auto game = std::make_shared<CGame>();
    auto object = std::make_shared<CGameObject>();
    object->setName("serializedObject");
    object->setType("CGameObject");

    CSerialization::setProperty(nullptr, "ignored", std::make_shared<json>(true));
    CSerialization::setProperty(object, "type", std::make_shared<json>(42));
    expect_true(object->getType() == "42", "numeric JSON should coerce into string-backed properties");
    CSerialization::setProperty(object, "dynamicJsonFromString",
                                std::make_shared<json>(std::string(R"({"value": true})")));
    CSerialization::setProperty(object, "dynamicMapFromString",
                                std::make_shared<json>(std::string(R"({"entry": {"class": "CGameObject"}})")));
    CSerialization::setProperty(object, "dynamicJson", std::make_shared<json>(json::parse(R"({"value": true})")));

    std::set<std::shared_ptr<CGameObject>> object_set{object};
    auto serialized_set =
        CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::serialize(object_set);
    expect_true(serialized_set->is_array() && serialized_set->size() == 1,
                "set serializer should encode game objects as a JSON array");

    auto empty_array = std::make_shared<json>(json::array());
    auto deserialized_set =
        CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::deserialize(game,
                                                                                                        empty_array);
    expect_true(deserialized_set.empty(), "set deserializer should accept empty arrays");

    std::map<std::string, std::shared_ptr<CGameObject>> object_map{{"entry", object}};
    auto serialized_map =
        CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>>::serialize(
            object_map);
    expect_true(serialized_map->is_object() && serialized_map->contains("entry"),
                "map serializer should encode game objects by key");

    auto empty_object = std::make_shared<json>(json::object());
    auto deserialized_map =
        CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(
            game, empty_object);
    expect_true(deserialized_map.empty(), "map deserializer should accept empty objects");

    expect_true(CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
                    nullptr, std::make_shared<json>(json::object())) == nullptr,
                "non-strict object deserialization should fail closed without a game");

    expect_runtime_error(
        [&]() {
            CSerialization::StrictScope strict;
            CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
                nullptr, std::make_shared<json>(json::object()));
        },
        "strict object deserialization should reject a missing game");

    auto unresolved_ref = std::make_shared<json>(json::object());
    (*unresolved_ref)["ref"] = "missingObjectType";
    expect_runtime_error(
        [&]() {
            CSerialization::StrictScope strict;
            CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game, unresolved_ref);
        },
        "strict object deserialization should report unresolved references");

    auto invalid_array = std::make_shared<json>(json::array({1}));
    auto non_strict_skipped =
        CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::deserialize(game,
                                                                                                        invalid_array);
    expect_true(non_strict_skipped.empty(), "non-strict array deserialization should skip malformed entries");

    expect_runtime_error(
        [&]() {
            CSerialization::StrictScope strict;
            CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::deserialize(
                game, invalid_array);
        },
        "strict array deserialization should reject malformed entries");

    auto invalid_map = std::make_shared<json>(json::object());
    (*invalid_map)["bad"] = 1;
    expect_runtime_error(
        [&]() {
            CSerialization::StrictScope strict;
            CSerializerFunction<std::shared_ptr<json>,
                                std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(game, invalid_map);
        },
        "strict map deserialization should reject malformed entries");
}

} // namespace

int main() {
    test_string_deserialization_preserves_empty_and_whitespace();
    test_string_deserialization_coerces_non_string_targets();
    test_happy_path_add_and_distance();
    test_edge_case_adjacent_or_same();
    test_comparison_and_ordering();
    test_boundary_invalid_key_parsing();
    test_near_coords_helpers();
    test_pathfinder_find_path_without_obstacles();
    test_pathfinder_waypoint_and_blocked_goal();
    test_pathfinder_returns_start_when_passable_goal_has_no_route();
    test_pathfinder_caches_passability_checks();
    test_pathfinder_waypoint_override();
    test_pathfinder_crosses_levels_through_explicit_waypoint();
    test_toroidal_pathfinder_prefers_wrapped_route();
    test_toroidal_pathfinder_wraps_on_both_axes();
    test_json_parse_expected_success_and_failure();
    test_json_parse_dump_and_type_helpers();
    test_sdl_raii_alias_owns_surface();
    test_direction_mapping();
    test_rect_bounds_inclusion();
    test_tag_round_trip_and_ordering();
    test_unknown_tag_rejection();
    test_tag_mutation_iteration_and_range_helpers();
    test_property_setters_emit_change_signals();
    test_reviewed_value_wrappers_have_explicit_primitive_metadata();
    test_nested_primitive_wrappers_serialize_direct_values_and_round_trip();
    test_nested_property_notification_batches_emit_one_deterministic_signal();
    test_object_deserialization_batches_property_notifications();
    test_object_clone_batches_property_notifications();
    test_game_context_owns_distinct_gui_handlers_per_game();
    test_game_context_rejects_services_without_owner_game();
    test_game_context_transition_generation_helpers_and_shutdown();
    test_playtest_trace_records_and_helper_payloads();
    test_delayed_future_handlers_run_through_event_loop();
    test_script_rejects_executable_expressions();
    test_save_format_codec_validation();
    test_serialization_collection_and_error_helpers();

    return finish_tests();
}
