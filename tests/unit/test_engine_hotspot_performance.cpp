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

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CStats.h"
#include "object/CCreature.h"
#include "object/CMapObject.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "veventloop.h"

#include <pybind11/embed.h>

#include <cmath>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace {

constexpr int SHARED_TARGET_WIDTH = 17;
constexpr int SHARED_TARGET_HEIGHT = 17;
constexpr int SHARED_TARGET_ACTORS = 40;
constexpr int SPATIAL_MARKERS = 80;
constexpr int SPATIAL_HOTSPOT_MARKERS = 6;
constexpr int MODERATE_MOVE_ACTORS = 24;

struct MapFixture {
    std::shared_ptr<CGame> game;
    std::shared_ptr<CMap> map;
    int width = 0;
    int height = 0;
};

std::shared_ptr<CTile> make_tile(const std::shared_ptr<CGame> &game, bool can_step, const std::string &tile_type) {
    auto tile = std::make_shared<CTile>();
    tile->setGame(game);
    tile->setCanStep(can_step);
    tile->setTileType(tile_type);
    return tile;
}

MapFixture make_open_map(int width, int height) {
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, width - 1}});
    map->setYBounds({{0, height - 1}});

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            map->addTile(make_tile(game, true, "floor"), x, y, 0);
        }
    }

    return {game, map, width, height};
}

std::shared_ptr<CMapObject> make_object(const MapFixture &fixture, const std::string &name, Coords coords,
                                        bool can_step = true) {
    auto object = std::make_shared<CMapObject>();
    object->setGame(fixture.game);
    object->setName(name);
    object->setCanStep(can_step);
    object->setCoords(coords);
    return object;
}

std::shared_ptr<CStats> make_actor_stats() {
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    stats->setAgility(10);
    return stats;
}

std::shared_ptr<CCreature> make_actor(const MapFixture &fixture, const std::string &name, Coords coords,
                                      const std::string &target_name) {
    auto actor = std::make_shared<CCreature>();
    actor->setGame(fixture.game);
    actor->setName(name);
    actor->setBaseStats(make_actor_stats());
    actor->setLevel(1);
    actor->setHp(100);
    actor->setNpc(true);
    actor->setCoords(coords);

    auto controller = std::make_shared<CTargetController>();
    controller->setTarget(target_name);
    actor->setController(controller);
    return actor;
}

void add_object(const MapFixture &fixture, const std::shared_ptr<CMapObject> &object) {
    fixture.map->addObject(object);
}

Coords resolve_step(const std::shared_ptr<CCreature> &actor) {
    auto future = actor->getController()->control(actor);
    vstd::event_loop<>::instance()->run();
    return future->get();
}

bool is_cardinal_step(const std::shared_ptr<CMap> &map, Coords from, Coords to) {
    auto delta = map->getShortestDelta(from, to);
    return delta.z == 0 && std::abs(delta.x) + std::abs(delta.y) == 1;
}

bool moves_closer(const std::shared_ptr<CMap> &map, Coords from, Coords to, Coords goal) {
    return map->getDistance(to, goal) < map->getDistance(from, goal);
}

void replace_tile(const MapFixture &fixture, Coords coords, bool can_step, const std::string &tile_type) {
    fixture.map->removeTile(coords.x, coords.y, coords.z);
    fixture.map->addTile(make_tile(fixture.game, can_step, tile_type), coords.x, coords.y, coords.z);
}

void test_many_target_controllers_share_one_goal_without_mutating_navigation() {
    auto fixture = make_open_map(SHARED_TARGET_WIDTH, SHARED_TARGET_HEIGHT);
    const Coords goal_coords(SHARED_TARGET_WIDTH - 1, SHARED_TARGET_HEIGHT / 2, 0);
    add_object(fixture, make_object(fixture, "sharedGoal", goal_coords));

    std::vector<std::shared_ptr<CCreature>> actors;
    actors.reserve(SHARED_TARGET_ACTORS);
    for (int i = 0; i < SHARED_TARGET_ACTORS; ++i) {
        const Coords coords(i % 4, i / 4, 0);
        auto actor = make_actor(fixture, "sharedTargetActor" + std::to_string(i), coords, "sharedGoal");
        add_object(fixture, actor);
        actors.push_back(actor);
    }

    const auto revision_before = fixture.map->getNavigationRevision();
    const auto tile_count_before = fixture.map->getTiles().size();
    const auto object_count_before = fixture.map->getObjects().size();
    int progressing_steps = 0;

    performance_guard::clearTargetFlowCache();
    expect_true(performance_guard::targetFlowCacheSize() == 0, "shared-goal flow cache should start empty");
    for (const auto &actor : actors) {
        const auto start = fixture.map->normalizeCoords(actor->getCoords());
        const auto step = fixture.map->normalizeCoords(resolve_step(actor));
        if (step != start && is_cardinal_step(fixture.map, start, step) &&
            moves_closer(fixture.map, start, step, goal_coords) && fixture.map->canStep(step)) {
            progressing_steps++;
        }
    }

    expect_true(progressing_steps == SHARED_TARGET_ACTORS,
                "all shared-goal actors should receive one valid progress step");
    expect_true(performance_guard::targetFlowCacheSize() == 1, "shared-goal actors should reuse one target flow field");
    expect_true(fixture.map->getNavigationRevision() == revision_before,
                "shared-goal controller reads should not mutate the navigation revision");
    expect_true(fixture.map->getTiles().size() == tile_count_before,
                "shared-goal controller reads should not materialize or remove tiles");
    expect_true(fixture.map->getObjects().size() == object_count_before,
                "shared-goal controller reads should not add or remove objects");

    for (const auto &actor : actors) {
        resolve_step(actor);
    }
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "repeated shared-goal reads should keep reusing the cached target flow field");
}

void test_relevant_object_move_invalidates_target_navigation() {
    auto fixture = make_open_map(7, 5);
    const Coords goal_coords(6, 2, 0);
    auto goal = make_object(fixture, "objectInvalidationGoal", goal_coords);
    auto blocker = make_object(fixture, "movingBlocker", Coords(3, 4, 0), false);
    auto actor = make_actor(fixture, "objectInvalidationActor", Coords(0, 2, 0), "objectInvalidationGoal");
    add_object(fixture, goal);
    add_object(fixture, blocker);
    add_object(fixture, actor);

    const auto revision_before_warm = fixture.map->getNavigationRevision();
    performance_guard::clearTargetFlowCache();
    const auto open_step = fixture.map->normalizeCoords(resolve_step(actor));
    expect_true(open_step == Coords(1, 2, 0), "open object-invalidation path should initially move east");
    expect_true(fixture.map->getNavigationRevision() == revision_before_warm,
                "warming target navigation should not bump the navigation revision");
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "object-invalidation warm path should build one target flow field");

    blocker->moveTo(open_step);
    expect_true(fixture.map->getNavigationRevision() == revision_before_warm + 1,
                "moving a blocking object into the path should bump the navigation revision exactly once");
    expect_true(!fixture.map->canStep(open_step), "moved blocking object should make the old next step impassable");

    const auto rerouted_step = fixture.map->normalizeCoords(resolve_step(actor));
    expect_true(rerouted_step != open_step, "target navigation should reroute after a relevant object move");
    expect_true(rerouted_step != actor->getCoords() && is_cardinal_step(fixture.map, actor->getCoords(), rerouted_step),
                "rerouted object-invalidation step should still be one legal movement");
    expect_true(fixture.map->canStep(rerouted_step), "rerouted object-invalidation step should be passable");
    expect_true(performance_guard::targetFlowCacheSize() == 2,
                "object navigation revision change should create one replacement flow field");
}

void test_relevant_tile_change_invalidates_target_navigation() {
    auto fixture = make_open_map(7, 5);
    const Coords goal_coords(6, 2, 0);
    auto goal = make_object(fixture, "tileInvalidationGoal", goal_coords);
    auto actor = make_actor(fixture, "tileInvalidationActor", Coords(0, 2, 0), "tileInvalidationGoal");
    add_object(fixture, goal);
    add_object(fixture, actor);

    const auto revision_before_warm = fixture.map->getNavigationRevision();
    performance_guard::clearTargetFlowCache();
    const auto open_step = fixture.map->normalizeCoords(resolve_step(actor));
    expect_true(open_step == Coords(1, 2, 0), "open tile-invalidation path should initially move east");
    expect_true(fixture.map->getNavigationRevision() == revision_before_warm,
                "warming tile-invalidation navigation should not bump the navigation revision");
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "tile-invalidation warm path should build one target flow field");

    replace_tile(fixture, open_step, false, "wall");
    expect_true(fixture.map->getNavigationRevision() == revision_before_warm + 2,
                "replacing one tile should bump navigation once for removal and once for insertion");
    expect_true(!fixture.map->canStep(open_step), "replacement wall tile should make the old next step impassable");

    const auto rerouted_step = fixture.map->normalizeCoords(resolve_step(actor));
    expect_true(rerouted_step != open_step, "target navigation should reroute after a relevant tile change");
    expect_true(rerouted_step != actor->getCoords() && is_cardinal_step(fixture.map, actor->getCoords(), rerouted_step),
                "rerouted tile-invalidation step should still be one legal movement");
    expect_true(fixture.map->canStep(rerouted_step), "rerouted tile-invalidation step should be passable");
    expect_true(performance_guard::targetFlowCacheSize() == 2,
                "tile navigation revision change should create one replacement flow field");
}

void test_irrelevant_metadata_activity_does_not_invalidate_navigation() {
    auto fixture = make_open_map(9, 5);
    const Coords goal_coords(8, 2, 0);
    auto goal = make_object(fixture, "metadataGoal", goal_coords);
    auto actor = make_actor(fixture, "metadataActor", Coords(0, 2, 0), "metadataGoal");
    auto marker = make_object(fixture, "metadataMarker", Coords(8, 4, 0));
    add_object(fixture, goal);
    add_object(fixture, actor);
    add_object(fixture, marker);

    performance_guard::clearTargetFlowCache();
    const auto first_step = fixture.map->normalizeCoords(resolve_step(actor));
    const auto revision_before_metadata = fixture.map->getNavigationRevision();
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "metadata activity fixture should build one target flow field");
    marker->setLabel("changed without movement");
    marker->setDescription("non-navigation metadata");
    const auto second_step = fixture.map->normalizeCoords(resolve_step(actor));

    expect_true(fixture.map->getNavigationRevision() == revision_before_metadata,
                "irrelevant object metadata changes should not invalidate navigation");
    expect_true(second_step == first_step, "irrelevant object metadata changes should keep the same target step");
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "irrelevant metadata activity should not rebuild target flow fields");
    expect_true(fixture.map->getObjectsAtCoords(marker->getCoords()).contains(marker),
                "irrelevant object metadata changes should keep the spatial cache entry intact");
}

void test_coordinate_cache_lookup_cardinality_and_move_updates() {
    auto fixture = make_open_map(12, 12);
    const Coords hotspot(4, 4, 0);
    const Coords destination(5, 4, 0);
    std::vector<std::shared_ptr<CMapObject>> markers;
    markers.reserve(SPATIAL_MARKERS);

    for (int i = 0; i < SPATIAL_MARKERS; ++i) {
        Coords coords((i * 5) % fixture.width, (i * 7) % fixture.height, 0);
        if (i < SPATIAL_HOTSPOT_MARKERS) {
            coords = hotspot;
        } else if (coords == hotspot || coords == destination) {
            coords = Coords((coords.x + 2) % fixture.width, (coords.y + 3) % fixture.height, 0);
        }
        auto marker = make_object(fixture, "spatialMarker" + std::to_string(i), coords);
        add_object(fixture, marker);
        markers.push_back(marker);
    }

    expect_true(fixture.map->getObjects().size() == SPATIAL_MARKERS,
                "spatial map should contain the expected marker count");
    expect_true(fixture.map->getObjectCacheEntryCountForTesting() == SPATIAL_MARKERS,
                "spatial cache should contain one coordinate entry per object");
    performance_guard::resetMapCoordinateLookupProbe();
    expect_true(fixture.map->getObjectsAtCoords(hotspot).size() == SPATIAL_HOTSPOT_MARKERS,
                "hotspot lookup should return only collocated marker objects");
    expect_true(performance_guard::mapCoordinateLookupProbeCount() == SPATIAL_HOTSPOT_MARKERS,
                "hotspot lookup should inspect only the matching coordinate bucket");
    performance_guard::resetMapCoordinateLookupProbe();
    expect_true(fixture.map->getObjectsAtCoords(destination).empty(),
                "destination lookup should start empty before a cache move");
    expect_true(performance_guard::mapCoordinateLookupProbeCount() == 0,
                "empty coordinate lookup should inspect no cached object entries");

    int hotspot_visit_count = 0;
    performance_guard::resetMapCoordinateLookupProbe();
    fixture.map->forObjectsAtCoords(hotspot,
                                    [&hotspot_visit_count](std::shared_ptr<CMapObject>) { hotspot_visit_count++; });
    expect_true(hotspot_visit_count == SPATIAL_HOTSPOT_MARKERS,
                "forObjectsAtCoords should visit exactly the hotspot cardinality");
    expect_true(performance_guard::mapCoordinateLookupProbeCount() == SPATIAL_HOTSPOT_MARKERS,
                "forObjectsAtCoords should probe only the matching coordinate bucket");

    const auto revision_before_move = fixture.map->getNavigationRevision();
    markers.front()->moveTo(destination);
    expect_true(fixture.map->getNavigationRevision() == revision_before_move + 1,
                "moving one cached marker should bump navigation exactly once");
    expect_true(fixture.map->getObjectsAtCoords(hotspot).size() == SPATIAL_HOTSPOT_MARKERS - 1,
                "moving one cached marker should remove it from the old coordinate bucket");
    expect_true(fixture.map->getObjectsAtCoords(destination).size() == 1,
                "moving one cached marker should add it to the new coordinate bucket");
    expect_true(fixture.map->getObjects().size() == SPATIAL_MARKERS,
                "moving one cached marker should not change total object count");
    expect_true(fixture.map->getObjectCacheEntryCountForTesting() == SPATIAL_MARKERS,
                "moving one cached marker should keep one coordinate entry per object");
    performance_guard::disableMapCoordinateLookupProbe();
}

void test_moderate_actor_map_move_turn_state_and_revision_bounds() {
    auto fixture = make_open_map(16, 10);
    const Coords goal_coords(15, 5, 0);
    add_object(fixture, make_object(fixture, "turnMoveGoal", goal_coords));

    std::vector<std::shared_ptr<CCreature>> actors;
    std::map<std::string, Coords> starting_positions;
    actors.reserve(MODERATE_MOVE_ACTORS);
    for (int i = 0; i < MODERATE_MOVE_ACTORS; ++i) {
        const Coords coords(i % 4, i / 4, 0);
        auto actor = make_actor(fixture, "turnMoveActor" + std::to_string(i), coords, "turnMoveGoal");
        add_object(fixture, actor);
        starting_positions[actor->getName()] = fixture.map->normalizeCoords(coords);
        actors.push_back(actor);
    }

    const auto revision_before_move = fixture.map->getNavigationRevision();
    const auto object_count_before_move = fixture.map->getObjects().size();
    const auto turn_before_move = fixture.map->getTurn();
    fixture.map->move();

    int moved_actors = 0;
    for (const auto &actor : actors) {
        const auto start = starting_positions.at(actor->getName());
        const auto current = fixture.map->normalizeCoords(actor->getCoords());
        if (current != start && is_cardinal_step(fixture.map, start, current) &&
            moves_closer(fixture.map, start, current, goal_coords)) {
            moved_actors++;
        }
        expect_true(fixture.map->getObjectByName(actor->getName()) == actor,
                    "turn-moved actor should remain registered by name");
    }

    expect_true(moved_actors == MODERATE_MOVE_ACTORS, "moderate actor turn should move every target-controlled actor");
    expect_true(fixture.map->getNavigationRevision() == revision_before_move + MODERATE_MOVE_ACTORS,
                "moderate actor turn should bump navigation once per committed actor move");
    expect_true(fixture.map->getTurn() == turn_before_move + 1, "moderate actor turn should advance map turn once");
    expect_true(!fixture.map->isMoving(), "moderate actor turn should clear the moving flag after completion");
    expect_true(fixture.map->getObjects().size() == object_count_before_move,
                "moderate actor turn should not add or remove map objects");
}

} // namespace

void run_engine_hotspot_performance_tests() {
    std::optional<pybind11::scoped_interpreter> interpreter;
    if (!Py_IsInitialized()) {
        interpreter.emplace();
    }

    test_many_target_controllers_share_one_goal_without_mutating_navigation();
    test_relevant_object_move_invalidates_target_navigation();
    test_relevant_tile_change_invalidates_target_navigation();
    test_irrelevant_metadata_activity_does_not_invalidate_navigation();
    test_coordinate_cache_lookup_cardinality_and_move_updates();
    test_moderate_actor_map_move_turn_state_and_revision_bounds();
}
