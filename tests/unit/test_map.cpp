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
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CProvider.h"
#include "core/CSceneManager.h"
#include "core/CSerialization.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "handler/CEventHandler.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CGameObject.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "object/CTrigger.h"
#include "test_harness.h"
#include "veventloop.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

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

bool contains_coords(const std::vector<Coords> &coords, Coords target) {
    return std::ranges::find(coords, target) != coords.end();
}

std::pair<int, int> read_png_dimensions(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    std::array<unsigned char, 24> header{};
    input.read(reinterpret_cast<char *>(header.data()), static_cast<std::streamsize>(header.size()));

    auto read_big_endian = [](const unsigned char *bytes) {
        return (static_cast<int>(bytes[0]) << 24) | (static_cast<int>(bytes[1]) << 16) |
               (static_cast<int>(bytes[2]) << 8) | static_cast<int>(bytes[3]);
    };

    return {read_big_endian(&header[16]), read_big_endian(&header[20])};
}

struct TraceReset {
    ~TraceReset() { CPlaytestTrace::configure(false); }
};

std::vector<json> drain_trace_json() {
    std::vector<json> records;
    for (const auto &line : CPlaytestTrace::drain()) {
        records.push_back(json::parse(line));
    }
    return records;
}

bool has_trace_event(const std::vector<json> &records, const std::string &event) {
    for (const auto &record : records) {
        if (record.contains("event") && record["event"].get<std::string>() == event) {
            return true;
        }
    }
    return false;
}

int count_trace_event(const std::vector<json> &records, const std::string &event) {
    int count = 0;
    for (const auto &record : records) {
        if (record.contains("event") && record["event"].get<std::string>() == event) {
            ++count;
        }
    }
    return count;
}

int count_players_on_map(const std::shared_ptr<CMap> &map) {
    int count = 0;
    for (const auto &object : map->getObjects()) {
        if (std::dynamic_pointer_cast<CPlayer>(object)) {
            ++count;
        }
    }
    return count;
}

std::size_t count_player_event_triggers(const std::shared_ptr<CMap> &map) {
    std::size_t count = 0;
    for (const auto &trigger : map->getEventHandler()->getTriggers()) {
        if (trigger && trigger->getObject() == "player") {
            ++count;
        }
    }
    return count;
}

bool has_trace_event_reason(const std::vector<json> &records, const std::string &event, const std::string &reason) {
    for (const auto &record : records) {
        if (record.contains("event") && record["event"].get<std::string>() == event && record.contains("reason") &&
            record["reason"].get<std::string>() == reason) {
            return true;
        }
    }
    return false;
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
    expect_true(count_players_on_map(old_map) == 1,
                "scene transition should leave the source map untouched (its player reference is preserved)");
    expect_true(count_players_on_map(new_map) == 1, "new map should contain exactly one player after transfer");
    expect_true(manager->getTransitionState() == CSceneManager::TransitionState::Idle,
                "scene manager should return to idle after transition completion");
    expect_true(!manager->isTransitionPending(), "completed scene transition should clear pending state");
    expect_true(manager->getPendingMapName().empty(), "completed scene transition should clear pending map name");
}

void test_game_change_map_duplicate_requests_commit_once() {
    TraceReset reset;
    CPlaytestTrace::configure(true);

    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto old_map = game->getMap();
    auto player = old_map->getPlayer();
    old_map->setTurn(23);
    auto manager = game->getSceneManager();

    game->changeMap("ritual");
    game->changeMap("siege");

    expect_true(manager->getPendingMapName() == "ritual",
                "CGame::changeMap duplicate request should keep the first pending target");
    expect_true(game->getMap() == old_map, "CGame::changeMap should defer the map swap until the event loop runs");

    pump_event_loop_iterations();

    auto new_map = game->getMap();
    int player_object_count = 0;
    for (const auto &object : new_map->getObjects()) {
        if (object.get() == player.get()) {
            ++player_object_count;
        }
    }

    auto records = drain_trace_json();
    expect_true(new_map != old_map, "one queued CGame::changeMap request should commit after the event loop runs");
    expect_true(new_map->getMapName() == "ritual", "first CGame::changeMap request should determine the destination");
    expect_true(new_map->getMapName() != "siege", "duplicate CGame::changeMap request should not commit later");
    expect_true(new_map->getTurn() == 23, "single committed transition should preserve the old map turn");
    expect_true(new_map->getPlayer() == player, "single committed transition should transfer the same player object");
    expect_true(player_object_count == 1, "single committed transition should attach the player exactly once");
    expect_true(manager->getTransitionState() == CSceneManager::TransitionState::Idle,
                "single committed transition should return the scene manager to idle");
    expect_true(count_trace_event(records, "map_transition_requested") == 1,
                "duplicate CGame::changeMap calls should queue exactly one transition request");
    expect_true(has_trace_event_reason(records, "map_transition_rejected", "transition_pending"),
                "duplicate CGame::changeMap call should be rejected as pending");
    expect_true(count_trace_event(records, "map_transition_completed") == 1,
                "duplicate CGame::changeMap calls should commit exactly one transition");
}

void test_scene_manager_transition_generation_start_and_commit() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");

    auto context = game->getContext();
    auto initial_generation = context->captureTransitionGeneration();
    auto manager = game->getSceneManager();

    expect_true(manager->requestMapChange(game, "ritual"), "scene manager should accept a transition request");
    auto started_generation = context->getTransitionGeneration();
    expect_true(started_generation == initial_generation + 1,
                "accepted scene transition should advance generation when it starts");
    expect_true(!context->isTransitionGenerationCurrent(initial_generation),
                "pre-transition generation should be stale after transition start");
    expect_true(context->isTransitionGenerationCurrent(started_generation),
                "transition-start generation should remain current before commit");

    pump_event_loop_iterations();

    auto committed_generation = context->getTransitionGeneration();
    expect_true(committed_generation == started_generation + 1,
                "completed scene transition should advance generation when it commits");
    expect_true(!context->isTransitionGenerationCurrent(started_generation),
                "transition-start generation should be stale after commit");
    expect_true(context->isTransitionGenerationCurrent(committed_generation),
                "committed transition generation should be current");
}

void test_scene_manager_stale_transition_generation_clears_pending_state() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");

    auto old_map = game->getMap();
    auto manager = game->getSceneManager();
    auto context = game->getContext();

    expect_true(manager->requestMapChange(game, "ritual"), "scene manager should accept a transition request");
    auto started_generation = context->captureTransitionGeneration();
    context->advanceTransitionGeneration();

    pump_event_loop_iterations();

    expect_true(game->getMap() == old_map, "stale transition generation should not replace the active map");
    expect_true(!context->isTransitionGenerationCurrent(started_generation),
                "manually advanced transition generation should make the request stale");
    expect_true(manager->getTransitionState() == CSceneManager::TransitionState::Idle,
                "stale transition callback should clear pending state");
    expect_true(!manager->isTransitionPending(), "stale transition callback should not leave a pending transition");
    expect_true(manager->getPendingMapName().empty(), "stale transition callback should clear pending map name");
}

void test_scene_manager_trace_rejections_and_completion() {
    TraceReset reset;
    CPlaytestTrace::configure(true);

    auto standalone_manager = std::make_shared<CSceneManager>();
    expect_true(!standalone_manager->requestMapChange(nullptr, "ritual"),
                "trace-enabled scene manager should reject null-game requests");

    auto first_game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(first_game, "test", "Warrior");
    auto second_game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(second_game, "test", "Warrior");
    auto first_manager = first_game->getSceneManager();

    expect_true(!first_manager->requestMapChange(second_game, "ritual"),
                "trace-enabled scene manager should reject mismatched game requests");
    expect_true(first_manager->requestMapChange(first_game, "ritual"),
                "trace-enabled scene manager should accept a valid transition");
    expect_true(!first_manager->requestMapChange(first_game, "siege"),
                "trace-enabled scene manager should reject duplicate pending transitions");

    pump_event_loop_iterations();

    auto records = drain_trace_json();
    expect_true(has_trace_event_reason(records, "map_transition_rejected", "missing_game"),
                "trace should record missing-game rejection");
    expect_true(has_trace_event_reason(records, "map_transition_rejected", "mismatched_scene_manager"),
                "trace should record mismatched-manager rejection");
    expect_true(has_trace_event_reason(records, "map_transition_rejected", "transition_pending"),
                "trace should record duplicate pending transition rejection");
    expect_true(has_trace_event(records, "map_transition_requested"), "trace should record accepted transitions");
    expect_true(has_trace_event(records, "map_transition_completed"), "trace should record completed transitions");
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

void test_scene_manager_rejects_cross_game_requests() {
    auto game_a = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game_a, "test", "Warrior");
    auto game_b = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game_b, "test", "Warrior");

    auto manager_a = game_a->getSceneManager();
    auto manager_b = game_b->getSceneManager();

    expect_true(!manager_a->requestMapChange(game_b, "ritual"),
                "scene manager should reject transition requests for another game");
    expect_true(manager_a->getTransitionState() == CSceneManager::TransitionState::Idle,
                "cross-game rejection should leave the called manager idle");
    expect_true(manager_a->getPendingMapName().empty(), "cross-game rejection should not queue a destination");
    expect_true(manager_b->getTransitionState() == CSceneManager::TransitionState::Idle,
                "cross-game rejection should not mutate the target game's manager");

    pump_event_loop_iterations();

    expect_true(game_a->getMap()->getMapName() == "test", "cross-game rejection should not transition source game");
    expect_true(game_b->getMap()->getMapName() == "test", "cross-game rejection should not transition target game");
}

class FixedStepController : public CController {
  public:
    explicit FixedStepController(Coords target, bool remove_before_return = false)
        : target(target), removeBeforeReturn(remove_before_return) {}

    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override {
        return vstd::later([this, creature]() {
            if (removeBeforeReturn && creature && creature->getMap()) {
                creature->getMap()->removeObject(creature);
            }
            return target;
        });
    }

    void interrupt(std::shared_ptr<CCreature>) override { interruptCount++; }

    void onStepCommitted(std::shared_ptr<CCreature>, const Coords &) override { committedCount++; }

    void onTurnEnded(std::shared_ptr<CCreature>) override { turnEndedCount++; }

    Coords target;
    bool removeBeforeReturn = false;
    int interruptCount = 0;
    int committedCount = 0;
    int turnEndedCount = 0;
};

class TransitionDuringControlController : public CController {
  public:
    TransitionDuringControlController(std::string map_name, Coords target)
        : mapName(std::move(map_name)), target(target) {}

    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override {
        return vstd::later([this, creature]() {
            futureRan = true;
            if (creature && creature->getGame()) {
                creature->getGame()->changeMap(mapName);
            }
            return target;
        });
    }

    void onStepCommitted(std::shared_ptr<CCreature>, const Coords &) override { committedCount++; }

    void interrupt(std::shared_ptr<CCreature>) override { interruptCount++; }

    std::string mapName;
    Coords target;
    bool futureRan = false;
    int committedCount = 0;
    int interruptCount = 0;
};

class MovementOriginProbeCreature : public CCreature {
  public:
    void afterMove() override {
        observedOriginDuringAfterMove = getPendingMoveOrigin();
        CCreature::afterMove();
        originClearedAfterBaseAfterMove = !getPendingMoveOrigin().has_value();
    }

    std::optional<Coords> observedOriginDuringAfterMove;
    bool originClearedAfterBaseAfterMove = false;
};

class MoveHookCounterCreature : public CCreature {
  public:
    void beforeMove() override {
        beforeMoveCalls++;
        CCreature::beforeMove();
    }

    void afterMove() override {
        afterMoveCalls++;
        CCreature::afterMove();
    }

    int beforeMoveCalls = 0;
    int afterMoveCalls = 0;
};

class ObjectChangedProbe : public CGameObject {
    V_META(ObjectChangedProbe, CGameObject, V_METHOD(ObjectChangedProbe, onObjectChanged, void, Coords))

  public:
    void onObjectChanged(Coords coords) { objectChangedCoords.push_back(coords); }

    std::vector<Coords> objectChangedCoords;
};

// Drives the attacker's side of a step-combat encounter to a deterministic outcome so the
// post-combat position policy in CCreature::afterMove can be exercised without real RNG.
class PostCombatKillingFightController : public CFightController {
  public:
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature> opponent) override {
        if (opponent) {
            opponent->setHp(0);
        }
        return true;
    }
};

class PostCombatSelfDefeatFightController : public CFightController {
  public:
    bool control(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature>) override {
        if (actor) {
            actor->setHp(0);
        }
        return true;
    }
};

class PostCombatCancellingFightController : public CFightController {
  public:
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return false; }

    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return true; }
};

// Finds a walkable origin square that has at least one walkable orthogonal neighbour, returning
// the origin together with the single-step delta that reaches that neighbour.
bool find_walkable_step(const std::shared_ptr<CMap> &map, Coords &origin, Coords &delta) {
    for (const auto &[z, bounds] : map->getBounds()) {
        for (int y = 0; y <= bounds.second; ++y) {
            for (int x = 0; x <= bounds.first; ++x) {
                Coords candidate(x, y, z);
                if (!map->canStep(candidate)) {
                    continue;
                }
                for (const auto &step : {EAST, WEST, SOUTH, NORTH}) {
                    Coords target = map->normalizeCoords(candidate + step);
                    if (target != candidate && map->canStep(target)) {
                        origin = candidate;
                        delta = step;
                        return true;
                    }
                }
            }
        }
    }
    return false;
}

std::shared_ptr<CStats> creature_stats() {
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("intelligence");
    stats->setIntelligence(10);
    stats->setStrength(10);
    stats->setAgility(10);
    stats->setStamina(10);
    return stats;
}

std::shared_ptr<CCreature> test_creature(const std::shared_ptr<CGame> &game, const std::string &name, Coords coords,
                                         const std::shared_ptr<CController> &controller) {
    auto creature = std::make_shared<CCreature>();
    creature->setBaseStats(creature_stats());
    creature->setName(name);
    creature->setGame(game);
    creature->setController(controller);
    creature->setPosX(coords.x);
    creature->setPosY(coords.y);
    creature->setPosZ(coords.z);
    creature->setHp(creature->getHpMax());
    return creature;
}

std::shared_ptr<CCreature> add_post_combat_hostile(const std::shared_ptr<CGame> &game, const std::string &name,
                                                   Coords coords) {
    auto hostile = std::make_shared<CCreature>();
    hostile->setName(name);
    hostile->setGame(game);
    hostile->setBaseStats(creature_stats());
    hostile->setLevel(1);
    hostile->setHp(hostile->getHpMax());
    hostile->setFightController(std::make_shared<CFightController>());
    hostile->setPosX(coords.x);
    hostile->setPosY(coords.y);
    hostile->setPosZ(coords.z);
    game->getMap()->addObject(hostile);
    hostile->setHp(hostile->getHpMax());
    return hostile;
}

void test_map_move_ignores_controller_future_after_transition_generation_changes() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();

    Coords origin = ZERO;
    Coords planned = ZERO;
    bool found = false;
    for (const auto &[z, bounds] : map->getBounds()) {
        for (int y = 0; y <= bounds.second && !found; ++y) {
            for (int x = 0; x <= bounds.first && !found; ++x) {
                Coords candidate(x, y, z);
                if (!map->canStep(candidate)) {
                    continue;
                }
                for (const auto &delta : {EAST, WEST, SOUTH, NORTH}) {
                    Coords step = map->normalizeCoords(candidate + delta);
                    if (step != candidate && map->canStep(step)) {
                        origin = candidate;
                        planned = step;
                        found = true;
                        break;
                    }
                }
            }
        }
        if (found) {
            break;
        }
    }
    expect_true(found, "transition-stale controller fixture should find a walkable planned step");
    if (!found) {
        return;
    }

    auto controller = std::make_shared<TransitionDuringControlController>("ritual", planned);
    auto creature = test_creature(game, "transitionStaleFutureWalker", origin, controller);
    map->addObject(creature);

    map->move();

    expect_true(controller->futureRan, "controller future should run during map movement");
    expect_true(game->getSceneManager()->isTransitionPending(),
                "controller future should queue a transition while map movement is still resolving");
    expect_true(creature->getCoords() == origin,
                "stale controller future result should not move a creature after transition generation changes");
    expect_true(controller->committedCount == 0,
                "stale controller future result should not be reported as a committed step");
    expect_true(controller->interruptCount == 0,
                "stale controller future result should be dropped before movement interruption callbacks");

    pump_event_loop_iterations();

    expect_true(game->getMap()->getMapName() == "ritual", "queued transition should still commit after movement ends");
    expect_true(game->getMap()->getObjectByName("transitionStaleFutureWalker") == nullptr,
                "non-player object from the old map should not be carried into the new map");
}

template <typename Func> void expect_runtime_error(Func func, const char *message) {
    bool threw = false;
    try {
        func();
    } catch (const std::runtime_error &) {
        threw = true;
    }
    expect_true(threw, message);
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
    expect_true(floor->getMovementCost() == 1, "tile movement cost should default to one");
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
    floor->setMovementCost(4);
    expect_true(map->getMovementCost(2, 1, 0) == 4, "map movement cost should read the stored tile value");
    floor->setMovementCost(0);
    expect_true(map->getMovementCost(2, 1, 0) == 1, "map movement cost should clamp invalid tile values");

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

void test_tile_movement_cost_deserialization() {
    auto game = CGameLoader::loadGame();

    auto omitted = game->createObject<CTile>("GrassTile");
    expect_true(omitted && omitted->getMovementCost() == 1,
                "configured tiles without movementCost should keep the default");

    auto weighted_config = std::make_shared<json>();
    (*weighted_config)["class"] = "CTile";
    (*weighted_config)["properties"]["canStep"] = true;
    (*weighted_config)["properties"]["movementCost"] = 6;
    (*weighted_config)["properties"]["tileType"] = "weighted";
    game->getObjectHandler()->registerConfig("WeightedTile", weighted_config);

    auto weighted = game->createObject<CTile>("WeightedTile");
    expect_true(weighted && weighted->getMovementCost() == 6, "configured movementCost should deserialize onto CTile");

    auto invalid_config = std::make_shared<json>();
    (*invalid_config)["class"] = "CTile";
    (*invalid_config)["properties"]["movementCost"] = -3;
    game->getObjectHandler()->registerConfig("InvalidCostTile", invalid_config);

    auto invalid = game->createObject<CTile>("InvalidCostTile");
    expect_true(invalid && invalid->getMovementCost() == 1,
                "invalid configured movementCost should clamp to one during deserialization");
}

void test_map_movement_cost_default_lookup_without_materializing() {
    auto game = CGameLoader::loadGame();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, 3}});
    map->setYBounds({{0, 3}});

    auto default_config = std::make_shared<json>();
    (*default_config)["class"] = "CTile";
    (*default_config)["properties"]["canStep"] = true;
    (*default_config)["properties"]["movementCost"] = 7;
    (*default_config)["properties"]["tileType"] = "weightedDefault";
    game->getObjectHandler()->registerConfig("WeightedDefaultTile", default_config);

    auto edge_config = std::make_shared<json>();
    (*edge_config)["class"] = "CTile";
    (*edge_config)["properties"]["canStep"] = false;
    (*edge_config)["properties"]["movementCost"] = 9;
    (*edge_config)["properties"]["tileType"] = "weightedEdge";
    game->getObjectHandler()->registerConfig("WeightedEdgeTile", edge_config);

    map->setDefaultTiles({{0, "WeightedDefaultTile"}});
    map->setOutOfBoundsTiles({{0, "WeightedEdgeTile"}});

    const auto initial_tile_count = map->getTiles().size();
    const auto initial_navigation_revision = map->getNavigationRevision();

    expect_true(map->lookupMovementCost(1, 1, 0) == 7,
                "movement cost should read configured default tile cost without an explicit tile");
    expect_true(map->lookupMovementCost(4, 1, 0) == 9,
                "movement cost should read configured out-of-bounds tile cost without an explicit tile");
    expect_true(map->getTiles().size() == initial_tile_count,
                "movement cost lookup should not materialize default or out-of-bounds tiles");
    expect_true(!map->contains(1, 1, 0), "default cost lookup should leave the sparse coordinate empty");
    expect_true(!map->contains(4, 1, 0), "out-of-bounds cost lookup should leave the sparse coordinate empty");
    expect_true(map->getNavigationRevision() == initial_navigation_revision,
                "non-materializing movement cost lookup should not bump navigation revision");
}

void test_map_navigation_edges_update_revision() {
    auto map = std::make_shared<CMap>();
    map->setXBounds({{0, 4}});
    map->setYBounds({{0, 4}});
    map->setWrapX({{0, 1}});

    const auto initial_revision = map->getNavigationRevision();
    CNavigationEdge bridge;
    bridge.source = Coords(-1, 2, 0);
    bridge.target = Coords(1, 2, 0);
    bridge.enabled = true;
    bridge.bidirectional = true;
    bridge.movementCost = 3;
    bridge.sourceObjectName = "ropeBridge";

    map->addNavigationEdge(bridge);
    expect_true(map->getNavigationRevision() > initial_revision,
                "adding a navigation edge should bump navigation revision");

    const auto revision_after_add = map->getNavigationRevision();
    const auto &edges = map->getNavigationEdges();
    expect_true(edges.size() == 1, "added navigation edge should be stored by the map");
    expect_true(edges.front().source == Coords(4, 2, 0), "navigation edge source should be normalized");
    expect_true(edges.front().target == Coords(1, 2, 0), "navigation edge target should be normalized");
    expect_true(edges.front().enabled, "navigation edge should preserve enabled state");
    expect_true(edges.front().bidirectional, "navigation edge should preserve directionality");
    expect_true(edges.front().movementCost == 3, "navigation edge should preserve movement cost");
    expect_true(edges.front().sourceObjectName == std::optional<std::string>("ropeBridge"),
                "navigation edge should preserve source object name");

    const std::optional<std::string> bridge_name = "ropeBridge";
    expect_true(!map->removeNavigationEdge(Coords(4, 2, 0), Coords(0, 2, 0), bridge_name),
                "removing a missing navigation edge should report false");
    expect_true(map->getNavigationRevision() == revision_after_add,
                "removing a missing navigation edge should not bump navigation revision");

    expect_true(map->removeNavigationEdge(Coords(-1, 2, 0), Coords(1, 2, 0), bridge_name),
                "removing an existing navigation edge should report true");
    expect_true(map->getNavigationEdges().empty(), "removed navigation edge should leave map storage");
    expect_true(map->getNavigationRevision() > revision_after_add,
                "removing an existing navigation edge should bump navigation revision");
}

void test_map_navigation_neighbors_include_registered_edges() {
    auto map = std::make_shared<CMap>();
    const Coords origin(2, 2, 0);

    auto base_neighbors = map->getNavigationNeighbors(origin);
    expect_true(contains_coords(base_neighbors, origin + EAST), "navigation neighbors should include east cardinal");
    expect_true(contains_coords(base_neighbors, origin + WEST), "navigation neighbors should include west cardinal");
    expect_true(contains_coords(base_neighbors, origin + SOUTH), "navigation neighbors should include south cardinal");
    expect_true(contains_coords(base_neighbors, origin + NORTH), "navigation neighbors should include north cardinal");
    expect_true(!contains_coords(base_neighbors, origin),
                "navigation neighbors should not include self unless requested");
    expect_true(contains_coords(map->getNavigationNeighbors(origin, true), origin),
                "navigation neighbors should include self when requested");

    CNavigationEdge portal;
    portal.source = origin;
    portal.target = Coords(9, 9, 0);
    portal.enabled = true;
    portal.sourceObjectName = "portal";
    map->registerNavigationEdge(portal);

    CNavigationEdge closed_portal;
    closed_portal.source = origin;
    closed_portal.target = Coords(8, 8, 0);
    closed_portal.enabled = false;
    closed_portal.sourceObjectName = "portal";
    map->registerNavigationEdge(closed_portal);

    CNavigationEdge bridge;
    bridge.source = Coords(6, 2, 0);
    bridge.target = origin;
    bridge.enabled = true;
    bridge.bidirectional = true;
    bridge.sourceObjectName = "bridge";
    map->registerNavigationEdge(bridge);

    auto edge_neighbors = map->getNavigationNeighbors(origin);
    expect_true(contains_coords(edge_neighbors, portal.target),
                "navigation neighbors should include enabled edge targets");
    expect_true(!contains_coords(edge_neighbors, closed_portal.target),
                "navigation neighbors should exclude disabled edge targets");
    expect_true(contains_coords(edge_neighbors, bridge.source),
                "navigation neighbors should include reverse targets for bidirectional edges");

    const auto revision_after_edges = map->getNavigationRevision();
    expect_true(map->unregisterNavigationEdgesForObject("portal") == 2,
                "unregistering by object name should remove all matching navigation edges");
    auto remaining_neighbors = map->getNavigationNeighbors(origin);
    expect_true(!contains_coords(remaining_neighbors, portal.target),
                "unregistered navigation edges should no longer be returned");
    expect_true(contains_coords(remaining_neighbors, bridge.source),
                "unregistering one object should leave other object edges active");
    expect_true(map->getNavigationRevision() > revision_after_edges,
                "unregistering matching navigation edges should bump navigation revision");

    const auto revision_after_missing = map->getNavigationRevision();
    expect_true(map->unregisterNavigationEdgesForObject("missing") == 0,
                "unregistering a missing object name should remove no edges");
    expect_true(map->getNavigationRevision() == revision_after_missing,
                "unregistering a missing object name should not bump navigation revision");
}

void test_map_dump_paths_uses_navigation_neighbors() {
    auto game = CGameLoader::loadGame();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, 10}});
    map->setYBounds({{0, 0}});

    for (int x = 0; x <= 10; ++x) {
        auto blocked = std::make_shared<CTile>();
        blocked->setCanStep(false);
        expect_true(map->addTile(blocked, x, 0, 0), "blocked dump-path fixture tile should be added");
    }

    for (int x : {0, 10}) {
        map->removeTile(x, 0, 0);
        auto open = std::make_shared<CTile>();
        open->setCanStep(true);
        expect_true(map->addTile(open, x, 0, 0), "open dump-path fixture tile should be added");
    }

    CNavigationEdge edge;
    edge.source = Coords(0, 0, 0);
    edge.target = Coords(10, 0, 0);
    edge.enabled = true;
    map->registerNavigationEdge(edge);

    auto player = std::make_shared<CPlayer>();
    player->setBaseStats(creature_stats());
    map->setPlayer(player);

    const auto output_path = std::filesystem::temp_directory_path() / "navigation-neighbor-path-dump.png";
    std::filesystem::remove(output_path);
    map->dumpPaths(output_path.string());

    expect_true(std::filesystem::exists(output_path), "navigation-neighbor path dump should create a PNG");
    expect_true(std::filesystem::file_size(output_path) > 0, "navigation-neighbor path dump should be non-empty");
    auto [width, height] = read_png_dimensions(output_path);
    expect_true(width == 44 && height == 4,
                "navigation-neighbor path dump should include the authored edge target in its bounds");
    std::filesystem::remove(output_path);
}

void test_map_defensive_branches_and_strict_validation() {
    auto map = std::make_shared<CMap>();
    map->setXBounds({{0, -1}});
    map->setYBounds({{0, 0}});
    map->setWrapX({{0, 1}});
    expect_true(map->normalizeCoords(Coords(5, 0, 0)) == Coords(5, 0, 0),
                "wrapped normalization should leave invalid bounds unchanged");

    map->setXBounds({{0, 2}});
    auto bounds = map->getBounds();
    expect_true(bounds.at(0) == std::make_pair(2, 0), "getBounds should return combined bounds");
    expect_true(map->getAdjacentCoords(Coords(1, 1, 0)).size() == 4,
                "non-wrapped adjacency should return four neighbors");

    auto located = std::make_shared<CMapObject>();
    located->setName("locatedObject");
    located->setCanStep(false);
    located->setPosX(1);
    located->setPosY(0);
    located->setPosZ(0);
    map->addObject(located);
    expect_true(map->getLocationByName("locatedObject") == Coords(1, 0, 0),
                "getLocationByName should return existing object coordinates");
    expect_true(map->getLocationByName("missingObject") == ZERO,
                "getLocationByName should return ZERO for missing objects");
    expect_true(map->addObjectByName("CMapObject", Coords(1, 0, 0)).empty(),
                "addObjectByName should return an empty name for blocked coordinates");

    auto named_tile = std::make_shared<CTile>();
    named_tile->setTileType("namedTile");
    expect_true(map->addTile(named_tile, 0, 0, 0), "fixture tile should be added");
    expect_true(map->getTile(Coords(0, 0, 0)) == named_tile, "coordinate getTile overload should return stored tiles");
    expect_true(map->getTiles().size() == 1, "getTiles should return stored tile snapshots");
    expect_true(map->getObjects().size() == 1, "getObjects should return stored object snapshots");
    expect_true(map->getObjectsAtCoords(Coords(99, 99, 0)).empty(),
                "empty coordinate lookups should return an empty set");

    map->setPlayer(nullptr);

    std::string error;
    auto empty_map = std::make_shared<CMap>();
    expect_true(!empty_map->restorePlayerAfterLoad(error) && error == "saved map does not contain a player object",
                "restorePlayerAfterLoad should reject maps without a player");

    auto invalid_player_map = std::make_shared<CMap>();
    auto invalid_player = std::make_shared<CPlayer>();
    invalid_player->setBaseStats(creature_stats());
    invalid_player->setName("notPlayer");
    invalid_player_map->addObject(invalid_player);
    expect_true(!invalid_player_map->restorePlayerAfterLoad(error) &&
                    error == "saved player object is not named player",
                "restorePlayerAfterLoad should reject non-canonical player names");

    auto duplicate_player_map = std::make_shared<CMap>();
    auto first_player = std::make_shared<CPlayer>();
    first_player->setBaseStats(creature_stats());
    first_player->setName("firstPlayer");
    auto second_player = std::make_shared<CPlayer>();
    second_player->setBaseStats(creature_stats());
    second_player->setName("secondPlayer");
    duplicate_player_map->addObject(first_player);
    duplicate_player_map->addObject(second_player);
    first_player->setName("player");
    second_player->setName("player");
    expect_true(!duplicate_player_map->restorePlayerAfterLoad(error) &&
                    error == "saved map contains multiple player objects",
                "restorePlayerAfterLoad should reject multiple player instances");

    auto duplicate_name = std::make_shared<CMapObject>();
    duplicate_name->setName("locatedObject");
    map->addObject(nullptr);
    map->addObject(duplicate_name);
    expect_true(map->getObjects().size() == 1, "addObject should ignore null and duplicate objects");

    {
        CSerialization::StrictScope strict;
        expect_runtime_error([&]() { map->setObjects({nullptr}); }, "strict setObjects should reject null objects");

        auto empty_name = std::make_shared<CMapObject>();
        empty_name->setName("");
        expect_runtime_error([&]() { map->setObjects({empty_name}); },
                             "strict setObjects should reject empty object names");
    }

    map->dumpPaths("/tmp/no-player-map-paths.txt");
    map->setTriggers({nullptr});
    map->objectMoved(nullptr, ZERO, ZERO);
    expect_true(map->getTriggers().empty(), "null triggers should be ignored");

    auto normal_trigger = std::make_shared<CTrigger>();
    normal_trigger->setObject("locatedObject");
    normal_trigger->setEvent("onTurn");
    auto custom_trigger = std::make_shared<CCustomTrigger>("locatedObject", "onDestroy", [](auto, auto) {});
    map->setTriggers({normal_trigger, custom_trigger});
    auto restored_triggers = map->getTriggers();
    expect_true(restored_triggers.contains(normal_trigger) && !restored_triggers.contains(custom_trigger),
                "getTriggers should omit custom trigger callbacks from serialized trigger snapshots");
}

void test_map_move_interrupts_invalid_planned_steps() {
    auto game = CGameLoader::loadGame();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, 2}});
    map->setYBounds({{0, 2}});
    for (int y = 0; y <= 2; ++y) {
        for (int x = 0; x <= 2; ++x) {
            auto tile = std::make_shared<CTile>();
            tile->setCanStep(!(x == 2 && y == 1));
            map->addTile(tile, x, y, 0);
        }
    }

    auto removing_controller = std::make_shared<FixedStepController>(Coords(1, 0, 0), true);
    auto removed_creature = test_creature(game, "removedCreature", Coords(0, 0, 0), removing_controller);
    map->addObject(removed_creature);
    map->move();
    expect_true(removing_controller->interruptCount == 1,
                "move should interrupt creatures removed before their planned step is committed");
    expect_true(map->getObjectByName("removedCreature") == nullptr,
                "fixture creature should have removed itself during planning");

    auto blocked_controller = std::make_shared<FixedStepController>(Coords(2, 1, 0));
    auto blocked_creature = test_creature(game, "blockedCreature", Coords(1, 1, 0), blocked_controller);
    map->addObject(blocked_creature);
    map->move();
    expect_true(blocked_controller->interruptCount == 1,
                "move should interrupt creatures whose planned step becomes blocked");
    expect_true(blocked_controller->committedCount == 0, "blocked planned steps should not be committed");
    expect_true(blocked_creature->getCoords() == Coords(1, 1, 0), "blocked creatures should stay in place");
}

void test_creature_tracks_pending_move_origin_only_during_after_move() {
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);

    auto origin_tile = std::make_shared<CTile>();
    origin_tile->setCanStep(true);
    auto destination_tile = std::make_shared<CTile>();
    destination_tile->setCanStep(true);
    map->addTile(origin_tile, 1, 1, 0);
    map->addTile(destination_tile, 2, 1, 0);

    auto creature = std::make_shared<MovementOriginProbeCreature>();
    creature->setName("movementOriginProbe");
    creature->setGame(game);
    creature->setBaseStats(creature_stats());
    creature->setLevel(1);
    creature->setHp(creature->getHpMax());
    creature->setPosX(1);
    creature->setPosY(1);
    creature->setPosZ(0);
    map->addObject(creature);

    expect_true(!creature->getPendingMoveOrigin().has_value(),
                "pending move origin should be empty before movement starts");

    creature->move(1, 0, 0);

    expect_true(creature->observedOriginDuringAfterMove.has_value(),
                "pending move origin should be populated during afterMove");
    expect_true(creature->observedOriginDuringAfterMove == Coords(1, 1, 0),
                "pending move origin should record the normalized pre-step coordinate");
    expect_true(creature->originClearedAfterBaseAfterMove, "base afterMove should clear pending move origin");
    expect_true(!creature->getPendingMoveOrigin().has_value(),
                "pending move origin should be empty after movement finishes");
}

void test_map_object_relocate_without_move_hooks_updates_spatial_state_once() {
    CTypes::register_type_metadata<ObjectChangedProbe, CGameObject>();

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, 4}});
    map->setYBounds({{0, 3}});
    map->setWrapX({{0, 1}});
    map->setWrapY({{0, 1}});

    auto creature = std::make_shared<MoveHookCounterCreature>();
    creature->setName("relocationProbe");
    creature->setGame(game);
    creature->setBaseStats(creature_stats());
    creature->setLevel(1);
    creature->setHp(creature->getHpMax());
    creature->setCanStep(false);
    map->addObject(creature);

    auto probe = std::make_shared<ObjectChangedProbe>();
    map->connect("objectChanged", probe, "onObjectChanged");

    const auto revision_before_relocation = map->getNavigationRevision();
    const auto cache_entries_before_relocation = map->getObjectCacheEntryCountForTesting();

    creature->relocateWithoutMoveHooks(Coords(-1, 4, 0));
    pump_event_loop_iterations();

    expect_true(creature->getCoords() == Coords(4, 0, 0),
                "relocateWithoutMoveHooks should normalize and store the destination coordinates");
    expect_true(map->getObjectsAtCoords(Coords(0, 0, 0)).empty(),
                "relocateWithoutMoveHooks should remove stale object cache entries");
    expect_true(map->getObjectsAtCoords(Coords(4, 0, 0)).contains(creature),
                "relocateWithoutMoveHooks should index the object at its normalized destination");
    expect_true(map->getObjectCacheEntryCountForTesting() == cache_entries_before_relocation,
                "relocateWithoutMoveHooks should keep one cache entry for the relocated object");
    expect_true(map->getNavigationRevision() > revision_before_relocation,
                "relocateWithoutMoveHooks should bump navigation revision through objectMoved");
    expect_true(creature->beforeMoveCalls == 0 && creature->afterMoveCalls == 0,
                "relocateWithoutMoveHooks should not invoke movement hooks");
    expect_true(!creature->getPendingMoveOrigin().has_value(),
                "relocateWithoutMoveHooks should not create pending movement origin state");
    expect_true((probe->objectChangedCoords == std::vector<Coords>{Coords(0, 0, 0), Coords(4, 0, 0)}),
                "relocateWithoutMoveHooks should emit one old-coordinate and one new-coordinate signal");
}

void test_map_owned_objects_and_tiles_remember_owner_when_active_map_changes() {
    auto game = std::make_shared<CGame>();
    auto old_map = std::make_shared<CMap>();
    auto new_map = std::make_shared<CMap>();
    old_map->setGame(game);
    new_map->setGame(game);
    old_map->setMapName("oldMap");
    new_map->setMapName("newMap");
    game->setMap(old_map);

    auto retained_object = std::make_shared<CMapObject>();
    retained_object->setGame(game);
    retained_object->setName("retainedObject");
    old_map->addObject(retained_object);

    auto retained_tile = std::make_shared<CTile>();
    retained_tile->setGame(game);
    expect_true(old_map->addTile(retained_tile, 1, 1, 0), "fixture tile should be added to the old map");

    auto rehomed_object = std::make_shared<CMapObject>();
    rehomed_object->setGame(game);
    rehomed_object->setName("rehomedObject");
    old_map->addObject(rehomed_object);

    auto rehomed_tile = std::make_shared<CTile>();
    rehomed_tile->setGame(game);
    expect_true(old_map->addTile(rehomed_tile, 3, 1, 0), "rehomed tile should start on the old map");

    new_map->addObject(rehomed_object);
    expect_true(new_map->addTile(rehomed_tile, 3, 1, 0), "rehomed tile should move to the new map");

    game->setMap(new_map);

    expect_true(retained_object->getMap() == old_map,
                "retained old-map objects should resolve their owning map after the active map changes");
    expect_true(retained_tile->getMap() == old_map,
                "retained old-map tiles should resolve their owning map after the active map changes");
    expect_true(rehomed_object->getMap() == new_map, "rehomed objects should resolve their new map owner");
    expect_true(rehomed_tile->getMap() == new_map, "rehomed tiles should resolve their new map owner");

    auto restored_object = std::make_shared<CMapObject>();
    restored_object->setGame(game);
    restored_object->setName("restoredObject");
    auto restored_tile = std::make_shared<CTile>();
    restored_tile->setGame(game);
    restored_tile->setPosx(2);
    restored_tile->setPosy(1);
    restored_tile->setPosz(0);

    old_map->setObjects({retained_object, restored_object});
    old_map->setTiles({retained_tile, restored_tile});

    expect_true(restored_object->getMap() == old_map,
                "objects restored through setObjects should resolve the restoring map");
    expect_true(restored_tile->getMap() == old_map, "tiles restored through setTiles should resolve the restoring map");
    expect_true(rehomed_object->getMap() == new_map,
                "setObjects should not clear objects already rehomed to another map");
    expect_true(rehomed_tile->getMap() == new_map, "setTiles should not clear tiles already rehomed to another map");

    bool destroy_callback_saw_old_map = false;
    old_map->setTriggers(
        {std::make_shared<CCustomTrigger>("retainedObject", CGameEvent::CType::onDestroy,
                                          [&](std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent>) {
                                              destroy_callback_saw_old_map = object && object->getMap() == old_map;
                                          })});

    old_map->removeObject(retained_object);

    expect_true(destroy_callback_saw_old_map,
                "destroy callbacks should still resolve the object owner before ownership is cleared");
    expect_true(retained_object->getMap() == new_map,
                "removed objects should fall back to the active game map after destroy callbacks finish");
}

void test_map_player_trigger_registration_is_idempotent() {
    auto game = CGameLoader::loadGame();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, 2}});
    map->setYBounds({{0, 2}});

    auto first_player = std::make_shared<CPlayer>();
    first_player->setBaseStats(creature_stats());
    auto second_player = std::make_shared<CPlayer>();
    second_player->setBaseStats(creature_stats());
    map->setPlayer(first_player);
    map->setPlayer(second_player);
    expect_true(map->getPlayer() == second_player, "setPlayer should still replace the active player");
}

void test_map_player_detach_attach_transfer_api() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto old_map = game->getMap();
    auto player = old_map->getPlayer();
    player->setHp(7);
    const auto old_trigger_count = count_player_event_triggers(old_map);

    auto detached_player = old_map->detachPlayer();

    expect_true(detached_player == player, "detachPlayer should return the active player");
    expect_true(old_map->getObjectByName("player") == nullptr, "detachPlayer should remove the canonical player name");
    expect_true(count_players_on_map(old_map) == 0, "detachPlayer should leave no player object on the source map");
    expect_true(player->getHp() == 7, "detachPlayer should not run the player onDestroy restart trigger");
    expect_true(count_player_event_triggers(old_map) == old_trigger_count,
                "detachPlayer should not add duplicate source-map player triggers");

    auto new_map = std::make_shared<CMap>();
    game->setMap(new_map);
    new_map->setGame(game);
    new_map->setEntryX(2);
    new_map->setEntryY(1);
    new_map->setEntryZ(0);

    new_map->attachPlayer(player);
    const auto first_attach_trigger_count = count_player_event_triggers(new_map);

    expect_true(new_map->getPlayer() == player, "attachPlayer should set the active player pointer");
    expect_true(new_map->getObjectByName("player") == player, "attachPlayer should add the canonical player object");
    expect_true(player->getName() == "player", "attachPlayer should assign canonical player identity");
    expect_true(std::dynamic_pointer_cast<CPlayerController>(player->getController()) != nullptr,
                "attachPlayer should install a player controller");
    expect_true(std::dynamic_pointer_cast<CPlayerFightController>(player->getFightController()) != nullptr,
                "attachPlayer should install a player fight controller");
    expect_true(player->getMap() == new_map, "attachPlayer should update map ownership");
    expect_true(player->getCoords() == new_map->getEntry(), "attachPlayer should place the player at the entry");
    expect_true(count_players_on_map(new_map) == 1, "attachPlayer should leave exactly one player object");
    expect_true(new_map->getObjectCacheEntryCountForTesting() == 1,
                "attachPlayer should create exactly one spatial cache entry for the player");
    expect_true(first_attach_trigger_count >= 2, "attachPlayer should register player lifecycle triggers");

    new_map->attachPlayer(player, Coords(4, 3, 0));

    expect_true(player->getCoords() == Coords(4, 3, 0), "attachPlayer(coords) should relocate the same player");
    expect_true(count_players_on_map(new_map) == 1, "reattaching the same player should not duplicate player objects");
    expect_true(new_map->getObjectsAtCoords(new_map->getEntry()).empty(),
                "reattaching the same player should clear the old spatial cache entry");
    expect_true(new_map->getObjectsAtCoords(Coords(4, 3, 0)).contains(player),
                "reattaching the same player should index the new spatial cache entry");
    expect_true(new_map->getObjectCacheEntryCountForTesting() == 1,
                "reattaching the same player should keep exactly one spatial cache entry");
    expect_true(count_player_event_triggers(new_map) == first_attach_trigger_count,
                "reattaching the same player should not duplicate player triggers");

    auto replacement_player = game->createObject<CPlayer>("Warrior");
    new_map->attachPlayer(replacement_player, Coords(1, 1, 0));

    expect_true(new_map->getPlayer() == replacement_player, "attachPlayer should replace the active player pointer");
    expect_true(new_map->getObjectByName("player") == replacement_player,
                "attachPlayer should replace the canonical player object");
    expect_true(count_players_on_map(new_map) == 1, "replacing the player should preserve the one-player invariant");
    expect_true(!new_map->getObjects().contains(player),
                "replacing the player should remove the previous player object");
    expect_true(count_player_event_triggers(new_map) == first_attach_trigger_count,
                "replacing the player should not duplicate player triggers");
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

void test_map_session_store_put_get_evict_and_ownership() {
    CMapSessionStore store;
    expect_true(store.size() == 0, "a new session store should be empty");

    auto first = std::make_shared<CMap>();
    first->setMapName("alpha");
    auto second = std::make_shared<CMap>();
    second->setMapName("alpha");
    auto beta = std::make_shared<CMap>();
    beta->setMapName("beta");

    store.put(first);                     // alpha / default instance, key derived from the map name
    store.put("alpha", "second", second); // alpha / explicit instance id
    store.put(beta, "");

    expect_true(store.size() == 3, "store should hold three distinct sessions");
    expect_true(store.get("alpha") == first, "default-instance get should return the stored map");
    expect_true(store.get("alpha", "second") == second, "instance get should return the per-instance map");
    expect_true(store.get("beta") == beta, "named get should return the stored map");
    expect_true(store.get("missing") == nullptr, "an absent session should resolve to null");
    expect_true(store.contains("alpha", "second"), "contains should report a stored instance session");
    expect_true(!store.contains("alpha", "third"), "contains should reject an unstored instance id");

    // The store owns its cached maps: dropping every external reference keeps the map alive.
    std::weak_ptr<CMap> weakBeta = beta;
    beta.reset();
    expect_true(!weakBeta.expired(), "store should retain ownership of cached maps");
    expect_true(store.get("beta") != nullptr, "a retained map should still be retrievable");

    expect_true(store.evict("alpha", "second"), "evict should report removing an existing session");
    expect_true(!store.evict("alpha", "second"), "evicting an absent session should report false");
    expect_true(store.get("alpha", "second") == nullptr, "an evicted session should no longer resolve");
    expect_true(store.get("alpha") == first, "evicting one instance should not affect the default session");

    auto replacement = std::make_shared<CMap>();
    replacement->setMapName("alpha");
    store.put(replacement);
    expect_true(store.get("alpha") == replacement, "putting the same key should replace the cached map");

    store.put(std::shared_ptr<CMap>(), "ignored");
    expect_true(!store.contains("", "ignored"), "putting a null map should be ignored");

    store.clear();
    expect_true(store.size() == 0, "clear should drop every session");
    expect_true(store.get("alpha") == nullptr, "a cleared store should resolve nothing");
}

void test_game_context_owns_a_map_session_store() {
    auto game = std::make_shared<CGame>();
    auto context = game->getContext();
    auto store = context->getMapSessionStore();
    expect_true(store != nullptr, "context should expose a map session store");
    expect_true(context->getMapSessionStore() == store, "context should return the same store instance on each call");

    auto cached = std::make_shared<CMap>();
    cached->setMapName("cached");
    store->put(cached);
    expect_true(context->getMapSessionStore()->get("cached") == cached,
                "context-owned store should retain maps across accessor calls");
}

class TurnCountingController : public CController {
  public:
    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override {
        controlCalls++;
        return vstd::later([creature]() { return creature->getCoords(); });
    }

    int controlCalls = 0;
};

void test_map_move_blocks_new_turn_while_transition_pending() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();

    auto controller = std::make_shared<TurnCountingController>();
    auto creature = test_creature(game, "transitionPendingWalker", ZERO, controller);
    map->addObject(creature);

    expect_true(game->getSceneManager()->requestMapChange(game, "ritual"),
                "requesting a map change should be accepted while the scene manager is idle");
    expect_true(game->getSceneManager()->isTransitionPending(),
                "the scene manager should report a pending transition after the request");

    const int turn_before = map->getTurn();
    map->move();

    expect_true(controller->controlCalls == 0, "no controller cycle should start while a transition is pending");
    expect_true(map->getTurn() == turn_before, "the old map should not advance a turn while a transition is pending");
}

void test_post_combat_player_victory_returns_to_origin() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();
    auto player = map->getPlayer();

    Coords origin = ZERO;
    Coords delta = ZERO;
    expect_true(find_walkable_step(map, origin, delta), "post-combat victory fixture should find a walkable step");
    const Coords hostile_cell = map->normalizeCoords(origin + delta);

    player->relocateWithoutMoveHooks(origin);
    player->setFightController(std::make_shared<PostCombatKillingFightController>());
    auto hostile = add_post_combat_hostile(game, "postCombatVictoryFoe", hostile_cell);

    player->move(delta.x, delta.y, delta.z);

    expect_true(map->normalizeCoords(player->getCoords()) == origin,
                "winning a step-into fight should return the player to the pre-step origin");
    expect_true(map->normalizeCoords(player->getCoords()) != hostile_cell,
                "victorious player should never remain inside the hostile cell");
    expect_true(!hostile->isAlive(), "the defeated opponent should be removed from the encounter");
    expect_true(!player->getPendingMoveOrigin().has_value(),
                "afterMove should clear the pending move origin once the encounter is resolved");
}

void test_post_combat_player_defeat_skips_further_movement() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();
    auto player = map->getPlayer();

    Coords origin = ZERO;
    Coords delta = ZERO;
    expect_true(find_walkable_step(map, origin, delta), "post-combat defeat fixture should find a walkable step");
    const Coords hostile_cell = map->normalizeCoords(origin + delta);

    player->relocateWithoutMoveHooks(origin);
    player->setFightController(std::make_shared<PostCombatSelfDefeatFightController>());
    add_post_combat_hostile(game, "postCombatDefeatFoe", hostile_cell);

    player->move(delta.x, delta.y, delta.z);
    pump_event_loop_iterations();

    // The defeated player is removed and then respawned at the map entry by the player
    // onDestroy trigger, so the post-combat policy must skip its own movement work.
    expect_true(map->normalizeCoords(player->getCoords()) != hostile_cell,
                "a defeated attacker must never be left standing inside the hostile cell");
    expect_true(map->normalizeCoords(player->getCoords()) == map->normalizeCoords(map->getEntry()),
                "a defeated player should respawn at the map entry rather than the hostile cell");
    expect_true(!player->getPendingMoveOrigin().has_value(),
                "afterMove should clear the pending move origin even when the attacker is defeated");
}

void test_post_combat_player_cancellation_returns_to_origin() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();
    auto player = map->getPlayer();

    Coords origin = ZERO;
    Coords delta = ZERO;
    expect_true(find_walkable_step(map, origin, delta), "post-combat cancellation fixture should find a walkable step");
    const Coords hostile_cell = map->normalizeCoords(origin + delta);

    player->relocateWithoutMoveHooks(origin);
    player->setFightController(std::make_shared<PostCombatCancellingFightController>());
    auto hostile = add_post_combat_hostile(game, "postCombatCancelFoe", hostile_cell);

    player->move(delta.x, delta.y, delta.z);

    expect_true(map->normalizeCoords(player->getCoords()) == origin,
                "cancelling a step-into fight should return the player to the pre-step origin");
    expect_true(map->normalizeCoords(player->getCoords()) != hostile_cell,
                "a cancelled or stalled encounter must never leave the player inside the hostile cell");
    expect_true(player->isAlive() && hostile->isAlive(), "a cancelled encounter should leave both combatants alive");
    expect_true(!player->getPendingMoveOrigin().has_value(),
                "afterMove should clear the pending move origin after a cancelled encounter");
}

void test_post_combat_player_multi_opponent_cell_returns_to_origin() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();
    auto player = map->getPlayer();

    Coords origin = ZERO;
    Coords delta = ZERO;
    expect_true(find_walkable_step(map, origin, delta),
                "post-combat multi-opponent fixture should find a walkable step");
    const Coords hostile_cell = map->normalizeCoords(origin + delta);

    player->relocateWithoutMoveHooks(origin);
    player->setFightController(std::make_shared<PostCombatKillingFightController>());
    auto first = add_post_combat_hostile(game, "postCombatMultiFoeA", hostile_cell);
    auto second = add_post_combat_hostile(game, "postCombatMultiFoeB", hostile_cell);

    player->move(delta.x, delta.y, delta.z);

    expect_true(map->normalizeCoords(player->getCoords()) == origin,
                "clearing a multi-opponent cell should still return the player to the pre-step origin");
    expect_true(map->normalizeCoords(player->getCoords()) != hostile_cell,
                "the player must not remain in a cleared multi-opponent cell");
    expect_true(!first->isAlive() && !second->isAlive(),
                "every opponent sharing the hostile cell should be defeated before the move resolves");
    expect_true(!player->getPendingMoveOrigin().has_value(),
                "afterMove should clear the pending move origin after a multi-opponent encounter");
}

void test_post_combat_victory_keeps_object_cache_at_origin_not_hostile_cell() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();
    auto player = map->getPlayer();

    Coords origin = ZERO;
    Coords delta = ZERO;
    expect_true(find_walkable_step(map, origin, delta),
                "post-combat victory cache fixture should find a walkable step");
    const Coords hostile_cell = map->normalizeCoords(origin + delta);

    player->relocateWithoutMoveHooks(origin);
    player->setFightController(std::make_shared<PostCombatKillingFightController>());
    auto hostile = add_post_combat_hostile(game, "postCombatVictoryCacheFoe", hostile_cell);

    player->move(delta.x, delta.y, delta.z);

    // The coordinate cache must follow the committed final position atomically: the victorious
    // player is indexed back at its origin and is never left registered in the contested cell, and
    // the defeated opponent is purged from that cell.
    expect_true(map->getObjectsAtCoords(origin).contains(player),
                "the victorious player should be indexed at its origin in the coordinate cache");
    expect_true(!map->getObjectsAtCoords(hostile_cell).contains(player),
                "the victorious player must not remain indexed in the hostile cell");
    expect_true(!map->getObjectsAtCoords(hostile_cell).contains(hostile),
                "the defeated opponent should be removed from the hostile-cell cache");
    expect_true(map->getObjectByName(player->getName()) == player,
                "the player should still resolve by name after returning to its origin");
}

void test_post_combat_cancellation_keeps_object_cache_at_origin_with_foe_present() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "test", "Warrior");
    auto map = game->getMap();
    auto player = map->getPlayer();

    Coords origin = ZERO;
    Coords delta = ZERO;
    expect_true(find_walkable_step(map, origin, delta),
                "post-combat cancellation cache fixture should find a walkable step");
    const Coords hostile_cell = map->normalizeCoords(origin + delta);

    player->relocateWithoutMoveHooks(origin);
    player->setFightController(std::make_shared<PostCombatCancellingFightController>());
    auto hostile = add_post_combat_hostile(game, "postCombatCancelCacheFoe", hostile_cell);

    player->move(delta.x, delta.y, delta.z);

    // A cancelled/stalled encounter restores the origin without disturbing the survived opponent:
    // the player is indexed at its origin, never in the contested cell, and the still-living foe
    // remains indexed in that cell.
    expect_true(map->getObjectsAtCoords(origin).contains(player),
                "a cancelled-encounter player should be indexed at its origin in the coordinate cache");
    expect_true(!map->getObjectsAtCoords(hostile_cell).contains(player),
                "a cancelled-encounter player must not remain indexed in the hostile cell");
    expect_true(map->getObjectsAtCoords(hostile_cell).contains(hostile),
                "the surviving opponent should stay indexed in its cell after a cancelled encounter");
    expect_true(player->isAlive() && hostile->isAlive(),
                "a cancelled encounter should leave both combatants alive and correctly indexed");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_scene_manager_state_duplicate_and_player_transfer();
    test_game_change_map_duplicate_requests_commit_once();
    test_scene_manager_transition_generation_start_and_commit();
    test_scene_manager_stale_transition_generation_clears_pending_state();
    test_scene_manager_trace_rejections_and_completion();
    test_scene_manager_repeated_transitions_and_controller_usability();
    test_scene_manager_null_and_legacy_missing_target_behavior();
    test_scene_manager_rejects_cross_game_requests();
    test_map_move_ignores_controller_future_after_transition_generation_changes();
    test_map_tiles_bounds_wrapping_and_object_cache();
    test_tile_movement_cost_deserialization();
    test_map_movement_cost_default_lookup_without_materializing();
    test_map_navigation_edges_update_revision();
    test_map_navigation_neighbors_include_registered_edges();
    test_map_dump_paths_uses_navigation_neighbors();
    test_map_defensive_branches_and_strict_validation();
    test_map_move_interrupts_invalid_planned_steps();
    test_creature_tracks_pending_move_origin_only_during_after_move();
    test_map_object_relocate_without_move_hooks_updates_spatial_state_once();
    test_map_owned_objects_and_tiles_remember_owner_when_active_map_changes();
    test_map_player_trigger_registration_is_idempotent();
    test_map_player_detach_attach_transfer_api();
    test_map_keeps_tiles_and_objects_separate_by_z();
    test_can_step_checks_default_tile_passability_without_materializing();
    test_animation_provider_uses_dynamic_animation_for_directory_resources();
    test_map_session_store_put_get_evict_and_ownership();
    test_game_context_owns_a_map_session_store();
    test_map_move_blocks_new_turn_while_transition_pending();
    test_post_combat_player_victory_returns_to_origin();
    test_post_combat_player_defeat_skips_further_movement();
    test_post_combat_player_cancellation_returns_to_origin();
    test_post_combat_player_multi_opponent_cell_returns_to_origin();
    test_post_combat_victory_keeps_object_cache_at_origin_not_hostile_cell();
    test_post_combat_cancellation_keeps_object_cache_at_origin_with_foe_present();

    return finish_tests();
}
