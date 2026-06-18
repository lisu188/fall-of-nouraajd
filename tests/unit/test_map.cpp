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

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CProvider.h"
#include "core/CSceneManager.h"
#include "object/CGameObject.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "veventloop.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <memory>
#include <set>

namespace {

void pump_event_loop_iterations(int iterations = 10) {
    auto loop = vstd::event_loop<>::instance();
    for (int i = 0; i < iterations; ++i) {
        loop->run();
    }
}

Coords first_adjacent_walkable(const std::shared_ptr<CMap> &map, Coords origin) {
    for (const auto &delta : {EAST, WEST, SOUTH, NORTH}) {
        Coords target(origin.x + delta.x, origin.y + delta.y, origin.z + delta.z);
        if (map->canStep(target)) {
            return target;
        }
    }
    return origin;
}

void test_scene_manager_state_duplicate_and_player_transfer() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto old_map = game->getMap();
    auto player = old_map->getPlayer();
    old_map->setTurn(17);

    auto manager = game->getSceneManager();
    expect_true(manager->getTransitionState() == CSceneManager::TransitionState::Idle,
                "scene manager should start idle");
    expect_true(!manager->isTransitionPending(), "idle scene manager should not report pending transitions");
    expect_true(manager->requestMapChange(game, "ritual"), "scene manager should accept a first transition request");
    expect_true(manager->getTransitionState() == CSceneManager::TransitionState::TransitionPending,
                "accepted scene transition should enter pending state before the event loop runs");
    expect_true(manager->isTransitionPending(), "pending scene manager should report an active transition");
    expect_true(manager->getPendingMapName() == "ritual", "scene manager should expose the queued target");
    expect_true(!manager->requestMapChange(game, "siege"),
                "scene manager should reject duplicate transition requests while pending");
    expect_true(manager->getPendingMapName() == "ritual", "duplicate request should not replace the pending target");
    expect_true(game->getMap() == old_map, "transition should not replace the active map before the event loop runs");

    pump_event_loop_iterations();

    auto new_map = game->getMap();
    expect_true(new_map != old_map, "transition should replace the active map after the event loop runs");
    expect_true(new_map->getMapName() == "ritual", "first queued transition should determine the destination map");
    expect_true(new_map->getTurn() == 17, "scene transition should preserve the old map turn");
    expect_true(new_map->getPlayer() == player, "scene transition should transfer the same player object");
    expect_true(player->getCoords() == new_map->getEntry(), "transferred player should land at the target map entry");
    expect_true(manager->getTransitionState() == CSceneManager::TransitionState::Idle,
                "scene manager should return to idle after transition completion");
    expect_true(!manager->isTransitionPending(), "completed scene transition should clear pending state");
    expect_true(manager->getPendingMapName().empty(), "completed scene transition should clear pending map name");
}

void test_scene_manager_repeated_transitions_and_controller_usability() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto player = game->getMap()->getPlayer();
    game->getMap()->setTurn(5);

    game->getSceneManager()->requestMapChange(game, "ritual");
    pump_event_loop_iterations();
    auto ritual_map = game->getMap();
    expect_true(ritual_map->getMapName() == "ritual", "first sequential scene transition should reach ritual");
    expect_true(ritual_map->getPlayer() == player, "first sequential scene transition should keep player identity");

    auto controller = std::dynamic_pointer_cast<CPlayerController>(player->getController());
    expect_true(controller != nullptr,
                "player controller should be reset to a usable CPlayerController after transition");
    const auto target = first_adjacent_walkable(ritual_map, player->getCoords());
    if (target != player->getCoords()) {
        controller->setTarget(player, target);
        ritual_map->move();
        expect_true(player->getCoords() == target, "player controller should move the player after transition");
    }

    const int expected_turn = ritual_map->getTurn() + 3;
    ritual_map->setTurn(expected_turn);
    game->getSceneManager()->requestMapChange(game, "test");
    pump_event_loop_iterations();

    expect_true(game->getMap()->getMapName() == "test", "second sequential scene transition should reach test map");
    expect_true(game->getMap()->getPlayer() == player,
                "second sequential scene transition should keep player identity");
    expect_true(game->getMap()->getTurn() == expected_turn,
                "second sequential scene transition should copy the updated turn");
    expect_true(game->getSceneManager()->getTransitionState() == CSceneManager::TransitionState::Idle,
                "scene manager should remain reusable after sequential transitions");
}

void test_scene_manager_null_and_legacy_missing_target_behavior() {
    auto standalone_manager = std::make_shared<CSceneManager>();
    expect_true(!standalone_manager->requestMapChange(nullptr, "ritual"),
                "scene manager should reject transition requests without a game");
    expect_true(standalone_manager->getTransitionState() == CSceneManager::TransitionState::Idle,
                "null-game rejection should leave scene manager idle");
    CGameLoader::changeMap(nullptr, "ritual");

    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto old_player = game->getMap()->getPlayer();
    game->getMap()->setTurn(19);

    expect_true(game->getSceneManager()->requestMapChange(game, ""),
                "scene manager should preserve loader compatibility for empty map names");
    pump_event_loop_iterations();

    expect_true(game->getMap() != nullptr, "empty-map compatibility path should still install a map object");
    expect_true(game->getMap()->getMapName().empty(), "empty-map compatibility path should keep the blank map name");
    expect_true(game->getMap()->getPlayer() == old_player,
                "empty-map compatibility path should still transfer the existing player");
    expect_true(game->getMap()->getTurn() == 19, "empty-map compatibility path should copy the old turn");
    expect_true(game->getSceneManager()->getTransitionState() == CSceneManager::TransitionState::Idle,
                "empty-map compatibility path should reset transition state");

    game->getMap()->setTurn(21);

    expect_true(game->getSceneManager()->requestMapChange(game, "missingSceneManagerMap"),
                "scene manager should preserve loader compatibility for missing map names");
    pump_event_loop_iterations();

    expect_true(game->getMap() != nullptr, "missing-map compatibility path should still install a map object");
    expect_true(game->getMap()->getMapName().empty(), "missing-map compatibility path should keep the blank map name");
    expect_true(game->getMap()->getPlayer() == old_player,
                "missing-map compatibility path should still transfer the existing player");
    expect_true(game->getMap()->getTurn() == 21, "missing-map compatibility path should copy the old turn");
    expect_true(game->getSceneManager()->getTransitionState() == CSceneManager::TransitionState::Idle,
                "missing-map compatibility path should reset transition state");
}

void test_map_tiles_bounds_wrapping_and_object_cache() {
    auto map = std::make_shared<CMap>();
    map->setMapName("coverageMap");
    map->setTurn(7);
    map->setEntryX(1);
    map->setEntryY(2);
    map->setEntryZ(3);
    expect_true(map->getMapName() == "coverageMap", "map name accessors should round-trip values");
    expect_true(map->getTurn() == 7, "map turn accessors should round-trip values");
    expect_true(map->getEntry() == Coords(1, 2, 3), "map entry accessors should expose a single coordinate");

    map->setXBounds({{0, 4}, {1, 2}});
    map->setYBounds({{0, 3}, {2, 5}});
    map->setDefaultTiles({{0, "GroundTile"}});
    map->setOutOfBoundsTiles({{0, "MountainTile"}});
    map->setWrapX({{0, 1}});
    map->setWrapY({{0, 1}});
    expect_true(map->getXBounds().at(0) == 4, "x bounds should be stored by level");
    expect_true(map->getYBounds().at(2) == 5, "y bounds should be stored by level");
    expect_true(map->getDefaultTiles().at(0) == "GroundTile", "default tile ids should be stored by level");
    expect_true(map->getOutOfBoundsTiles().at(0) == "MountainTile", "out-of-bounds tile ids should be stored by level");
    expect_true(map->getWrapX().at(0) == 1 && map->getWrapY().at(0) == 1, "wrapping flags should be stored by level");

    auto bounds = map->getBounds();
    expect_true(bounds.at(0) == std::make_pair(4, 3), "bounds should combine matching x/y levels");
    expect_true(bounds.at(1) == std::make_pair(2, 0), "bounds should include x-only levels");
    expect_true(bounds.at(2) == std::make_pair(0, 5), "bounds should include y-only levels");
    expect_true(map->wrapsX(0) && map->wrapsY(0), "configured wrapped levels should report wrapping");
    expect_true(!map->wrapsX(1) && !map->wrapsY(1), "unconfigured levels should not report wrapping");
    expect_true(map->normalizeCoords(Coords(-1, 4, 0)) == Coords(4, 0, 0),
                "wrapped coordinates should normalize across both axes");

    const auto adjacent = map->getAdjacentCoords(Coords(0, 0, 0), true);
    expect_true(adjacent.size() == 5, "wrapped adjacency should include self and four unique neighbors");
    expect_true(std::find(adjacent.begin(), adjacent.end(), Coords(4, 0, 0)) != adjacent.end(),
                "wrapped adjacency should include the west edge neighbor");
    expect_true(std::find(adjacent.begin(), adjacent.end(), Coords(0, 3, 0)) != adjacent.end(),
                "wrapped adjacency should include the north edge neighbor");
    expect_true(map->getShortestDelta(Coords(0, 0, 0), Coords(4, 3, 0)) == Coords(-1, -1, 0),
                "shortest deltas should prefer wrapped movement when shorter");
    expect_true(map->getDistance(Coords(0, 0, 0), Coords(4, 0, 0)) == 1.0,
                "distance should use wrapped shortest deltas");

    auto floor = std::make_shared<CTile>();
    floor->setTileType("floor");
    floor->setCanStep(true);
    expect_true(!map->addTile(nullptr, 0, 0, 0), "addTile should reject null tiles");
    expect_true(map->addTile(floor, 1, 1, 0), "addTile should store a new tile");
    expect_true(floor->getCoords() == Coords(1, 1, 0), "addTile should synchronize tile coordinates");
    expect_true(!map->addTile(std::make_shared<CTile>(), 1, 1, 0), "addTile should reject duplicate coordinates");
    expect_true(map->contains(1, 1, 0), "contains should find manually added tiles");
    expect_true(map->getTile(1, 1, 0) == floor, "getTile should return existing tiles without creating defaults");
    expect_true(map->canStep(1, 1, 0), "walkable manual tiles should be passable");

    const auto revision_before_move = map->getNavigationRevision();
    map->moveTile(floor, 2, 1, 0);
    expect_true(map->getNavigationRevision() > revision_before_move, "moving a tile should bump navigation revision");
    expect_true(!map->contains(1, 1, 0) && map->contains(2, 1, 0), "moveTile should relocate the tile index");
    expect_true(map->getTile(2, 1, 0) == floor, "moved tiles should be indexed at their new coordinate");
    expect_true(map->getMovementCost(2, 1, 0) == 1, "movement cost should be available for existing tiles");

    auto wall = std::make_shared<CTile>();
    wall->setCanStep(false);
    expect_true(map->addTile(wall, 3, 1, 0), "additional manual tiles should be accepted");
    expect_true(!map->canStep(3, 1, 0), "blocking manual tiles should make coordinates impassable");
    expect_true(!map->canStep(1, 0, 2), "bounded non-wrapped levels should reject out-of-bounds coordinates");

    int visited_tiles = 0;
    map->forTiles([&visited_tiles](std::shared_ptr<CTile>) { visited_tiles++; },
                  [](std::shared_ptr<CTile>) { return true; });
    expect_true(visited_tiles == 2, "forTiles should visit stored tiles");
    map->removeTile(3, 1, 0);
    expect_true(!map->contains(3, 1, 0), "removeTile should erase indexed tiles");

    std::set<std::shared_ptr<CTile>> replacement_tiles;
    replacement_tiles.insert(nullptr);
    replacement_tiles.insert(floor);
    map->setTiles(replacement_tiles);
    expect_true(map->getTiles().size() == 1, "setTiles should ignore null tiles and keep valid tiles");

    auto blocker = std::make_shared<CMapObject>();
    blocker->setName("blockingObject");
    blocker->setCanStep(false);
    blocker->setPosX(2);
    blocker->setPosY(2);
    blocker->setPosZ(0);
    auto marker = std::make_shared<CMapObject>();
    marker->setName("markerObject");
    marker->setCanStep(true);
    marker->setPosX(4);
    marker->setPosY(2);
    marker->setPosZ(0);

    std::set<std::shared_ptr<CMapObject>> objects;
    objects.insert(nullptr);
    objects.insert(blocker);
    objects.insert(marker);
    map->setObjects(objects);
    expect_true(map->getObjects().size() == 2, "setObjects should ignore null objects and index valid objects");
    expect_true(map->getObjectByName("markerObject") == marker, "objects should be searchable by name");
    expect_true(map->getObjectByName("missingObject") == nullptr, "missing object names should return null");
    expect_true(!map->canStep(2, 2, 0), "blocking objects should make coordinates impassable");

    int visited_objects = 0;
    map->forObjects([&visited_objects](std::shared_ptr<CMapObject>) { visited_objects++; },
                    [](std::shared_ptr<CMapObject>) { return true; });
    expect_true(visited_objects == 2, "forObjects should visit indexed objects");

    int marker_visits = 0;
    map->forObjectsAtCoords(
        Coords(4, 2, 0), [&marker_visits](std::shared_ptr<CMapObject>) { marker_visits++; },
        [](std::shared_ptr<CMapObject> object) { return object->getCanStep(); });
    expect_true(marker_visits == 1, "forObjectsAtCoords should filter objects at normalized coordinates");

    const auto old_coords = marker->getCoords();
    marker->setPosX(0);
    marker->setPosY(2);
    map->objectMoved(marker, old_coords, marker->getCoords());
    expect_true(map->getObjectsAtCoords(Coords(4, 2, 0)).empty(),
                "objectMoved should remove stale object cache entries");
    expect_true(map->getObjectsAtCoords(Coords(0, 2, 0)).contains(marker),
                "objectMoved should index objects at their new coordinate");

    auto missing = std::make_shared<CMapObject>();
    missing->setName("missingObject");
    map->removeObject(nullptr);
    map->removeObject(missing);
    map->removeObjectByName("markerObject");
    expect_true(map->getObjectByName("markerObject") == nullptr, "removeObjectByName should erase existing objects");
    map->removeObjects([](std::shared_ptr<CMapObject> object) { return object->getName() == "blockingObject"; });
    expect_true(map->getObjects().empty(), "removeObjects should erase matching objects from a cloned iteration");
}

void test_map_keeps_tiles_and_objects_separate_by_z() {
    auto map = std::make_shared<CMap>();
    map->setXBounds({{0, 4}, {1, 4}});
    map->setYBounds({{0, 4}, {1, 4}});

    auto lower_floor = std::make_shared<CTile>();
    lower_floor->setCanStep(true);
    lower_floor->setTileType("lowerFloor");
    auto upper_wall = std::make_shared<CTile>();
    upper_wall->setCanStep(false);
    upper_wall->setTileType("upperWall");
    auto upper_floor = std::make_shared<CTile>();
    upper_floor->setCanStep(true);
    upper_floor->setTileType("upperFloor");
    auto lower_probe_floor = std::make_shared<CTile>();
    lower_probe_floor->setCanStep(true);
    lower_probe_floor->setTileType("lowerProbeFloor");

    expect_true(map->addTile(lower_floor, 1, 1, 0), "same x/y should accept a level 0 tile");
    expect_true(map->addTile(upper_wall, 1, 1, 1), "same x/y should accept a separate level 1 tile");
    expect_true(!map->addTile(std::make_shared<CTile>(), 1, 1, 0),
                "duplicate x/y/z tile coordinates should still be rejected");
    expect_true(map->addTile(lower_probe_floor, 2, 2, 0), "lower probe tile should be stored");
    expect_true(map->addTile(upper_floor, 2, 2, 1), "upper probe tile should be stored");

    expect_true(map->getTile(1, 1, 0) == lower_floor, "getTile should return the level 0 tile");
    expect_true(map->getTile(1, 1, 1) == upper_wall, "getTile should return the level 1 tile");
    expect_true(map->canStep(1, 1, 0), "walkable lower tile should be passable");
    expect_true(!map->canStep(1, 1, 1), "blocking upper tile should be impassable");
    expect_true(map->getTiles().size() == 4, "tile storage should count distinct z-level coordinates");

    auto lower_blocker = std::make_shared<CMapObject>();
    lower_blocker->setName("lowerBlocker");
    lower_blocker->setCanStep(false);
    lower_blocker->setPosX(2);
    lower_blocker->setPosY(2);
    lower_blocker->setPosZ(0);
    auto upper_marker = std::make_shared<CMapObject>();
    upper_marker->setName("upperMarker");
    upper_marker->setCanStep(true);
    upper_marker->setPosX(2);
    upper_marker->setPosY(2);
    upper_marker->setPosZ(1);

    map->setObjects({lower_blocker, upper_marker});
    auto lower_objects = map->getObjectsAtCoords(Coords(2, 2, 0));
    auto upper_objects = map->getObjectsAtCoords(Coords(2, 2, 1));
    expect_true(lower_objects.size() == 1 && lower_objects.contains(lower_blocker),
                "object lookup should return only objects on the requested lower level");
    expect_true(upper_objects.size() == 1 && upper_objects.contains(upper_marker),
                "object lookup should return only objects on the requested upper level");
    expect_true(!map->canStep(2, 2, 0), "lower blocking object should block only its own level");
    expect_true(map->canStep(2, 2, 1), "upper level should remain passable at the same x/y");

    auto old_upper_coords = upper_marker->getCoords();
    upper_marker->setPosX(3);
    map->objectMoved(upper_marker, old_upper_coords, upper_marker->getCoords());
    expect_true(map->getObjectsAtCoords(Coords(2, 2, 1)).empty(),
                "moving an upper-level object should clear its old z-specific cache entry");
    expect_true(map->getObjectsAtCoords(Coords(3, 2, 1)).contains(upper_marker),
                "moving an upper-level object should populate its new z-specific cache entry");
    expect_true(map->getObjectsAtCoords(Coords(2, 2, 0)).contains(lower_blocker),
                "moving an upper-level object should not disturb lower-level cache entries");
}

void test_can_step_checks_default_tile_passability_without_materializing() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "multilevel", "Warrior");
    auto map = game->getMap();

    const auto initial_tile_count = map->getTiles().size();
    const auto initial_navigation_revision = map->getNavigationRevision();
    expect_true(!map->contains(0, 0, 0), "sparse multilevel map should not materialize default tiles at load");
    expect_true(!map->canStep(0, 0, 0), "canStep should honor the level's blocking default tile");
    expect_true(map->getTiles().size() == initial_tile_count, "canStep should not materialize missing default tiles");
    expect_true(map->getNavigationRevision() == initial_navigation_revision,
                "canStep should not bump navigation revision for missing default tiles");
}

void test_animation_provider_uses_dynamic_animation_for_directory_resources() {
    auto game = CGameLoader::loadGame();
    auto object = std::make_shared<CGameObject>();
    object->setAnimation("images/monsters/octobogz");

    auto animation = CAnimationProvider::getAnimation(game, object);
    expect_true(animation && animation->meta()->inherits("CDynamicAnimation"),
                "animation provider should use dynamic animations for directory resources");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_scene_manager_state_duplicate_and_player_transfer();
    test_scene_manager_repeated_transitions_and_controller_usability();
    test_scene_manager_null_and_legacy_missing_target_behavior();
    test_map_tiles_bounds_wrapping_and_object_cache();
    test_map_keeps_tiles_and_objects_separate_by_z();
    test_can_step_checks_default_tile_passability_without_materializing();
    test_animation_provider_uses_dynamic_animation_for_directory_resources();

    return finish_tests();
}
