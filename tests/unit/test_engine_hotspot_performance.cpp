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
#include "core/CAsync.h"
#include "core/CGameContext.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "core/CTags.h"
#include "core/CUtil.h"
#include "handler/CFightHandler.h"
#include "handler/CEventHandler.h"
#include "object/CTrigger.h"
#include "handler/CObjectHandler.h"
#include "gui/CGui.h"
#include "gui/CMovementBatch.h"
#include "gui/object/CMinimapGraphicsObject.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CEffect.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "stat_composition_fixture.h"
#include "veventloop.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <cmath>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <set>
#include <utility>
#include <vector>

namespace {

constexpr int SHARED_TARGET_WIDTH = 17;
constexpr int SHARED_TARGET_HEIGHT = 17;
constexpr int SHARED_TARGET_ACTORS = 40;
constexpr int SPATIAL_MARKERS = 80;
constexpr int SPATIAL_HOTSPOT_MARKERS = 6;
constexpr int MODERATE_MOVE_ACTORS = 24;
constexpr int BULK_INVENTORY_ITEM_COUNT = 96;

struct MapFixture {
    std::shared_ptr<CGame> game;
    std::shared_ptr<CMap> map;
    int width = 0;
    int height = 0;
};

class NotificationCountProbe : public CGameObject {
    V_META(NotificationCountProbe, CGameObject, V_METHOD(NotificationCountProbe, onPropertyChanged, void, std::string),
           V_METHOD(NotificationCountProbe, onPropertiesChanged, void, std::set<std::string>),
           V_METHOD(NotificationCountProbe, onInventoryChanged))

  public:
    void onPropertyChanged(std::string property_name) {
        ++property_changed_calls;
        observed_property_names.insert(std::move(property_name));
    }

    void onPropertiesChanged(std::set<std::string> property_names) {
        ++properties_changed_calls;
        observed_property_names.insert(property_names.begin(), property_names.end());
    }

    void onInventoryChanged() { ++inventory_changed_calls; }

    int property_changed_calls = 0;
    int properties_changed_calls = 0;
    int inventory_changed_calls = 0;
    std::set<std::string> observed_property_names;
};

void drain_event_loop() {
    auto loop = vstd::event_loop<>::instance();
    for (int i = 0; i < 5; ++i) {
        loop->run();
    }
}

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
    return game_async::run(actor->getController()->controlAsync(actor), game_async::WaitMode::PostedWork);
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

void add_navigation_edge(const MapFixture &fixture, Coords source, Coords target,
                         std::optional<std::string> source_object_name = std::nullopt) {
    CNavigationEdge edge;
    edge.source = source;
    edge.target = target;
    edge.enabled = true;
    edge.sourceObjectName = std::move(source_object_name);
    fixture.map->registerNavigationEdge(std::move(edge));
}

void testSuspendedPlayerNavigationWorkIsBounded() {
    constexpr int ATTEMPTS = 128;
    auto fixture = make_open_map(9, 3);
    fixture.game->getObjectHandler()->registerType("CPlayerController",
                                                   [] { return std::make_shared<CPlayerController>(); });
    fixture.game->getObjectHandler()->registerType("CPlayerFightController",
                                                   [] { return std::make_shared<CPlayerFightController>(); });
    auto player = std::make_shared<CPlayer>();
    player->setGame(fixture.game);
    player->setBaseStats(make_actor_stats());
    player->setLevelStats(std::make_shared<CStats>());
    player->setHp(20);
    fixture.map->setPlayer(player);
    const Coords origin(0, 1, 0), goal(8, 1, 0);
    player->relocateWithoutMoveHooks(origin);
    auto controller = std::dynamic_pointer_cast<CPlayerController>(player->getController());
    expect_true(controller != nullptr, "the suspension guard requires the native player movement controller");
    if (!controller) {
        fixture.game->getContext()->shutdown();
        return;
    }
    auto navigation = fixture.map->getNavigationService();
    const auto cold_searches = navigation->searchCount();
    controller->setTarget(player, goal);
    expect_true(navigation->searchCount() == cold_searches + 1 && !controller->isCompleted(player),
                "the fixed open map must produce one real native route before suspension");
    controller->setMovementSuspended(true);
    const auto serial = controller->getRequestSerial();
    const auto overlays = controller->getOverlayLookupCount();
    const auto searches = navigation->searchCount();
    const auto used = navigation->budget()->used();
    const auto peak = navigation->budget()->peak();
    const auto flows = performance_guard::targetFlowCacheSize();
    const auto revision = fixture.map->getNavigationRevision();
    const auto objects = fixture.map->getObjects().size();
    const auto cache_entries = fixture.map->getObjectCacheEntryCountForTesting();
    const auto tiles = fixture.map->getTiles().size();
    const auto turn = fixture.map->getTurn();
    int idle_steps = 0, hidden_overlays = 0, completed_routes = 0;
    for (int attempt = 0; attempt < ATTEMPTS; ++attempt) {
        controller->setTarget(player, Coords(8, attempt % 3, 0));
        idle_steps += resolve_step(player) == origin;
        hidden_overlays += !controller->isOnPath(player, goal).first;
        controller->onStepCommitted(player, goal);
        controller->interrupt(player);
        completed_routes += controller->isCompleted(player);
    }
    fixture.map->move();
    const auto disabled_searches = navigation->searchCount() - searches;
    const auto disabled_serial_delta = controller->getRequestSerial() - serial;
    expect_true(idle_steps == ATTEMPTS && hidden_overlays == ATTEMPTS && completed_routes == ATTEMPTS &&
                    player->getCoords() == origin && fixture.map->getTurn() == turn + 1,
                "128 disabled native requests, plans and overlay probes must remain idle without suppressing turns");
    expect_true(
        controller->getRequestSerial() == serial && controller->getOverlayLookupCount() == overlays &&
            navigation->searchCount() == searches && navigation->budget()->used() == used &&
            navigation->budget()->peak() == peak && performance_guard::targetFlowCacheSize() == flows,
        "disabled movement must not churn route serials or grow path searches, live bytes, peak bytes or flows");
    expect_true(fixture.map->getNavigationRevision() == revision && fixture.map->getObjects().size() == objects &&
                    fixture.map->getObjectCacheEntryCountForTesting() == cache_entries &&
                    fixture.map->getTiles().size() == tiles,
                "disabled movement must preserve navigation revision and map/cache cardinality");
    controller->setMovementSuspended(false);
    controller->setTarget(player, goal);
    fixture.map->move();
    expect_true(navigation->searchCount() == searches + 1 && controller->getRequestSerial() == serial + 1 &&
                    player->getCoords() == Coords(1, 1, 0) && fixture.map->getTurn() == turn + 2 &&
                    fixture.map->getNavigationRevision() == revision + 1,
                "one enabled request must restore exactly one ordinary path search, committed step and turn");
    std::cout << "player suspension guard: disabledRequests=" << ATTEMPTS << " idlePlans=" << idle_steps
              << " hiddenOverlays=" << hidden_overlays << " disabledSearches=" << disabled_searches
              << " disabledRouteSerialDelta=" << disabled_serial_delta
              << " enabledSearches=" << navigation->searchCount() - searches << " enabledMoves=1\n";
    fixture.game->getContext()->shutdown();
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
    performance_guard::resetMapCoordinateLookupProbe();
    std::vector<vstd::task_handle<Coords>> pending;
    for (const auto &actor : actors) {
        pending.push_back(fixture.game->getContext()->spawnTask(actor->getController()->controlAsync(actor)));
    }
    std::vector<Coords> steps;
    for (const auto &task : pending) {
        steps.push_back(game_async::wait(task, game_async::WaitMode::PostedWork));
    }
    const auto cold_probes = performance_guard::mapCoordinateLookupProbeCount();
    performance_guard::disableMapCoordinateLookupProbe();
    for (std::size_t i = 0; i < actors.size(); ++i) {
        const auto &actor = actors[i];
        const auto start = fixture.map->normalizeCoords(actor->getCoords());
        const auto step = fixture.map->normalizeCoords(steps[i]);
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

    pending.clear();
    performance_guard::resetMapCoordinateLookupProbe();
    for (const auto &actor : actors) {
        pending.push_back(fixture.game->getContext()->spawnTask(actor->getController()->controlAsync(actor)));
    }
    for (const auto &task : pending) {
        game_async::wait(task, game_async::WaitMode::PostedWork);
    }
    const auto warm_probes = performance_guard::mapCoordinateLookupProbeCount();
    performance_guard::disableMapCoordinateLookupProbe();
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "repeated shared-goal reads should keep reusing the cached target flow field");
    // Unique actor cells are inspected at most once per adjacent flood cell, plus
    // goal/step validation. Warm requests need only the goal and step checks.
    expect_true(cold_probes <= SHARED_TARGET_ACTORS * 8,
                "concurrent cold requests must keep coordinate lookup work bounded by one shared flood");
    expect_true(warm_probes <= SHARED_TARGET_ACTORS * 2,
                "concurrent warm requests must reuse the settled flood without expanding it again");
    std::cout << "Shared target flow coordinate probes: cold=" << cold_probes << "/" << SHARED_TARGET_ACTORS * 8
              << " warm=" << warm_probes << "/" << SHARED_TARGET_ACTORS * 2 << "\n";
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
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "object navigation changes should repair the existing target field");
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
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "tile navigation changes should repair the existing target field");
}

void test_navigation_edge_removal_invalidates_target_navigation() {
    auto fixture = make_open_map(5, 3);
    const Coords start_coords(0, 1, 0);
    const Coords goal_coords(4, 1, 0);
    auto goal = make_object(fixture, "edgeInvalidationGoal", goal_coords);
    auto actor = make_actor(fixture, "edgeInvalidationActor", start_coords, "edgeInvalidationGoal");

    for (int x = 1; x < 4; ++x) {
        for (int y = 0; y < fixture.height; ++y) {
            replace_tile(fixture, Coords(x, y, 0), false, "edgeInvalidationWall");
        }
    }

    add_object(fixture, goal);
    add_object(fixture, actor);
    add_navigation_edge(fixture, start_coords, goal_coords, "edgeShortcut");

    const auto revision_with_edge = fixture.map->getNavigationRevision();
    performance_guard::clearTargetFlowCache();
    const auto shortcut_step = fixture.map->normalizeCoords(resolve_step(actor));
    expect_true(shortcut_step == goal_coords, "edge-invalidation path should initially use the authored edge");
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "edge-invalidation warm path should build one target flow field");

    const auto repeated_shortcut_step = fixture.map->normalizeCoords(resolve_step(actor));
    expect_true(repeated_shortcut_step == goal_coords, "unchanged edge topology should reuse the authored edge");
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "unchanged edge topology should keep reusing the cached target flow field");

    expect_true(
        fixture.map->removeNavigationEdge(start_coords, goal_coords, std::optional<std::string>("edgeShortcut")),
        "removing the authored edge should report success");
    expect_true(fixture.map->getNavigationRevision() == revision_with_edge + 1,
                "removing the authored edge should bump navigation revision exactly once");

    const auto blocked_step = fixture.map->normalizeCoords(resolve_step(actor));
    expect_true(blocked_step == start_coords, "target navigation should stop after the only edge route is removed");
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "edge topology rebuild should replace the contents of the existing target field");
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

class StationaryTurnFrameProbe : public CMapObject {
  public:
    explicit StationaryTurnFrameProbe(int &callbacks) : callbacks(callbacks) {}

    void onTurn(std::shared_ptr<CGameEvent>) override {
        ++turns;
        ++callbacks;
    }

    int turns = 0;

  private:
    int &callbacks;
};

void testStationaryMapTurnsCompleteBeforeRendering() {
    constexpr int OBJECTS = 128;
    constexpr int TURNS = 4;
    constexpr std::size_t READY_PASS_BUDGET = 1024;
    int callbacks = 0;
    auto fixture = make_open_map(16, 8);
    auto context = fixture.game->getContext();
    std::vector<std::shared_ptr<StationaryTurnFrameProbe>> probes;
    for (int index = 0; index < OBJECTS; ++index) {
        auto object = std::make_shared<StationaryTurnFrameProbe>(callbacks);
        object->setGame(fixture.game);
        object->setName("stationaryTurnFrameProbe" + std::to_string(index));
        object->setCanStep(true);
        object->setCoords(Coords(index % 16, index / 16, 0));
        add_object(fixture, object);
        probes.push_back(object);
    }
    auto loop = vstd::event_loop<>::instance();
    loop->runUntilIdle(READY_PASS_BUDGET);
    const auto pending_before = loop->getPendingTaskCount();
    const auto conditional_before = loop->getConditionalTaskCount();
    const auto delayed_before = loop->getDelayedTaskCount();
    const auto frame_callbacks_before = loop->getFrameCallbackCount();
    const auto revision_before = fixture.map->getNavigationRevision();
    const auto initial_turn = fixture.map->getTurn();
    game_async::FramePumpBudget budget;
    budget.maxReadyPasses = READY_PASS_BUDGET;
    budget.maxReadyTime = std::nullopt;
    int frames = 0;
    int complete_frames = 0;
    for (int turn = 0; turn < TURNS; ++turn) {
        const auto callbacks_before = callbacks;
        const auto frames_before = frames;
        int callbacks_at_frame = 0;
        auto movement = context->spawnTask(fixture.map->moveAsync());
        auto frame = loop->connectFrameCallback([&](int) {
            ++frames;
            callbacks_at_frame = callbacks - callbacks_before;
            if (movement.finished() && fixture.map->getTurn() == initial_turn + turn + 1 && !fixture.map->isMoving()) {
                ++complete_frames;
            }
        });
        const bool running = game_async::runFrame(*loop, budget);
        frame.reset();
        expect_true(running && frames == frames_before + 1,
                    "one bounded pump must render exactly one frame for a stationary map turn");
        expect_true(callbacks_at_frame == OBJECTS && complete_frames == turn + 1,
                    "all 128 onTurn callbacks and the turn commit must finish before that frame renders");
        expect_true(movement.finished(), "128 stationary map objects must fit within the fixed ready-pass budget");
        // Drain a failing implementation without adding frames or leaving references to this fixture queued.
        loop->runUntilIdle(READY_PASS_BUDGET * 4);
        if (!movement.finished()) {
            context->shutdown();
            loop->runUntilIdle(READY_PASS_BUDGET * 4);
            return;
        }
        movement.get();
        expect_true(callbacks == (turn + 1) * OBJECTS && fixture.map->getTurn() == initial_turn + turn + 1 &&
                        !fixture.map->isMoving(),
                    "each stationary turn must dispatch exactly one callback per object and commit exactly once");
        expect_true(loop->getPendingTaskCount() == pending_before &&
                        loop->getConditionalTaskCount() == conditional_before &&
                        loop->getDelayedTaskCount() == delayed_before &&
                        loop->getFrameCallbackCount() == frame_callbacks_before,
                    "a stationary turn must release its continuations without growing event-loop registrations");
    }
    for (int index = 0; index < OBJECTS; ++index) {
        expect_true(probes[index]->turns == TURNS && probes[index]->getCoords() == Coords(index % 16, index / 16, 0),
                    "stationary objects must receive four callbacks without changing position");
    }
    expect_true(fixture.map->getNavigationRevision() == revision_before &&
                    fixture.map->getObjects().size() == OBJECTS &&
                    fixture.map->getObjectCacheEntryCountForTesting() == OBJECTS,
                "stationary turns must preserve navigation and object/cache cardinality");
    std::cout << "stationary map turn frame guard: objects=" << OBJECTS << " turns=" << TURNS
              << " callbacks=" << callbacks << " callbackBudget=" << OBJECTS * TURNS << " frames=" << frames
              << " frameBudget=" << TURNS << " completedBeforeFrame=" << complete_frames
              << " readyPassBudget=" << READY_PASS_BUDGET << "\n";
    context->shutdown();
    loop->runUntilIdle(READY_PASS_BUDGET);
}

void testMovementBatchInteractionSchedulingIsLinear() {
    constexpr int STEPS = 64;
    constexpr int REUSE_PASSES = 4;
    constexpr std::size_t CELLS_PER_STEP = 10;
    auto fixture = make_open_map(1, 1);
    fixture.map->setXBounds({{0, STEPS * 5}});
    fixture.map->setYBounds({{0, 8}});
    const auto tiles_before = fixture.map->getTiles().size();
    const auto revision_before = fixture.map->getNavigationRevision();
    CMovementBatch distant;
    std::size_t maximum_cells = 0;
    int distant_groups = 0;
    for (int pass = 0; pass < REUSE_PASSES; ++pass) {
        distant.clear();
        expect_true(distant.cellCount() == 0, "reusing a movement batch must release the previous interaction cells");
        int groups = 1;
        for (int step = 0; step < STEPS; ++step) {
            const Coords origin(2 + step * 5, 2, 0);
            const auto cells = CMovementBatch::interactionCells(*fixture.map, origin, origin + EAST);
            expect_true(!cells.empty() && cells.size() <= CELLS_PER_STEP,
                        "each movement footprint must contain at most ten normalized endpoint-neighbor cells");
            const auto probes_before = distant.probeCount();
            if (distant.conflicts(cells)) {
                ++groups;
                distant.clear();
            }
            expect_true(distant.probeCount() - probes_before <= CELLS_PER_STEP,
                        "conflict lookup must probe at most ten cells independently of the batch actor count");
            distant.add(cells);
            maximum_cells = std::max(maximum_cells, distant.cellCount());
        }
        expect_true(groups == 1, "64 distant moves must share one presentation group on every reuse pass");
        expect_true(distant.cellCount() <= STEPS * CELLS_PER_STEP,
                    "batch interaction storage must remain bounded by the current fixed movement workload");
        distant_groups += groups;
    }
    expect_true(distant.probeCount() <= STEPS * REUSE_PASSES * CELLS_PER_STEP &&
                    distant.insertionCount() <= STEPS * REUSE_PASSES * CELLS_PER_STEP,
                "repeated distant movement scheduling must stay within linear probe and insertion budgets");
    distant.clear();
    expect_true(distant.cellCount() == 0, "a finished movement batch must retain no active interaction cells");

    CMovementBatch contact;
    int contact_groups = 1;
    for (int step = 0; step < STEPS; ++step) {
        const Coords origin(2 + step * 2, 5, 0);
        const auto cells = CMovementBatch::interactionCells(*fixture.map, origin, origin + EAST);
        const auto probes_before = contact.probeCount();
        if (contact.conflicts(cells)) {
            ++contact_groups;
            contact.clear();
        }
        expect_true(contact.probeCount() - probes_before <= CELLS_PER_STEP,
                    "nearby interaction checks must keep the same per-step probe budget");
        contact.add(cells);
    }
    expect_true(contact_groups == STEPS, "a chain of contacting movement footprints must remain sequential");
    expect_true(contact.probeCount() <= STEPS * CELLS_PER_STEP && contact.insertionCount() <= STEPS * CELLS_PER_STEP &&
                    contact.cellCount() <= CELLS_PER_STEP,
                "sequential contact groups must release prior cells without quadratic scheduling work");
    contact.clear();
    expect_true(contact.cellCount() == 0 && fixture.map->getTiles().size() == tiles_before &&
                    fixture.map->getNavigationRevision() == revision_before,
                "presentation grouping must clean its cells without materializing or changing map terrain");
    std::cout << "movement batch interaction guard: steps=" << STEPS << " reusePasses=" << REUSE_PASSES
              << " distantGroups=" << distant_groups << " distantGroupBudget=" << REUSE_PASSES
              << " contactGroups=" << contact_groups << " probes=" << distant.probeCount()
              << " probeBudget=" << STEPS * REUSE_PASSES * CELLS_PER_STEP << " insertions=" << distant.insertionCount()
              << " maxCells=" << maximum_cells << " contactProbes=" << contact.probeCount()
              << " perStepProbeBudget=" << CELLS_PER_STEP << "\n";
    fixture.game->getContext()->shutdown();
}

class PlannedMoveWorkProbe : public CController {
  public:
    explicit PlannedMoveWorkProbe(std::vector<std::shared_ptr<CCreature>> &order) : order(order) {}

    vstd::task<Coords> controlAsync(std::shared_ptr<CCreature> creature) override {
        ++plans;
        order.push_back(creature);
        const auto current = creature->getCoords();
        co_return Coords((current.x + 1) % 8, current.y, current.z);
    }

    void onStepCommitted(std::shared_ptr<CCreature> creature, const Coords &) override {
        ++commits;
        if (afterCommit) {
            afterCommit(creature);
        }
    }

    void interrupt(std::shared_ptr<CCreature>) override { ++interrupts; }

    void onTurnEnded(std::shared_ptr<CCreature>) override { ++endedTurns; }

    std::function<void(std::shared_ptr<CCreature>)> afterCommit;
    int plans = 0;
    int commits = 0;
    int interrupts = 0;
    int endedTurns = 0;

  private:
    std::vector<std::shared_ptr<CCreature>> &order;
};

void testStalePlannedMapMoveWorkIsBounded() {
    constexpr int TURNS = 4;
    constexpr int ACTORS = MODERATE_MOVE_ACTORS;
    auto fixture = make_open_map(8, ACTORS);
    std::vector<std::shared_ptr<PlannedMoveWorkProbe>> probes;
    std::vector<std::shared_ptr<CCreature>> actors;
    std::vector<std::shared_ptr<CCreature>> planned_order;
    planned_order.reserve(ACTORS);
    std::shared_ptr<CCreature> stale_actor;
    int relocations = 0;
    for (int index = 0; index < ACTORS; ++index) {
        auto actor = make_actor(fixture, "plannedMoveActor" + std::to_string(100 + index), Coords(0, index, 0), "");
        auto probe = std::make_shared<PlannedMoveWorkProbe>(planned_order);
        probe->afterCommit = [&](const std::shared_ptr<CCreature> &committer) {
            if (committer != planned_order.front()) {
                return;
            }
            stale_actor = planned_order.back();
            const auto current = stale_actor->getCoords();
            stale_actor->relocateWithoutMoveHooks(Coords((current.x + 2) % 8, current.y, current.z));
            ++relocations;
        };
        actor->setController(probe);
        add_object(fixture, actor);
        actors.push_back(actor);
        probes.push_back(probe);
    }
    const auto revision = fixture.map->getNavigationRevision();
    const auto turn = fixture.map->getTurn();
    const auto objects = fixture.map->getObjects().size();
    for (int iteration = 0; iteration < TURNS; ++iteration) {
        planned_order.clear();
        fixture.map->move();
        expect_true(planned_order.size() == ACTORS && stale_actor &&
                        stale_actor->getPosX() == ((iteration + 1) * 2) % 8,
                    "the last planned actor must retain its actual relocation without a stale commit");
        expect_true(fixture.map->getTurn() == turn + iteration + 1 && !fixture.map->isMoving(),
                    "discarding one stale plan must complete exactly one turn per fixed iteration");
    }
    int plans = 0;
    int commits = 0;
    int ended_turns = 0;
    for (int index = 0; index < ACTORS; ++index) {
        const auto &probe = probes[index];
        plans += probe->plans;
        commits += probe->commits;
        ended_turns += probe->endedTurns;
        expect_true(probe->plans == TURNS && probe->endedTurns == TURNS,
                    "each registered actor must receive one plan and one end callback per turn");
        expect_true(probe->commits == (actors[index] == stale_actor ? 0 : TURNS) &&
                        probe->interrupts == (actors[index] == stale_actor ? TURNS : 0),
                    "only the relocated actor's stale plan must be interrupted, without duplicate work");
    }
    expect_true(relocations == TURNS && plans == ACTORS * TURNS && ended_turns == ACTORS * TURNS &&
                    commits == (ACTORS - 1) * TURNS,
                "24 actors over four turns must perform 96 plans/end callbacks and 92 valid commits");
    expect_true(fixture.map->getNavigationRevision() == revision + ACTORS * TURNS,
                "each valid movement or explicit relocation must invalidate navigation exactly once");
    expect_true(fixture.map->getObjects().size() == objects &&
                    fixture.map->getObjectCacheEntryCountForTesting() == objects,
                "stale-plan rejection must preserve object and coordinate-cache cardinality");
    const auto stale_probe =
        stale_actor ? std::dynamic_pointer_cast<PlannedMoveWorkProbe>(stale_actor->getController()) : nullptr;
    expect_true(stale_probe != nullptr, "the work guard must retain the actual relocated actor's controller");
    std::cout << "planned map move work guard: actors=" << ACTORS << " turns=" << TURNS << " plans=" << plans
              << " ends=" << ended_turns << " commits=" << commits << " validCommitBudget=" << (ACTORS - 1) * TURNS
              << " relocations=" << relocations << " staleCommits=" << (stale_probe ? stale_probe->commits : -1)
              << " staleBudget=0\n";
}

void test_bulk_inventory_property_notifications_are_count_bounded() {
    CTypes::register_type_metadata<NotificationCountProbe, CGameObject>();

    auto creature = std::make_shared<CCreature>();
    auto probe = std::make_shared<NotificationCountProbe>();
    creature->connect("propertyChanged", probe, "onPropertyChanged");
    creature->connect("propertiesChanged", probe, "onPropertiesChanged");
    creature->connect("inventoryChanged", probe, "onInventoryChanged");

    std::set<std::shared_ptr<CItem>> items;
    for (int i = 0; i < BULK_INVENTORY_ITEM_COUNT; ++i) {
        auto item = std::make_shared<CItem>();
        item->setName("bulkInventoryItem" + std::to_string(i));
        items.insert(item);
    }

    creature->setItems(items);
    drain_event_loop();

    expect_true(probe->property_changed_calls == 0,
                "bulk inventory replacement should not emit per-item propertyChanged signals");
    expect_true(probe->properties_changed_calls == 1,
                "bulk inventory replacement should emit one batched propertiesChanged signal");
    expect_true(probe->observed_property_names == std::set<std::string>{"items"},
                "bulk inventory property notification should report only the items property");
    expect_true(probe->inventory_changed_calls == BULK_INVENTORY_ITEM_COUNT,
                "legacy inventoryChanged remains item-level until GUI refresh migrates to property notifications");
}

void test_stat_composition_eliminates_repeated_reflective_increments() {
    using namespace stat_composition_fixture;
    constexpr std::size_t reads_per_fixture = 32;
    constexpr std::array<std::size_t, 7> contribution_counts{7, 10, 11, 9, 15, 20, 16};
    std::vector<Fixture> fixtures;
    std::vector<std::shared_ptr<CStats>> expected;
    for (int mode = 0; mode < 7; ++mode) {
        fixtures.push_back(make(mode));
    }
    std::size_t reflective_work = 0;
    {
        IncrementProbe probe;
        for (std::size_t i = 0; i < fixtures.size(); ++i) {
            for (std::size_t read = 0; read < reads_per_fixture; ++read) {
                std::size_t contributions = 0;
                auto result = reflectiveReference(fixtures[i].creature, contributions);
                expect_true(contributions == contribution_counts[i], "reference contribution workload stays fixed");
                if (read == 0) {
                    expected.push_back(result);
                }
            }
        }
        reflective_work = probe.count();
    }
    expect_true(reflective_work == 47872,
                "old public apply performs exactly 17 increments per contribution, even zeros");
    std::size_t private_work = 0;
    {
        IncrementProbe probe;
        expect_true(probe.count() == 0, "reset must start a new stat work sample at zero");
        for (std::size_t i = 0; i < fixtures.size(); ++i) {
            for (std::size_t read = 0; read < reads_per_fixture; ++read) {
                auto result = fixtures[i].creature->getStats();
                expect_true(result->modifier() == expected[i]->modifier() &&
                                result->getMainStat() == expected[i]->getMainStat(),
                            "fixed representative composed and legacy stat reads must retain the reference values");
            }
        }
        private_work = probe.count();
    }
    expect_true(private_work == 0, "private stat composition must perform zero reflective numeric increments");
    expected.front()->incProperty("strength", 0);
    expect_true(performance_guard::numericIncrementProbeCount() == private_work,
                "probe scope must disable observation without changing ordinary property writes");
    std::cout << "stat composition work: 224 reads, reflective increments " << reflective_work << " -> " << private_work
              << '\n';
}

void test_weighted_target_flow_field_is_single_build_and_materialization_bounded() {
    auto fixture = make_open_map(6, 3);
    // Make the row-0 band between the chasers and the goal expensive so the weighted flow field has
    // to route around it; this exercises movement-cost lookups during flow-field construction.
    for (int x = 1; x <= 4; ++x) {
        if (auto tile = fixture.map->getTile(Coords(x, 0, 0))) {
            tile->setMovementCost(30);
        }
    }

    const Coords goal_coords(5, 0, 0);
    add_object(fixture, make_object(fixture, "weightedGoal", goal_coords));

    std::vector<std::shared_ptr<CCreature>> chasers;
    for (int y = 0; y < 3; ++y) {
        auto chaser = make_actor(fixture, "weightedChaser" + std::to_string(y), Coords(0, y, 0), "weightedGoal");
        add_object(fixture, chaser);
        chasers.push_back(chaser);
    }

    const auto revision_before = fixture.map->getNavigationRevision();
    const auto tiles_before = fixture.map->getTiles().size();
    const auto objects_before = fixture.map->getObjects().size();

    performance_guard::clearTargetFlowCache();
    expect_true(performance_guard::targetFlowCacheSize() == 0, "weighted flow cache should start empty");
    for (const auto &chaser : chasers) {
        resolve_step(chaser);
    }

    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "weighted chasers sharing one goal should reuse a single target flow field");
    expect_true(fixture.map->getNavigationRevision() == revision_before,
                "weighted flow-field reads should not mutate the navigation revision");
    expect_true(fixture.map->getTiles().size() == tiles_before,
                "weighted flow-field reads should not materialize extra tiles");
    expect_true(fixture.map->getObjects().size() == objects_before,
                "weighted flow-field reads should not add or remove objects");

    for (const auto &chaser : chasers) {
        resolve_step(chaser);
    }
    expect_true(performance_guard::targetFlowCacheSize() == 1,
                "repeated weighted reads should keep reusing the cached target flow field");
}

class CombatActionCountProbe : public CInteraction {
  public:
    int calls = 0;
    void performAction(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++calls; }
};

class HealingSelectionPotionProbe : public CPotion {
  public:
    void onUse(std::shared_ptr<CGameEvent>) override { ++calls; }

    bool isDisposable() override { return false; }

    std::size_t calls = 0;
};

class HealingSelectionProbeScope {
  public:
    HealingSelectionProbeScope() { performance_guard::resetHealingItemSelectionProbe(); }

    ~HealingSelectionProbeScope() { performance_guard::disableHealingItemSelectionProbe(); }

    HealingSelectionProbeScope(const HealingSelectionProbeScope &) = delete;
    HealingSelectionProbeScope &operator=(const HealingSelectionProbeScope &) = delete;
};

void testHealingItemSelectionWorkAndCallbacksAreBounded() {
    constexpr std::size_t inventoryCount = 96;
    constexpr std::size_t turns = 64;
    auto fixture = make_open_map(2, 1);
    auto actor = make_actor(fixture, "healingActor", Coords(0, 0, 0), "opponent");
    auto opponent = make_actor(fixture, "opponent", Coords(1, 0, 0), "healingActor");
    actor->setNpc(false);
    opponent->setNpc(false);
    auto actorStats = std::make_shared<CStats>();
    actorStats->setMainStat("intelligence");
    actorStats->setStamina(10);
    actor->setBaseStats(actorStats);
    actor->setHp(35);
    auto opponentStats = std::make_shared<CStats>();
    opponentStats->setMainStat("intelligence");
    opponentStats->setStamina(10);
    opponentStats->setDmgMin(16);
    opponentStats->setDmgMax(16);
    opponent->setBaseStats(opponentStats);
    opponent->setHp(70);
    auto attack = std::make_shared<CombatActionCountProbe>();
    attack->setGame(fixture.game);
    attack->setName("attack");
    attack->setTypeId("Attack");
    actor->addAction(attack);
    std::vector<std::shared_ptr<HealingSelectionPotionProbe>> itemProbes;
    std::shared_ptr<HealingSelectionPotionProbe> selected;
    for (std::size_t index = 0; index < 64; ++index) {
        auto potion = std::make_shared<HealingSelectionPotionProbe>();
        potion->setGame(fixture.game);
        potion->setName("heal" + std::to_string(index));
        potion->setPower(index < 32 ? 1 : index == 32 ? 2 : 3);
        potion->addTag(CTag::Heal);
        actor->addItem(potion);
        itemProbes.push_back(potion);
        if (index == 32) {
            selected = potion;
        }
    }
    for (std::size_t index = 0; index < 32; ++index) {
        auto item = std::make_shared<HealingSelectionPotionProbe>();
        item->setGame(fixture.game);
        item->setName("nonHealingItem" + std::to_string(index));
        actor->addItem(item);
        itemProbes.push_back(item);
    }
    const auto inventory = actor->getItems();
    const auto actions = actor->getInteractions();
    const auto effects = actor->getEffects();
    const auto objects = fixture.map->getObjects();
    const int mana = actor->getMana();
    expect_true(inventory.size() == inventoryCount && actor->getHpMax() == 70,
                "healing selection fixture must retain its fixed inventory and health scale");
    auto controller = std::make_shared<CMonsterFightController>();
    HealingSelectionProbeScope probe;
    int renderedFrames = 0;
    auto frameObserver = vstd::event_loop<>::instance()->connectFrameCallback([&](int) { ++renderedFrames; });
    for (std::size_t turn = 0; turn < turns; ++turn) {
        const auto previousCalls = selected->calls;
        expect_true(controller->control(actor, opponent), "healing selection must take one action per turn");
        expect_true(selected->calls == previousCalls + 1,
                    "each healing selection must invoke the exact least viable item once");
    }
    expect_true(renderedFrames == 0,
                "headless item boundaries must not render or pace frames between coroutine continuations");
    const auto visits = performance_guard::healingItemSelectionProbeCount();
    std::size_t itemCalls = 0;
    for (const auto &item : itemProbes) {
        itemCalls += item->calls;
        expect_true(item->calls == (item == selected ? turns : 0),
                    "outpaced weak heals, stronger viable heals, and non-healing items must remain unused");
    }
    expect_true(visits == inventoryCount * turns,
                "healing selection must inspect every fixed inventory entry exactly once per turn");
    expect_true(itemCalls == turns && attack->calls == 0,
                "healing turns must produce one item callback and no attack callbacks");
    expect_true(actor->getItems() == inventory && actor->getInteractions() == actions &&
                    actor->getEffects() == effects && fixture.map->getObjects() == objects,
                "healing selection must not accumulate inventory, actions, effects, or map objects");
    expect_true(actor->getHp() == 35 && actor->getMana() == mana && opponent->getHp() == 70,
                "the counting-only item callback must keep the repeated workload fixed");
    std::cout << "healing item selection guard: inventory=" << inventoryCount << " turns=" << turns
              << " visits=" << visits << " visit budget=" << inventoryCount * turns << " item callbacks=" << itemCalls
              << " callback budget=" << turns << " attack callbacks=" << attack->calls
              << " renderedFrames=" << renderedFrames << " frameBudget=0\n";
}

struct MonsterItemWorkCounters {
    int started = 0;
    int resumed = 0;
    int destroyedFrames = 0;
    int callbacks = 0;
    int disposalChecks = 0;
    int destroyedItems = 0;
};

class MonsterItemWorkProbe : public CPotion {
  public:
    explicit MonsterItemWorkProbe(MonsterItemWorkCounters &counters) : counters(counters) {}
    ~MonsterItemWorkProbe() override { ++counters.destroyedItems; }
    void onUse(std::shared_ptr<CGameEvent>) override { ++counters.callbacks; }
    bool isDisposable() override {
        ++counters.disposalChecks;
        return true;
    }

  private:
    MonsterItemWorkCounters &counters;
};

vstd::task<bool> countedMonsterItemTurn(std::shared_ptr<CMonsterFightController> controller,
                                        std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> opponent,
                                        MonsterItemWorkCounters &counters) {
    struct FrameGuard {
        MonsterItemWorkCounters &counters;
        ~FrameGuard() { ++counters.destroyedFrames; }
    } guard{counters};
    ++counters.started;
    const auto result = co_await controller->controlAsync(std::move(actor), std::move(opponent));
    ++counters.resumed;
    co_return result;
}

void testMonsterItemTurnDispatchAndCleanupAreBounded() {
    constexpr int TURNS = 32;
    constexpr int SNAPSHOT_BUDGET = 8;
    constexpr std::size_t QUEUE_PEAK_BUDGET = 2;
    MonsterItemWorkCounters counters;
    auto fixture = make_open_map(2, 1);
    auto actor = make_actor(fixture, "itemBudgetActor", Coords(0, 0, 0), "opponent");
    auto opponent = make_actor(fixture, "itemBudgetOpponent", Coords(1, 0, 0), "itemBudgetActor");
    actor->setHp(actor->getHpMax() / 2);
    auto loop = vstd::event_loop<>::instance();
    loop->runUntilIdle();
    const auto initialPending = loop->getPendingTaskCount();
    auto context = fixture.game->getContext();
    int snapshots = 0;
    int consumptions = 0;
    int cancellations = 0;
    std::size_t queuePeak = 0;
    for (int turn = 0; turn <= TURNS; ++turn) {
        const bool cancel = turn == TURNS;
        auto item = std::make_shared<MonsterItemWorkProbe>(counters);
        item->setGame(fixture.game);
        item->setName("itemTurnBudget" + std::to_string(turn));
        item->setPower(2);
        item->addTag(CTag::Heal);
        actor->addItem(item);
        std::weak_ptr<MonsterItemWorkProbe> itemLifetime = item;
        auto controller = std::make_shared<CMonsterFightController>();
        std::weak_ptr<CMonsterFightController> controllerLifetime = controller;
        auto task = context->spawnTask(countedMonsterItemTurn(controller, actor, opponent, counters));
        controller.reset();
        expect_true(!task.finished() && counters.callbacks == turn,
                    "each item turn must suspend before its one item callback without pumping queued work");
        if (cancel) {
            task.requestStop();
        }
        for (int phase = 0; phase < SNAPSHOT_BUDGET && !task.finished(); ++phase) {
            queuePeak = std::max(queuePeak, loop->getPendingTaskCount() - initialPending);
            loop->runPostedTasks();
            ++snapshots;
        }
        expect_true(task.finished(), "one sequential item chain must finish within eight posted snapshots");
        if (!task.finished()) {
            task.requestStop();
            for (int rescue = 0; rescue < 32 && !task.finished(); ++rescue) {
                loop->runPostedTasks();
            }
        }
        if (!task.finished()) {
            context->shutdown();
            return;
        }
        try {
            const auto used = task.get();
            expect_true(!cancel && used, "an ordinary item turn must report its one completed action");
        } catch (const vstd::task_cancelled &) {
            ++cancellations;
            expect_true(cancel, "only the deliberately cancelled item turn may report cancellation");
        }
        if (cancel) {
            expect_true(actor->hasItem(item), "cancellation before onUse must preserve the unconsumed item");
            actor->removeItem(item);
        } else {
            expect_true(!actor->hasItem(item), "each completed disposable item turn must consume its exact item");
            ++consumptions;
        }
        item.reset();
        expect_true(controllerLifetime.expired() && itemLifetime.expired(),
                    "completed and cancelled native item frames must release their controller and item captures");
        expect_true(loop->getPendingTaskCount() == initialPending && counters.destroyedFrames == turn + 1 &&
                        counters.destroyedItems == turn + 1,
                    "each item turn must drain its continuations and release its frame and item before the next turn");
    }
    expect_true(counters.started == TURNS + 1 && counters.resumed == TURNS && counters.destroyedFrames == TURNS + 1 &&
                    counters.callbacks == TURNS && counters.disposalChecks == TURNS && consumptions == TURNS &&
                    cancellations == 1,
                "32 completed item turns and one cancelled turn must have exact bounded work and cleanup counts");
    // Sequential awaits need one continuation; allow one additional cancellation dispatch, independent of turn count.
    expect_true(queuePeak <= QUEUE_PEAK_BUDGET && snapshots <= (TURNS + 1) * SNAPSHOT_BUDGET,
                "item turn queue growth and continuation snapshots must remain bounded by the fixed workload");
    expect_true(actor->getItems().empty() && fixture.map->getObjects().empty(),
                "item turns must not accumulate inventory or spawn map actors");
    std::cout << "monster item coroutine guard: turns=" << TURNS << " starts=" << counters.started
              << " resumes=" << counters.resumed << " framesDestroyed=" << counters.destroyedFrames
              << " callbacks=" << counters.callbacks << " disposalChecks=" << counters.disposalChecks
              << " consumptions=" << consumptions << " cancellations=" << cancellations << " queuePeak=" << queuePeak
              << " queuePeakBudget=" << QUEUE_PEAK_BUDGET << " snapshots=" << snapshots
              << " snapshotBudget=" << (TURNS + 1) * SNAPSHOT_BUDGET << '\n';
    context->shutdown();
}

void testMonsterRoleCallbackAndStateGrowthAreBounded() {
    auto fixture = make_open_map(2, 1);
    auto actor = make_actor(fixture, "roleActor", Coords(0, 0, 0), "opponent");
    auto opponent = make_actor(fixture, "opponent", Coords(1, 0, 0), "roleActor");
    actor->setNpc(false);
    opponent->setNpc(false);
    auto role = std::make_shared<CCreatureClass>();
    role->setStringProperty("combatRole", "boundedRole");
    actor->setCreatureClass(role);
    auto signature = std::make_shared<CombatActionCountProbe>();
    signature->setGame(fixture.game);
    signature->setName("signature");
    signature->setBoolProperty("enemySignature", true);
    signature->setStringProperty("enemyRole", "boundedRole");
    signature->setStringProperty("enemyRoleTrigger", "opening");
    actor->addAction(signature);
    auto attack = std::make_shared<CombatActionCountProbe>();
    attack->setGame(fixture.game);
    attack->setName("attack");
    attack->setTypeId("Attack");
    actor->addAction(attack);
    for (int i = 0; i < 64; ++i) {
        auto excluded = std::make_shared<CombatActionCountProbe>();
        excluded->setName("excluded" + std::to_string(i));
        excluded->setBoolProperty("enemySignature", true);
        excluded->setStringProperty("enemyRole", "otherRole");
        actor->addAction(excluded);
    }
    const auto actionCount = actor->getInteractions().size();
    auto controller = std::make_shared<CMonsterFightController>();
    constexpr int turns = 200;
    for (int i = 0; i < turns; ++i) {
        expect_true(controller->control(actor, opponent),
                    "bounded role fixture should take exactly one action per turn");
    }
    expect_true(signature->calls == 1 && attack->calls == turns - 1,
                "200 role turns must produce one signature callback and 199 ordinary callbacks");
    expect_true(actor->getInteractions().size() == actionCount && actor->getEffects().empty(),
                "role selection must not accumulate actions or effects across turns");
    expect_true(fixture.map->getObjects().empty(), "combat role selection must not spawn map objects");
}

void testOctobogzPhaseCallbackAndStateGrowthAreBounded() {
    auto fixture = make_open_map(2, 1);
    auto actor = make_actor(fixture, "huntActor", Coords(0, 0, 0), "opponent");
    auto opponent = make_actor(fixture, "opponent", Coords(1, 0, 0), "huntActor");
    actor->setNpc(false);
    opponent->setNpc(false);
    actor->setStringProperty("octobogzCombatRole", "shadow");
    actor->setStringProperty("octobogzCombatPhase", "predator");
    actor->setHp(1);
    actor->setMana(5);
    auto addAction = [actor, &fixture](const std::string &id, int manaCost) {
        auto action = std::make_shared<CombatActionCountProbe>();
        action->setGame(fixture.game);
        action->setName(id);
        action->setTypeId(id);
        action->setManaCost(manaCost);
        actor->addAction(action);
        return action;
    };
    const auto attack = addAction("Attack", 0);
    const auto charge = addAction("octobogzCharge", 0);
    const auto pulse = addAction("octobogzShadowPulse", 5);
    charge->setBoolProperty("enemySignature", true);
    pulse->setBoolProperty("enemySignature", true);
    const auto actionCount = actor->getInteractions().size();
    auto controller = std::make_shared<CMonsterFightController>();
    constexpr int turns = 200;
    for (int i = 0; i < turns; ++i) {
        expect_true(controller->control(actor, opponent), "hunt phases must take one bounded action per turn");
    }
    expect_true(charge->calls == 1 && pulse->calls == 1 && attack->calls == turns - 2,
                "200 hunt turns must produce one warning, one paid pulse, and 198 attacks");
    expect_true(actor->getMana() == 0 && actor->getStringProperty("octobogzCombatPhase") == "spent",
                "bounded hunt phase must consume five mana once");
    expect_true(actor->getInteractions().size() == actionCount && actor->getEffects().empty() &&
                    fixture.map->getObjects().empty(),
                "hunt phase selection must not accumulate actions, effects, or map objects");
}

class EffectTickBudgetProbe : public CEffect {
  public:
    EffectTickBudgetProbe(int index, std::vector<int> &order) : index(index), order(order) {}

    void onEffect() override {
        ++callbacks;
        order.push_back(index);
    }

    int callbacks = 0;

  private:
    int index;
    std::vector<int> &order;
};

void testEffectTickCallbacksAndExpiryAreBounded() {
    constexpr int EFFECTS = 8;
    constexpr int TICKS = 4;
    auto fixture = make_open_map(1, 1);
    auto actor = make_actor(fixture, "unitEffectTickActor", Coords(0, 0, 0), "");
    const auto turn = fixture.map->getTurn();
    std::vector<int> order;
    order.reserve(EFFECTS * TICKS);
    std::vector<std::shared_ptr<EffectTickBudgetProbe>> probes;
    for (int index = EFFECTS - 1; index >= 0; --index) {
        auto effect = std::make_shared<EffectTickBudgetProbe>(index, order);
        effect->setGame(fixture.game);
        effect->setTypeId("unitEffectTick" + std::to_string(index));
        effect->setName("unitEffectTick" + std::to_string(index));
        effect->setDuration(TICKS);
        effect->setCaster(actor);
        effect->setVictim(actor);
        if (index % 2 == 0) {
            effect->addTag(CTag::Buff);
        }
        actor->addEffect(effect);
        probes.push_back(effect);
    }
    const std::vector<int> hurtOrder{0, 2, 4, 6, 1, 3, 5, 7};
    const std::vector<int> fullOrder{1, 3, 5, 7, 0, 2, 4, 6};
    for (int pass = 0; pass < TICKS; ++pass) {
        actor->setHp(actor->getHpMax() - (pass < 2 ? 0 : 1));
        const auto hpBefore = actor->getHp();
        const auto &expectedPass = pass < 2 ? fullOrder : hurtOrder;
        CFightHandler::applyEffects(actor);
        expect_true(order.size() == static_cast<std::size_t>((pass + 1) * EFFECTS),
                    "each effect pass must invoke each live effect exactly once");
        expect_true(order.size() == static_cast<std::size_t>((pass + 1) * EFFECTS) &&
                        std::equal(expectedPass.begin(), expectedPass.end(), order.begin() + pass * EFFECTS),
                    "each effect pass must follow its initial-health tier and canonical identity order");
        expect_true(actor->getHp() == hpBefore, "nonlethal order probes must not change actor health");
    }
    CFightHandler::applyEffects(actor);
    CFightHandler::applyEffects(actor);
    expect_true(actor->getEffects().empty() && order.size() == EFFECTS * TICKS,
                "expiry and a subsequent empty pass must not add callbacks or retain effects");
    for (const auto &effect : probes) {
        expect_true(effect->callbacks == TICKS && effect->getTimeLeft() == 0,
                    "each fixed-duration effect must receive exactly its four scheduled callbacks");
        effect->setCaster(nullptr);
        effect->setVictim(nullptr);
    }
    expect_true(fixture.map->getTurn() == turn && fixture.map->getObjects().empty(),
                "effect tick ordering must not advance map turns or accumulate map objects");
    std::cout << "effect tick guard: effects=" << EFFECTS << " ticks=" << TICKS << " callbacks=" << order.size()
              << " callbackBudget=" << EFFECTS * TICKS << "\n";
}

class DefeatOwnershipBudgetController : public CFightController {
  public:
    int starts = 0;
    int actions = 0;
    int ends = 0;
    void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++starts; }
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        ++actions;
        return false;
    }
    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return true; }
    void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++ends; }
};

void testDefeatResolutionRejectionsAndParticipantClaimsAreBounded() {
    constexpr int RECOVERIES = 4;
    constexpr int DUPLICATES_PER_RECOVERY = 32;
    constexpr int OVERLAPS_PER_RECOVERY = 32;
    auto fixture = make_open_map(5, 1);
    auto context = fixture.game->getContext();
    auto loop = vstd::event_loop<>::instance();
    fixture.map->setBoolProperty("plugin_cityFixedLoot", true);
    auto winner = make_actor(fixture, "boundedDefeatWinner", Coords(0, 0, 0), "");
    auto loser = make_actor(fixture, "boundedDefeatLoser", Coords(1, 0, 0), "");
    auto opponent = make_actor(fixture, "boundedDefeatOpponent", Coords(2, 0, 0), "");
    auto independent = make_actor(fixture, "boundedIndependentActor", Coords(3, 0, 0), "");
    auto independentOpponent = make_actor(fixture, "boundedIndependentOpponent", Coords(4, 0, 0), "");
    for (const auto &actor : {winner, loser, opponent, independent, independentOpponent}) {
        fixture.map->addObject(actor);
    }
    auto blockedController = std::make_shared<DefeatOwnershipBudgetController>();
    auto independentController = std::make_shared<DefeatOwnershipBudgetController>();
    winner->setFightController(blockedController);
    opponent->setFightController(std::make_shared<DefeatOwnershipBudgetController>());
    independent->setFightController(independentController);
    independentOpponent->setFightController(std::make_shared<DefeatOwnershipBudgetController>());
    bool released = false;
    int destructions = 0;
    fixture.map->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
        loser->getName(), "onDestroy", [&released, &destructions, loop](auto, auto) -> vstd::task<void> {
            ++destructions;
            co_await vstd::until(loop, [&released] { return released; });
        }));
    const auto pump = [&](const auto &ready) {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while (!ready() && std::chrono::steady_clock::now() < deadline) {
            loop->runReady();
            game_async::waitForProgress();
        }
        return ready();
    };
    const auto turn = fixture.map->getTurn();
    int duplicateRejections = 0;
    int rejected = 0;
    for (int recovery = 0; recovery < RECOVERIES; ++recovery) {
        if (recovery != 0) {
            fixture.map->addObject(loser);
        }
        loser->setHp(0);
        released = false;
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        expect_true(pump([&] { return destructions == recovery + 1 || owner.finished(); }) && !owner.finished(),
                    "the bounded defeat owner must suspend in the real removal path");
        const auto experience = winner->getExp();
        const auto hp = winner->getHp();
        const auto mana = winner->getMana();
        const auto level = winner->getLevel();
        for (int duplicate = 0; duplicate < DUPLICATES_PER_RECOVERY; ++duplicate) {
            auto attempt = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
            bool rejectedDuplicate = false;
            if (attempt.finished()) {
                try {
                    attempt.get();
                } catch (const std::logic_error &) {
                    rejectedDuplicate = true;
                }
            }
            expect_true(rejectedDuplicate && !owner.finished() && !fixture.map->tryBeginSaveSnapshot(),
                        "a duplicate must reject without displacing the inline recovery or its lease");
            duplicateRejections += rejectedDuplicate;
        }
        for (int overlap = 0; overlap < OVERLAPS_PER_RECOVERY; ++overlap) {
            auto attempt = context->spawnTask(CFightHandler::fightManyResultAsync(winner, {opponent}));
            expect_true(attempt.finished() && attempt.get().outcome == CFightOutcome::Cancelled,
                        "an overlap must reject before starting any shared participant controller");
            ++rejected;
        }
        expect_true(blockedController->starts == 0 && blockedController->actions == 0 && blockedController->ends == 0,
                    "128 rejected overlaps have a deterministic zero controller-work budget");
        const auto disjoint = CFightHandler::fightManyResult(independent, {independentOpponent});
        expect_true(disjoint.outcome == CFightOutcome::Cancelled && independentController->starts == recovery + 1 &&
                        independentController->actions == recovery + 1 && independentController->ends == recovery + 1,
                    "participant ownership must allow bounded independent encounters during suspended recovery");
        released = true;
        expect_true(pump([&] { return owner.finished(); }), "the sole owner must drain its completed recovery");
        if (owner.finished()) {
            owner.get();
        }
        expect_true(destructions == recovery + 1 && winner->getExp() == experience && winner->getHp() == hp &&
                        winner->getMana() == mana && winner->getLevel() == level && opponent->getHp() == 100 &&
                        fixture.map->getObjects().size() == 4 && fixture.map->getTurn() == turn &&
                        fixture.map->tryBeginSaveSnapshot().has_value(),
                    "duplicate admission must add no rewards, recovery callbacks, actor state, objects or turns");
    }
    const auto reopened = CFightHandler::fightManyResult(winner, {opponent});
    expect_true(duplicateRejections == RECOVERIES * DUPLICATES_PER_RECOVERY &&
                    rejected == RECOVERIES * OVERLAPS_PER_RECOVERY && reopened.outcome == CFightOutcome::Cancelled &&
                    blockedController->starts == 1 && blockedController->actions == 1 && blockedController->ends == 1,
                "the last owner must release participant admission for a later ordinary encounter");
    std::cout << "defeat ownership guard: recoveries=" << destructions << " budget=" << RECOVERIES
              << " duplicateRejections=" << duplicateRejections
              << " duplicateBudget=" << RECOVERIES * DUPLICATES_PER_RECOVERY << " overlaps=" << rejected
              << " overlapBudget=" << RECOVERIES * OVERLAPS_PER_RECOVERY
              << " rejectedControllerWork=0 disjoint=" << independentController->actions
              << " disjointBudget=" << RECOVERIES << " actors=" << fixture.map->getObjects().size() << "\n";
    context->shutdown();
}

class MapBindingEpochBudgetProbe : public CGameObject {
    V_META(MapBindingEpochBudgetProbe, CGameObject, V_METHOD(MapBindingEpochBudgetProbe, onBindingChanged, void))

  public:
    int callbacks = 0;
    void onBindingChanged() { ++callbacks; }
};

void testMapBindingEpochQueriesAndPublicationsAreBounded() {
    constexpr int CYCLES = 128;
    constexpr int READS_PER_CYCLE = 4;
    CTypes::register_type_metadata<MapBindingEpochBudgetProbe, CGameObject>();
    auto game = std::make_shared<CGame>();
    auto first = std::make_shared<CMap>();
    auto second = std::make_shared<CMap>();
    first->setGame(game);
    second->setGame(game);
    game->setMap(first);
    auto context = game->getContext();
    const auto generation = context->getTransitionGeneration();
    auto probe = std::make_shared<MapBindingEpochBudgetProbe>();
    probe->setGame(game);
    game->connect("mapBindingChanged", probe, "onBindingChanged");
    auto loop = vstd::event_loop<>::instance();
    const auto pending = loop->getPendingTaskCount();
    const auto delayed = loop->getDelayedTaskCount();
    const auto initial = game->getMapBindingEpoch();
    int reads = 0;
    for (int cycle = 0; cycle < CYCLES; ++cycle) {
        for (int read = 0; read < READS_PER_CYCLE; ++read) {
            expect_true(game->getMapBindingEpoch() == initial + 2 * cycle,
                        "read-only epoch queries must not publish another map");
            ++reads;
        }
        game->setMap(first);
        game->setMap(second);
        game->setMap(second);
        game->setMap(first);
    }
    expect_true(
        reads == CYCLES * READS_PER_CYCLE && probe->callbacks == 2 * CYCLES &&
            game->getMapBindingEpoch() == initial + 2 * CYCLES && game->getMap() == first &&
            context->isTransitionGenerationCurrent(generation) && loop->getPendingTaskCount() == pending &&
            loop->getDelayedTaskCount() == delayed && first->getObjects().empty() && second->getObjects().empty(),
        "fixed epoch queries and publications must retain exact callback, queue, generation and object budgets");
    std::cout << "map binding epoch guard: cycles=" << CYCLES << " reads=" << reads
              << " publications=" << game->getMapBindingEpoch() - initial << " callbacks=" << probe->callbacks
              << " budget-publications=" << 2 * CYCLES << " budget-callbacks=" << 2 * CYCLES << '\n';
    game->disconnect("mapBindingChanged", probe, "onBindingChanged");
    context->shutdown();
}

void testAssignedPlayerQueriesAreMutationAndCallbackBounded() {
    constexpr int READS_PER_PHASE = 256;
    CTypes::register_type<CPlayerController>();
    CTypes::register_type<CPlayerFightController>();
    auto fixture = make_open_map(2, 1);
    auto movement_constructions = std::make_shared<int>(0);
    auto fight_constructions = std::make_shared<int>(0);
    fixture.game->getObjectHandler()->registerType("CPlayerController", [movement_constructions] {
        ++*movement_constructions;
        return std::make_shared<CPlayerController>();
    });
    fixture.game->getObjectHandler()->registerType("CPlayerFightController", [fight_constructions] {
        ++*fight_constructions;
        return std::make_shared<CPlayerFightController>();
    });
    auto player = std::make_shared<CPlayer>();
    player->setGame(fixture.game);
    player->setName("player");
    player->setBaseStats(make_actor_stats());
    player->setLevel(1);
    player->setHp(1);
    auto movement = std::make_shared<CController>();
    auto fight = std::make_shared<CFightController>();
    player->setController(movement);
    player->setFightController(fight);
    fixture.map->addObject(player);
    auto observer = std::make_shared<NotificationCountProbe>();
    observer->setGame(fixture.game);
    fixture.map->connect("propertyChanged", observer, "onPropertyChanged");
    fixture.map->connect("propertiesChanged", observer, "onPropertiesChanged");
    auto loop = vstd::event_loop<>::instance();
    int reads = 0;
    const CMap &observed = *fixture.map;
    for (const bool assigned : {false, true}) {
        if (assigned) {
            fixture.map->attachPlayer(player, Coords(0, 0, 0));
        }
        const auto current_movement = player->getController();
        const auto current_fight = player->getFightController();
        expect_true(*movement_constructions == (assigned ? 1 : 0) && *fight_constructions == (assigned ? 1 : 0),
                    "only actual attachment must construct each session-owned player controller once");
        if (assigned) {
            expect_true(std::dynamic_pointer_cast<CPlayerController>(current_movement) != nullptr &&
                            std::dynamic_pointer_cast<CPlayerFightController>(current_fight) != nullptr,
                        "the assigned query phase requires actual native player controllers, not null fallbacks");
        }
        const auto revision = fixture.map->getNavigationRevision();
        const auto turn = fixture.map->getTurn();
        const auto objects = fixture.map->getObjects();
        const auto triggers = fixture.map->getEventHandler()->getTriggers();
        const auto pending = loop->getPendingTaskCount();
        const auto delayed = loop->getDelayedTaskCount();
        const auto callbacks = observer->property_changed_calls + observer->properties_changed_calls;
        const auto movement_constructions_before = *movement_constructions;
        const auto fight_constructions_before = *fight_constructions;
        for (int read = 0; read < READS_PER_PHASE; ++read) {
            expect_true(observed.getAssignedPlayer() == (assigned ? player : nullptr),
                        "fixed queries must expose assignment without adopting the registered actor");
            ++reads;
        }
        const auto after_objects = fixture.map->getObjects();
        const auto after_triggers = fixture.map->getEventHandler()->getTriggers();
        const auto after_revision = fixture.map->getNavigationRevision();
        const auto after_turn = fixture.map->getTurn();
        const auto after_movement = player->getController();
        const auto after_fight = player->getFightController();
        const auto after_pending = loop->getPendingTaskCount();
        const auto after_delayed = loop->getDelayedTaskCount();
        const auto after_callbacks = observer->property_changed_calls + observer->properties_changed_calls;
        std::cout << "assigned player query phase: assigned=" << assigned << " reads=" << READS_PER_PHASE
                  << " objects=" << objects.size() << '/' << after_objects.size()
                  << " same-objects=" << (after_objects == objects) << " triggers=" << triggers.size() << '/'
                  << after_triggers.size() << " same-triggers=" << (after_triggers == triggers)
                  << " revision=" << revision << '/' << after_revision << " turn=" << turn << '/' << after_turn
                  << " same-movement=" << (after_movement == current_movement)
                  << " same-fight=" << (after_fight == current_fight) << " pending=" << pending << '/' << after_pending
                  << " delayed=" << delayed << '/' << after_delayed << " callbacks=" << callbacks << '/'
                  << after_callbacks << " movement-constructions=" << movement_constructions_before << '/'
                  << *movement_constructions << " fight-constructions=" << fight_constructions_before << '/'
                  << *fight_constructions << '\n';
        expect_true(fixture.map->getObjects() == objects && fixture.map->getEventHandler()->getTriggers() == triggers &&
                        fixture.map->getNavigationRevision() == revision && fixture.map->getTurn() == turn &&
                        player->getController() == current_movement && player->getFightController() == current_fight &&
                        loop->getPendingTaskCount() == pending && loop->getDelayedTaskCount() == delayed &&
                        observer->property_changed_calls + observer->properties_changed_calls == callbacks,
                    "256 queries per phase must add zero registry/controller/hook/turn/queue/callback work");
        expect_true(*movement_constructions == movement_constructions_before &&
                        *fight_constructions == fight_constructions_before,
                    "assigned-player queries must add zero session controller constructions");
        if (!assigned) {
            expect_true(current_movement == movement && current_fight == fight,
                        "unassigned observation must preserve even non-player controller identities");
        }
    }
    expect_true(reads == 2 * READS_PER_PHASE, "the assigned-player query guard must perform exactly 512 reads");
    std::cout << "assigned player query guard: reads=" << reads << " phases=2 budget-reads=" << 2 * READS_PER_PHASE
              << " budget-registry/controller/hook/turn/queue/callback-deltas=0; observations above\n";
    fixture.map->disconnect("propertyChanged", observer, "onPropertyChanged");
    fixture.map->disconnect("propertiesChanged", observer, "onPropertiesChanged");
    fixture.game->getContext()->shutdown();
}

void testMinimapTerrainCacheBuildsOnlyOnRelevantChanges() {
    constexpr int CACHED_FRAMES = 32;
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");
    auto fixture = make_open_map(8, 8);
    auto gui = std::make_shared<CGui>();
    gui->setGame(fixture.game);
    fixture.game->setGui(gui);
    auto player = std::make_shared<CPlayer>();
    player->setGame(fixture.game);
    player->setBaseStats(make_actor_stats());
    fixture.map->setPlayer(player);
    auto minimap = std::make_shared<CMinimapGraphicsObject>();
    gui->addChild(minimap);
    const auto rect = CUtil::rect(0, 0, 128, 128);

    for (int frame = 0; frame < CACHED_FRAMES; ++frame) {
        minimap->renderObject(gui, rect, 0);
    }
    expect_true(minimap->getTerrainTextureBuildCount() == 1, "unchanged minimap frames must build one terrain texture");
    expect_true(gui->getRenderContext().getStats().successfulCopies == CACHED_FRAMES,
                "each cached minimap frame must copy its valid terrain texture");

    player->moveTo(3, 4, 0);
    minimap->renderObject(gui, rect, 0);
    expect_true(minimap->getTerrainTextureBuildCount() == 1, "moving a player marker must reuse the terrain texture");
    fixture.map->getTile(Coords(4, 4, 0))->setTileType("grass");
    minimap->renderObject(gui, rect, 0);
    expect_true(minimap->getTerrainTextureBuildCount() == 2, "changing terrain must rebuild the minimap texture once");
    const auto resized = CUtil::rect(0, 0, 129, 128);
    minimap->renderObject(gui, resized, 0);
    expect_true(minimap->getTerrainTextureBuildCount() == 3,
                "changing minimap dimensions must rebuild its texture once");
    expect_true(gui->getRenderContext().getStats().successfulCopies == CACHED_FRAMES + 3,
                "marker, terrain, and size changes must retain valid rendering");

    auto replacement = std::make_shared<CGui>();
    replacement->setGame(fixture.game);
    gui->removeChild(minimap);
    replacement->addChild(minimap);
    minimap->renderObject(replacement, resized, 0);
    expect_true(minimap->getTerrainTextureBuildCount() == 4, "changing a live GUI owner must rebuild the texture once");
    expect_true(replacement->getRenderContext().getStats().successfulCopies == 1,
                "the replacement GUI must receive its own valid terrain texture");
    std::cout << "minimap terrain cache guard: cells=64 frames=" << CACHED_FRAMES + 4
              << " builds=" << minimap->getTerrainTextureBuildCount() << " budget=4\n";
}


} // namespace

void run_engine_hotspot_performance_tests() {
    std::optional<pybind11::scoped_interpreter> interpreter;
    if (!Py_IsInitialized()) {
        interpreter.emplace();
    }

    test_stat_composition_eliminates_repeated_reflective_increments();
    testSuspendedPlayerNavigationWorkIsBounded();
    test_many_target_controllers_share_one_goal_without_mutating_navigation();
    test_weighted_target_flow_field_is_single_build_and_materialization_bounded();
    test_relevant_object_move_invalidates_target_navigation();
    test_relevant_tile_change_invalidates_target_navigation();
    test_navigation_edge_removal_invalidates_target_navigation();
    test_irrelevant_metadata_activity_does_not_invalidate_navigation();
    test_coordinate_cache_lookup_cardinality_and_move_updates();
    test_moderate_actor_map_move_turn_state_and_revision_bounds();
    testStationaryMapTurnsCompleteBeforeRendering();
    testMovementBatchInteractionSchedulingIsLinear();
    testStalePlannedMapMoveWorkIsBounded();
    test_bulk_inventory_property_notifications_are_count_bounded();
    testHealingItemSelectionWorkAndCallbacksAreBounded();
    testMonsterItemTurnDispatchAndCleanupAreBounded();
    testMonsterRoleCallbackAndStateGrowthAreBounded();
    testOctobogzPhaseCallbackAndStateGrowthAreBounded();
    testEffectTickCallbacksAndExpiryAreBounded();
    testDefeatResolutionRejectionsAndParticipantClaimsAreBounded();
    testMapBindingEpochQueriesAndPublicationsAreBounded();
    testAssignedPlayerQueriesAreMutationAndCallbackBounded();
    testMinimapTerrainCacheBuildsOnlyOnRelevantChanges();
}
