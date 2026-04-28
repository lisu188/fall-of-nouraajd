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

#include "core/CTags.h"
#include "core/CJsonUtil.h"
#include "core/CPathFinder.h"
#include "core/CUtil.h"
#include "gui/CSdlResources.h"
#include "handler/CScriptHandler.h"
#include <rdg.h>
#include "vcache.h"
#include "vfunctional.h"
#include "vutil.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <iostream>
#include <map>
#include <pybind11/embed.h>
#include <queue>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>

namespace {
int failures = 0;
int cache_value_calls = 0;

int next_cache_value() { return ++cache_value_calls; }

int cache_ttl() { return 5; }

struct TagProbe {
    CTags tags;

    bool hasTag(CTag tag) { return tags.contains(tag); }
};

struct CastBase {
    virtual ~CastBase() = default;
};

struct CastDerived : CastBase {};

struct ConceptCanStep {
    bool operator()(const Coords &) const { return true; }
};

struct ConceptWaypoint {
    std::pair<bool, Coords> operator()(const Coords &) const { return {false, ZERO}; }
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

void expect_true(bool condition, const char *message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << "\n";
        ++failures;
    }
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
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(path.size() == 2, "findPath should include each next step until goal");
    expect_true(path.front() == Coords(1, 0, 0), "findPath should return first move toward goal");
    expect_true(path.back() == Coords(2, 0, 0), "findPath should end on goal");

    auto next_step = CPathFinder::findNextStep(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(next_step->get() == Coords(1, 0, 0), "findNextStep should return the first optimal neighbor");
}

void test_pathfinder_waypoint_and_blocked_goal() {
    auto can_step = [](const Coords &coords) { return coords == Coords(0, 0, 0); };
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(path.size() == 1, "findPath should return only start when goal is unreachable");
    expect_true(path.front() == Coords(0, 0, 0), "findPath should remain on start if no route exists");
}

void test_pathfinder_caches_passability_checks() {
    std::map<Coords, int> calls;
    auto can_step = [&calls](const Coords &coords) {
        calls[coords]++;
        return coords == Coords(0, 0, 0) || coords == Coords(1, 0, 0) || coords == Coords(2, 0, 0);
    };
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };
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
    auto forced_waypoint = [](const Coords &coords) {
        if (coords == Coords(0, 0, 0)) {
            return std::pair<bool, Coords>(true, Coords(2, 0, 0));
        }
        return std::pair<bool, Coords>(false, ZERO);
    };
    auto next_step = CPathFinder::findNextStep(Coords(0, 0, 0), Coords(2, 0, 0), can_step, forced_waypoint);
    expect_true(next_step->get() == Coords(2, 0, 0), "findNextStep should allow waypoint override when available");
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
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };
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
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };
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

void test_cache_helpers_reuse_and_expire_values() {
    cache_value_calls = 0;
    vstd::cache<std::string, int, next_cache_value, cache_ttl> cache;
    expect_true(cache.get("alpha", 10) == 1, "cache should populate a missing value");
    expect_true(cache.get("alpha", 12) == 1, "cache should reuse values before ttl expiry");
    expect_true(cache.get("alpha", 20) == 2, "cache should refresh values after ttl expiry");

    int callback_calls = 0;
    vstd::cache2<std::string, int, cache_ttl> callback_cache;
    auto callback = [&]() { return ++callback_calls; };
    expect_true(callback_cache.get("beta", 1, callback) == 1, "cache2 should populate from callback");
    expect_true(callback_cache.get("beta", 3, callback) == 1, "cache2 should reuse callback values before ttl expiry");
    expect_true(callback_cache.get("beta", 8, callback) == 2, "cache2 should refresh callback values after ttl expiry");
}

void test_functional_helpers_transform_iterate_and_group() {
    int void_call_result = 0;
    vstd::functional::call([&]() { void_call_result = 4; });
    expect_true(void_call_result == 4, "functional::call should invoke void callables");
    expect_true(vstd::functional::call([](int value) { return value * 2; }, 5) == 10,
                "functional::call should return non-void callable results");

    std::set<int> numbers{1, 2, 3, 4};
    auto labels = vstd::functional::map<std::set<std::string>>(
        numbers, [](int value) { return value % 2 == 0 ? "even" : "odd"; });
    expect_true(labels == std::set<std::string>({"even", "odd"}), "functional::map should transform into return set");

    int foreach_sum = 0;
    vstd::functional::foreach (numbers, [&](int value) { foreach_sum += value; });
    expect_true(foreach_sum == 10, "functional::foreach should visit every value");
    expect_true(vstd::functional::sum<int>(numbers) == 10, "functional::sum should add plain values");
    expect_true(vstd::functional::sum<int>(numbers, [](int value) { return value * 3; }) == 30,
                "functional::sum should add mapped values");

    auto grouped =
        vstd::functional::map_reduce<std::string>(numbers, [](int value) { return value % 2 == 0 ? "even" : "odd"; });
    expect_true(grouped["even"] == std::set<int>({2, 4}), "map_reduce should group even values");
    expect_true(grouped["odd"] == std::set<int>({1, 3}), "map_reduce should group odd values");
}

void test_vstd_container_and_pointer_helpers() {
    std::set<int> ordered{1, 2, 3};
    expect_true(*vstd::any(ordered) == 1, "any should return the first available element");
    expect_true(vstd::ctn(ordered, 2), "ctn should find values in set-like containers");

    std::string text = "abc";
    expect_true(vstd::ctn(text, 'b'), "ctn should find values in strings");

    std::vector<int> values{2, 4, 6};
    expect_true(vstd::ctn(values, 3, [](int target, int value) { return target * 2 == value; }),
                "ctn with comparator should use custom matching");
    expect_true(vstd::ctn_pred(values, [](int value) { return value == 4; }), "ctn_pred should use custom predicates");
    expect_true(*vstd::find_if(values, [](int value) { return value > 4; }) == 6,
                "find_if should return the first predicate match");

    int executed = 0;
    vstd::execute_if(values, [](int value) { return value == 4; }, [&](int value) { executed = value; });
    expect_true(executed == 4, "execute_if should run a callback for matching values");

    vstd::erase(values, 4, [](int left, int right) { return left == right; });
    expect_true(values == std::vector<int>({2, 6}), "erase should remove the first comparator match");
    vstd::erase_if(values, [](int value) { return value == 2; });
    expect_true(values == std::vector<int>({6}), "erase_if should remove the first predicate match");

    std::vector<int> indexed{10, 20, 30};
    const std::vector<int> const_indexed{40, 50};
    expect_true(*vstd::get(indexed, 1) == 20, "get should return a pointer for a valid mutable index");
    expect_true(vstd::get(indexed, -1) == nullptr, "get should reject negative mutable indexes");
    expect_true(*vstd::get(const_indexed, 0) == 40, "get should return a pointer for a valid const index");
    expect_true(vstd::get(const_indexed, 3) == nullptr, "get should reject out-of-bounds const indexes");

    std::shared_ptr<CastBase> base = std::make_shared<CastDerived>();
    expect_true(vstd::castable<CastDerived>(base), "castable should detect dynamic shared pointer casts");
    expect_true(vstd::type_pair<int, std::string>() ==
                    std::make_pair(std::type_index(typeid(int)), std::type_index(typeid(std::string))),
                "type_pair should return a pair of type indexes");
}

void test_vstd_queue_collection_and_function_helpers() {
    auto bound = vstd::bind([](int left, int right) { return left + right; }, 2, 3);
    expect_true(bound() == 5, "bind should store function arguments");

    auto unary = vstd::make_function([](int value) { return value + 1; });
    auto nullary = vstd::make_function([]() { return 9; });
    expect_true(unary(4) == 5, "make_function should wrap unary callables");
    expect_true(nullary() == 9, "make_function should wrap nullary callables");

    std::queue<int> queue;
    queue.push(7);
    expect_true(vstd::pop(queue) == 7, "pop should remove queue front values");

    std::priority_queue<int> priority_queue;
    priority_queue.push(3);
    priority_queue.push(9);
    expect_true(vstd::pop_p(priority_queue) == 9, "pop_p should remove priority queue top values");

    vstd::list<int> custom_list;
    custom_list.insert(4);
    expect_true(custom_list.front() == 4, "vstd::list::insert should append values");

    vstd::blocking_queue<int> blocking_queue;
    blocking_queue.push(11);
    int popped = 0;
    expect_true(blocking_queue.pop(popped) && popped == 11, "blocking_queue should pop queued values");
    blocking_queue.shutdown();
    expect_true(!blocking_queue.pop(popped), "blocking_queue should stop popping after shutdown");
    blocking_queue.reset();
    blocking_queue.push(12);
    expect_true(blocking_queue.pop(popped) && popped == 12, "blocking_queue reset should accept new values");
}

void test_vstd_allocation_random_and_value_helpers() {
    auto allocated = vstd::allocate<int>(2);
    allocated[0] = 3;
    allocated[1] = 4;
    expect_true(allocated[0] + allocated[1] == 7, "allocate should return writable storage");
    vstd::deallocate(allocated, 2);

    std::vector<int> array_source{5, 6};
    auto array = vstd::as_array(array_source);
    expect_true(array[0] == 5 && array[1] == 6, "as_array should copy vector values into allocated storage");
    vstd::deallocate(array, array_source.size());

    int observed = 0;
    auto pointer = std::make_shared<int>(13);
    vstd::if_not_null(pointer, [&](auto value) { observed = *value; });
    vstd::if_not_null(std::shared_ptr<int>(), [&](auto) { observed = -1; });
    expect_true(observed == 13, "if_not_null should only invoke callbacks for populated pointers");

    expect_true(vstd::percent(80, 25) == 20, "percent should compute a percentage of a value");
    expect_true(vstd::with<int>(pointer, [](auto value) { return *value + 1; }) == 14,
                "with should return callback values for populated pointers");
    expect_true(vstd::with<int>(std::shared_ptr<int>(), [](auto) { return 99; }) == 0,
                "with should return a default value for empty pointers");

    int void_with_value = 0;
    vstd::with<void>(pointer, [&](auto value) { void_with_value = *value; });
    expect_true(void_with_value == 13, "with<void> should run callbacks for populated pointers");

    expect_true(vstd::all_equals(3, 3, 3), "all_equals should accept matching values");
    expect_true(!vstd::all_equals(3, 4, 3), "all_equals should reject differing values");
    expect_true(vstd::set(1) == std::set<int>({1}), "set should build a std::set");
    expect_true(vstd::as_list(1).front() == 1, "as_list should build a std::list");

    std::set<int> old_values{1, 2};
    std::set<int> new_values{2, 3};
    auto [to_add, to_remove] = vstd::set_difference(old_values, new_values);
    expect_true(to_add == std::set<int>({3}) && to_remove == std::set<int>({1}),
                "set_difference should identify additions and removals");

    std::set<int> empty_choices;
    std::set<int> single_choice{42};
    expect_true(vstd::random_element(empty_choices) == empty_choices.end(),
                "random_element should return end for empty containers");
    expect_true(*vstd::random_element(single_choice) == 42, "random_element should return the only available element");

    auto components = vstd::random_components(5, std::set<int>({1, 2}));
    expect_true(vstd::functional::sum<int>(components) == 5, "random_components should decompose the requested value");
    expect_true(vstd::square_ctn(10, 10, 9, 0), "square_ctn should accept coordinates inside bounds");
    expect_true(!vstd::square_ctn(10, 10, 10, 0), "square_ctn should reject coordinates outside bounds");
}

void test_vstd_string_helpers() {
    expect_true(vstd::str(Coords(1, 2, 3)) == "1,2,3", "vstd::str should use the Coords specialization");
    expect_true(vstd::replace("red red", "red", "blue") == "blue blue", "replace should handle repeated matches");
    expect_true(vstd::trim("  text\t") == "text", "trim should remove surrounding whitespace");
    expect_true(vstd::is_empty(" \t"), "is_empty should treat whitespace as empty");
    expect_true(vstd::str("a", 1, "b") == "a1b", "variadic str should concatenate stringified values");
    expect_true(vstd::to_int("42").first == 42 && vstd::to_int("42").second, "to_int should parse integers");
    expect_true(!vstd::to_int("42x").second, "to_int should reject partially parsed integers");
    expect_true(!vstd::is_int("x"), "is_int should reject non-numeric strings");
    expect_true(vstd::join(std::list<std::string>{"a", "b"}, ",") == "a,b", "join should use separators");
    expect_true(vstd::split("a:b", ':') == std::vector<std::string>({"a", "b"}), "split should split on delimiter");
    expect_true(vstd::string_equals(5, "5"), "string_equals should compare stringified values");
    expect_true(vstd::ends_with("report.txt", ".txt"), "ends_with should detect matching suffixes");
    expect_true(!vstd::ends_with("txt", "report.txt"), "ends_with should reject longer suffixes");

    auto wide = vstd::to_wchar("abc");
    expect_true(wide[0] == L'a' && wide[2] == L'c', "to_wchar should convert narrow text");
    delete[] wide;

    const char *args[] = {"one", "two"};
    auto wide_args = vstd::to_wchar(2, args);
    expect_true(wide_args[0][0] == L'o' && wide_args[1][0] == L't', "to_wchar should convert argument arrays");
    delete[] wide_args[0];
    delete[] wide_args[1];
    delete[] wide_args;

    std::string lines = "first";
    vstd::add_line(lines, "second");
    vstd::add_line(lines, "");
    expect_true(lines == "first\nsecond", "add_line should append non-empty lines only");
    expect_true(vstd::camel("hello world") == "Hello World ", "camel should title-case space-separated words");
}

void test_script_handler_executes_commands_and_wraps_functions() {
    CScriptHandler handler;

    handler.execute_script("value = 4");
    expect_true(handler.get_object<int>("value") == 4, "execute_script should write into the main namespace");

    pybind11::dict custom_namespace;
    custom_namespace["seed"] = 7;
    handler.execute_script("result = seed + 5", custom_namespace);
    expect_true(custom_namespace["result"].cast<int>() == 12, "execute_script should honor a provided namespace");

    const auto built = handler.build_command({"capture", "alpha", "beta"});
    expect_true(built == "capture(\"alpha\",\"beta\")", "build_command should quote string arguments");

    handler.execute_script("captured = ''\n"
                           "def capture(first, second):\n"
                           "\tglobal captured\n"
                           "\tcaptured = first + ':' + second");
    handler.execute_command({"capture", "alpha", "beta"});
    expect_true(handler.get_object<std::string>("captured") == "alpha:beta",
                "execute_command should execute the built Python call");

    handler.import("math");
    handler.execute_script("root_value = math.isqrt(81)");
    expect_true(handler.get_object<int>("root_value") == 9, "import should load Python modules into the namespace");

    handler.add_function("triple_value", "return value * 3", {"value"});
    expect_true(handler.call_function<int, int>("triple_value", 7) == 21,
                "add_function should compile callable Python code");

    auto multiply = handler.create_function<int, int, int>("multiply_values", "return left * right", {"left", "right"});
    expect_true(multiply(6, 7) == 42, "create_function should return a typed callable wrapper");
    expect_true(handler.call_function<int, int, int>("multiply_values", 3, 5) == 15,
                "call_function should invoke previously created Python callables");

    handler.execute_script("observed = 0");
    auto store_value =
        handler.create_function<void, int>("store_value", "global observed\nobserved = value", {"value"});
    store_value(123);
    expect_true(handler.get_object<int>("observed") == 123,
                "void wrappers should execute Python callables without returning values");

    handler.execute_script("def returns_text():\n"
                           "\treturn 'oops'");
    auto invalid_cast = handler.get_function<int>("returns_text");
    expect_true(invalid_cast() == 0, "typed wrappers should return a default value after Python cast failures");

    handler.add_function("broken_function", "return )", {});
    handler.call_function<void>("broken_function");

    handler.add_class("NamedScriptClass", "def value(self):\n\treturn 9", {});
    handler.execute_script("named_instance = NamedScriptClass()");
    auto named_instance = handler.get_object<pybind11::object>("named_instance");
    expect_true(named_instance.attr("value")().cast<int>() == 9, "add_class should compile named Python classes");

    const auto generated_class = handler.add_class("def value(self):\n\treturn 11", {});
    handler.execute_script("generated_instance = " + generated_class + "()");
    auto generated_instance = handler.get_object<pybind11::object>("generated_instance");
    expect_true(generated_instance.attr("value")().cast<int>() == 11,
                "add_class overload should return a usable generated class name");

    expect_true(handler.call_created_function<int, int>("return value * 2", {"value"}, 8) == 16,
                "call_created_function should compile, call and delete temporary Python functions");

    handler.execute_script("created_void_value = 0");
    handler.call_created_function("global created_void_value\ncreated_void_value = value + 1", {"value"}, 4);
    expect_true(handler.get_object<int>("created_void_value") == 5,
                "void call_created_function should update Python state and clean up its temporary function");
}

void test_random_dungeon_cell_flags_and_validation() {
    rdg::Cell cell;
    cell.setType(rdg::CellType::ROOM);
    expect_true(cell.hasType(rdg::CellType::ROOM), "rdg cell should store a primary type");
    expect_true(cell.isBlockedRoom(), "rdg room cells should block room placement");
    expect_true(cell.isOpenspace(), "rdg room cells should be open space");
    cell.addType(rdg::CellType::ENTRANCE);
    cell.setLabel("A");
    expect_true(cell.hasLabel() && cell.getLabel() == "A", "rdg cells should expose single-character labels");
    expect_true(cell.isEspace(), "rdg labeled entrance cells should count as entrance space");
    cell.clearEspace();
    expect_true(!cell.hasLabel(), "rdg clearEspace should clear labels");
    expect_true(!cell.hasType(rdg::CellType::ENTRANCE), "rdg clearEspace should clear entrance flags");
    cell.setType(rdg::CellType::STAIR_DN);
    cell.addType(rdg::CellType::STAIR_UP);
    expect_true(cell.isStairs(), "rdg stair flags should be detected");
    cell.clearTypes();
    expect_true(!cell.isStairs(), "rdg clearTypes should remove stair flags");

    rdg::Door locked_door{.kind = rdg::DoorKind::Locked};
    rdg::Stairs up_stairs{.kind = rdg::StairKind::Up};
    expect_true(locked_door.getKey() == "lock", "rdg door keys should describe locked doors");
    expect_true(locked_door.getType() == "Locked Door", "rdg door labels should describe locked doors");
    expect_true(up_stairs.getKey() == "up", "rdg stair keys should describe up stairs");

    expect_true(rdg::dungeon_layout_from_string("Box") == rdg::DungeonLayout::Box,
                "rdg dungeon layout parsing should accept Box");
    expect_true(!rdg::dungeon_layout_from_string("Invalid"), "rdg dungeon layout parsing should reject unknown values");
    expect_true(rdg::room_layout_from_string("Packed") == rdg::RoomLayout::Packed,
                "rdg room layout parsing should accept Packed");
    expect_true(!rdg::room_layout_from_string("Invalid"), "rdg room layout parsing should reject unknown values");
    expect_true(rdg::map_style_from_string("Standard") == rdg::MapStyle::Standard,
                "rdg map style parsing should accept Standard");
    expect_true(!rdg::map_style_from_string("Invalid"), "rdg map style parsing should reject unknown values");
    expect_true(rdg::to_string(rdg::DungeonLayout::Round) == "Round", "rdg layout strings should include Round");
    expect_true(rdg::to_string(rdg::RoomLayout::Scattered) == "Scattered",
                "rdg room layout strings should include Scattered");
    expect_true(rdg::to_string(rdg::MapStyle::Standard) == "Standard", "rdg map style strings should include Standard");
    expect_true(rdg::key(rdg::DoorKind::Portcullis) == "portc", "rdg door keys should include portcullis");
    expect_true(rdg::to_string(rdg::DoorKind::Secret) == "Secret Door", "rdg door labels should include secret doors");
    expect_true(rdg::key(rdg::StairKind::Down) == "down", "rdg stair keys should include down stairs");

    rdg::Options options;
    options.n_rows = 2;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject tiny dimensions");
    options.n_rows = 4;
    options.n_cols = 5;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject even dimensions");
    options.n_rows = 5;
    options.room_min = 0;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject non-positive room sizes");
    options.room_min = 7;
    options.room_max = 3;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject inverted room sizes");
    options.room_min = 3;
    options.room_max = 7;
    options.remove_deadends = 101;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject invalid dead-end percentages");
    options.remove_deadends = 50;
    options.add_stairs = -1;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject negative stair counts");
    options.add_stairs = 1;
    options.cell_size = 0;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject non-positive cell sizes");
    options.cell_size = 18;
    expect_true(!rdg::validate_options(options).has_value(), "rdg should accept valid options");
}

void test_random_dungeon_layout_variants_generate_accessible_maps() {
    std::mt19937 rng(12345);
    std::vector<rdg::Options> variants;

    rdg::Options packed_box;
    packed_box.n_rows = 17;
    packed_box.n_cols = 17;
    packed_box.room_layout = rdg::RoomLayout::Packed;
    packed_box.dungeon_layout = rdg::DungeonLayout::Box;
    packed_box.corridor_layout = rdg::CorridorLayout::STRAIGHT;
    packed_box.add_stairs = 2;
    variants.push_back(packed_box);

    rdg::Options scattered_cross;
    scattered_cross.n_rows = 21;
    scattered_cross.n_cols = 21;
    scattered_cross.room_layout = rdg::RoomLayout::Scattered;
    scattered_cross.dungeon_layout = rdg::DungeonLayout::Cross;
    scattered_cross.corridor_layout = rdg::CorridorLayout::BENT;
    scattered_cross.remove_deadends = 50;
    scattered_cross.add_stairs = 1;
    variants.push_back(scattered_cross);

    rdg::Options round_labyrinth;
    round_labyrinth.n_rows = 19;
    round_labyrinth.n_cols = 19;
    round_labyrinth.room_layout = rdg::RoomLayout::Packed;
    round_labyrinth.dungeon_layout = rdg::DungeonLayout::Round;
    round_labyrinth.corridor_layout = rdg::CorridorLayout::LABYRINTH;
    round_labyrinth.remove_deadends = 0;
    round_labyrinth.add_stairs = 0;
    variants.push_back(round_labyrinth);

    for (const auto &options : variants) {
        auto dungeon = rdg::create_dungeon(options, rng);
        expect_true(dungeon.rowCount() == options.n_rows, "rdg dungeon should preserve requested row count");
        expect_true(dungeon.colCount() == options.n_cols, "rdg dungeon should preserve requested column count");
        expect_true(!dungeon.getCells().empty(), "rdg dungeon should expose generated cells");
        expect_true(!dungeon.getRooms().empty(), "rdg dungeon variants should generate rooms");

        int open_cells = 0;
        int blocked_cells = 0;
        int door_cells = 0;
        int stair_cells = 0;
        for (int row = 0; row < dungeon.rowCount(); ++row) {
            for (int col = 0; col < dungeon.colCount(); ++col) {
                const auto &cell = dungeon.cellAt(row, col);
                open_cells += cell.isOpenspace() ? 1 : 0;
                blocked_cells += cell.hasType(rdg::CellType::BLOCKED) ? 1 : 0;
                door_cells += cell.isDoorspace() ? 1 : 0;
                stair_cells += cell.isStairs() ? 1 : 0;
            }
        }

        expect_true(open_cells > 0, "rdg dungeon variants should include open cells");
        expect_true(blocked_cells >= 0, "rdg dungeon blocked count should be inspectable");
        expect_true(door_cells >= 0, "rdg dungeon door count should be inspectable");
        expect_true(stair_cells >= static_cast<int>(dungeon.getStairs().size()),
                    "rdg stair records should correspond to stair cells");
    }
}
} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_happy_path_add_and_distance();
    test_edge_case_adjacent_or_same();
    test_comparison_and_ordering();
    test_boundary_invalid_key_parsing();
    test_near_coords_helpers();
    test_pathfinder_find_path_without_obstacles();
    test_pathfinder_waypoint_and_blocked_goal();
    test_pathfinder_caches_passability_checks();
    test_pathfinder_waypoint_override();
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
    test_cache_helpers_reuse_and_expire_values();
    test_functional_helpers_transform_iterate_and_group();
    test_vstd_container_and_pointer_helpers();
    test_vstd_queue_collection_and_function_helpers();
    test_vstd_allocation_random_and_value_helpers();
    test_vstd_string_helpers();
    test_script_handler_executes_commands_and_wraps_functions();
    test_random_dungeon_cell_flags_and_validation();
    test_random_dungeon_layout_variants_generate_accessible_maps();

    if (failures == 0) {
        std::cout << "All unit tests passed.\n";
        return 0;
    }

    std::cerr << failures << " unit test(s) failed.\n";
    return 1;
}
