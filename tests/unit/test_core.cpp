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
#include "core/CPathFinder.h"
#include "core/CSerialization.h"
#include "core/CScript.h"
#include "core/CTags.h"
#include "core/CUtil.h"
#include "gui/CSdlResources.h"
#include "test_harness.h"
#include "vutil.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
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
    expect_true(CJsonUtil::from_string("{", "unit-json-wrapper") == nullptr,
                "from_string should keep the public nullptr behavior on parse failure");
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
    test_sdl_raii_alias_owns_surface();
    test_direction_mapping();
    test_rect_bounds_inclusion();
    test_tag_round_trip_and_ordering();
    test_unknown_tag_rejection();
    test_tag_mutation_iteration_and_range_helpers();
    test_delayed_future_handlers_run_through_event_loop();
    test_script_rejects_executable_expressions();

    return finish_tests();
}
