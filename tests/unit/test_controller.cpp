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
#include "core/CGameContext.h"
#include "core/CJson.h"
#include "core/CMap.h"
#include "core/CStats.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/panel/CGameFightPanel.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "veventloop.h"

#include <pybind11/embed.h>

#include <map>
#include <memory>
#include <vector>

namespace {

std::shared_ptr<CCreature> creature_at(int x, int y, int z) {
    auto creature = std::make_shared<CCreature>();
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("intelligence");
    creature->setBaseStats(stats);
    creature->setPosX(x);
    creature->setPosY(y);
    creature->setPosZ(z);
    return creature;
}

std::shared_ptr<CTile> walkable_tile() {
    auto tile = std::make_shared<CTile>();
    tile->setTileType("floor");
    tile->setCanStep(true);
    return tile;
}

Coords resolve_coords(const std::shared_ptr<vstd::future<Coords, void>> &future) {
    vstd::event_loop<>::instance()->run();
    return future->get();
}

std::shared_ptr<CTile> tile(bool can_step) {
    auto result = std::make_shared<CTile>();
    result->setCanStep(can_step);
    return result;
}

std::shared_ptr<CMap> open_tile_map(const std::shared_ptr<CGame> &game, int width, int height, int levels = 1) {
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    std::map<int, int> x_bounds;
    std::map<int, int> y_bounds;
    for (int z = 0; z < levels; ++z) {
        x_bounds[z] = width - 1;
        y_bounds[z] = height - 1;
    }
    map->setXBounds(x_bounds);
    map->setYBounds(y_bounds);
    for (int z = 0; z < levels; ++z) {
        for (int y = 0; y < height; ++y) {
            for (int x = 0; x < width; ++x) {
                map->addTile(tile(true), x, y, z);
            }
        }
    }
    return map;
}

void set_tile_movement_cost(const std::shared_ptr<CMap> &map, Coords coords, int movement_cost) {
    auto tile = map->getTile(coords);
    expect_true(tile != nullptr, "weighted path fixture tile should exist");
    if (tile) {
        tile->setMovementCost(movement_cost);
    }
}

std::shared_ptr<CMap> weighted_detour_map(const std::shared_ptr<CGame> &game) {
    auto map = open_tile_map(game, 5, 2);
    for (int x = 1; x <= 3; ++x) {
        set_tile_movement_cost(map, Coords(x, 0, 0), 30);
    }
    return map;
}

std::vector<Coords> expected_weighted_detour_path() {
    return {
        Coords(0, 1, 0), Coords(1, 1, 0), Coords(2, 1, 0), Coords(3, 1, 0), Coords(4, 1, 0), Coords(4, 0, 0),
    };
}

std::shared_ptr<CPlayer> player_at(const std::shared_ptr<CGame> &game, Coords coords) {
    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    player->setName("player");
    player->setCoords(coords);
    return player;
}

void add_navigation_edge(const std::shared_ptr<CMap> &map, Coords source, Coords target, bool bidirectional = false,
                         bool enabled = true) {
    CNavigationEdge edge;
    edge.source = source;
    edge.target = target;
    edge.enabled = enabled;
    edge.bidirectional = bidirectional;
    map->registerNavigationEdge(edge);
}

void test_movement_controller_null_and_no_map_paths() {
    auto creature = creature_at(2, 3, 4);

    auto base_controller = std::make_shared<CController>();
    expect_true(resolve_coords(base_controller->control(nullptr)) == ZERO,
                "base controller should return ZERO for null creatures");
    expect_true(resolve_coords(base_controller->control(creature)) == Coords(2, 3, 4),
                "base controller should return creature coordinates");
    base_controller->onStepCommitted(creature, creature->getCoords());
    base_controller->interrupt(creature);
    base_controller->onTurnEnded(creature);

    auto target_controller = std::make_shared<CTargetController>();
    target_controller->setTarget("missing");
    expect_true(target_controller->getTarget() == "missing", "target controller should expose its target id");
    expect_true(resolve_coords(target_controller->control(nullptr)) == ZERO,
                "target controller should return ZERO for null creatures");
    expect_true(resolve_coords(target_controller->control(creature)) == ZERO,
                "target controller should return ZERO before a creature has a map");

    auto random_controller = std::make_shared<CRandomController>();
    expect_true(resolve_coords(random_controller->control(nullptr)) == ZERO,
                "random controller should return ZERO for null creatures");

    auto npc_controller = std::make_shared<CNpcRandomController>();
    expect_true(resolve_coords(npc_controller->control(nullptr)) == ZERO,
                "NPC random controller should return ZERO for null creatures");
    expect_true(resolve_coords(npc_controller->control(creature)) == creature->getCoords(),
                "NPC random controller should stay put before a creature has a map");
    npc_controller->onStepCommitted(creature, creature->getCoords());
    npc_controller->interrupt(creature);

    auto ground_controller = std::make_shared<CGroundController>();
    ground_controller->setTileType("floor");
    expect_true(ground_controller->getTileType() == "floor", "ground controller should expose its tile type");
    expect_true(resolve_coords(ground_controller->control(nullptr)) == ZERO,
                "ground controller should return ZERO for null creatures");
    expect_true(resolve_coords(ground_controller->control(creature)) == creature->getCoords(),
                "ground controller should stay put before a creature has a map");

    auto range_controller = std::make_shared<CRangeController>();
    range_controller->setTarget("player");
    range_controller->setDistance(3);
    expect_true(range_controller->getTarget() == "player" && range_controller->getDistance() == 3,
                "range controller should expose target and distance settings");
    expect_true(resolve_coords(range_controller->control(nullptr)) == ZERO,
                "range controller should return ZERO for null creatures");
    expect_true(resolve_coords(range_controller->control(creature)) == creature->getCoords(),
                "range controller should stay put before a creature has a map");

    auto player_controller = std::make_shared<CPlayerController>();
    expect_true(resolve_coords(player_controller->control(nullptr)) == ZERO,
                "player controller should return ZERO for null creatures");
    player_controller->interrupt(nullptr);
    player_controller->onTurnEnded(nullptr);
}

void test_npc_random_controller_clears_current_tile_path() {
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, 0}});
    map->setYBounds({{0, 0}});
    map->setWrapX({{0, 1}});
    map->setWrapY({{0, 1}});
    map->addTile(walkable_tile(), 0, 0, 0);

    auto creature = creature_at(0, 0, 0);
    creature->setName("unitNpcRandomWalker");
    creature->setGame(game);
    creature->setHp(1);

    auto controller = std::make_shared<CNpcRandomController>();
    controller->setGame(game);
    creature->setController(controller);

    auto selected = resolve_coords(controller->control(creature));
    expect_true(selected == Coords(0, 0, 0),
                "NPC random controller should stay put when every random target normalizes to the current tile");
}

void test_npc_random_controller_clears_stale_blocked_path() {
    vstd::rng().seed(12345);
    auto game = std::make_shared<CGame>();
    auto map = open_tile_map(game, 11, 11);
    auto creature = creature_at(5, 5, 0);
    creature->setGame(game);

    auto controller = std::make_shared<CNpcRandomController>();
    Coords original = creature->getCoords();
    Coords planned = original;
    for (int attempt = 0; attempt < 20 && planned == original; ++attempt) {
        controller->interrupt(creature);
        planned = resolve_coords(controller->control(creature));
    }

    expect_true(planned != original, "NPC random controller fixture should find a real next step");
    expect_true(map->getDistance(original, planned) == 1.0, "NPC random controller should plan an adjacent step");
    expect_true(map->canStep(planned), "planned NPC random step should be initially passable");

    map->removeTile(planned.x, planned.y, planned.z);
    expect_true(map->addTile(tile(false), planned.x, planned.y, planned.z), "fixture should block the planned step");
    expect_true(!map->canStep(planned), "fixture should make the planned step impassable");

    auto replanned = resolve_coords(controller->control(creature));
    expect_true(replanned != planned, "NPC random controller should not keep a newly blocked stale next step");
    expect_true(replanned == original || map->canStep(replanned),
                "NPC random controller should either stay put or replan to a passable step");
}

void test_ground_controller_ignores_stale_transition_generation() {
    auto game = std::make_shared<CGame>();
    auto map = open_tile_map(game, 2, 1);
    map->getTile(0, 0, 0)->setTileType("stone");
    map->getTile(1, 0, 0)->setTileType("floor");

    auto creature = creature_at(0, 0, 0);
    creature->setGame(game);
    creature->setName("unitStaleGroundWalker");
    creature->setHp(1);
    auto controller = std::make_shared<CGroundController>();
    controller->setTileType("floor");
    creature->setController(controller);
    map->addObject(creature);

    auto pending = controller->control(creature);
    game->getContext()->advanceTransitionGeneration();

    expect_true(resolve_coords(pending) == Coords(0, 0, 0),
                "ground controller should ignore deferred steps from stale transition generations");
}

void test_player_controller_prefers_longer_lower_cost_route() {
    auto game = std::make_shared<CGame>();
    weighted_detour_map(game);
    auto player = player_at(game, Coords(0, 0, 0));
    auto controller = std::make_shared<CPlayerController>();
    player->setController(controller);
    controller->setTarget(player, Coords(4, 0, 0));

    for (const auto &expected_step : expected_weighted_detour_path()) {
        auto actual_step = resolve_coords(controller->control(player));
        expect_true(actual_step == expected_step, "player controller should follow the cheaper weighted detour");
        player->moveTo(actual_step);
        controller->onStepCommitted(player, actual_step);
    }

    expect_true(player->getCoords() == Coords(4, 0, 0), "player weighted detour should reach the target");
    expect_true(controller->isCompleted(player), "player weighted detour should complete after the target step");
}

void test_npc_random_controller_prefers_longer_lower_cost_route() {
    vstd::rng().seed(4);
    auto game = std::make_shared<CGame>();
    weighted_detour_map(game);
    auto creature = creature_at(0, 0, 0);
    creature->setGame(game);

    auto controller = std::make_shared<CNpcRandomController>();
    auto first = resolve_coords(controller->control(creature));
    expect_true(first == Coords(0, 1, 0), "NPC random controller should start on the cheaper weighted detour");
    creature->moveTo(first);
    controller->onStepCommitted(creature, first);

    auto second = resolve_coords(controller->control(creature));
    expect_true(second == Coords(1, 1, 0), "NPC random controller should keep following the weighted detour path");
}

void test_target_controller_flow_field_prefers_longer_lower_cost_route() {
    auto game = std::make_shared<CGame>();
    auto map = weighted_detour_map(game);

    auto target = std::make_shared<CMapObject>();
    target->setGame(game);
    target->setName("weightedTarget");
    target->setCanStep(true);
    target->setCoords(Coords(4, 0, 0));
    map->addObject(target);

    auto chaser = creature_at(0, 0, 0);
    chaser->setGame(game);
    chaser->setName("weightedChaser");
    chaser->setHp(1);
    auto controller = std::make_shared<CTargetController>();
    controller->setTarget("weightedTarget");
    chaser->setController(controller);
    map->addObject(chaser);

    performance_guard::clearTargetFlowCache();
    for (const auto &expected_step : expected_weighted_detour_path()) {
        auto actual_step = resolve_coords(controller->control(chaser));
        expect_true(actual_step == expected_step, "target flow field should follow the cheaper weighted detour");
        chaser->moveTo(actual_step);
    }

    expect_true(chaser->getCoords() == target->getCoords(), "target weighted detour should reach the target");
}

void test_player_controller_prefers_cheap_navigation_edge_over_expensive_band() {
    auto game = std::make_shared<CGame>();
    auto map = weighted_detour_map(game);
    // A bidirectional waypoint edge spans the expensive row-0 band. Its step cost is the destination
    // tile cost (1), not the 30-cost band, so weighted pathing must cross the edge instead of taking
    // the expensive direct row or the longer cheap detour.
    add_navigation_edge(map, Coords(0, 0, 0), Coords(4, 0, 0), true);

    const auto tiles_before = map->getTiles().size();

    auto player = player_at(game, Coords(0, 0, 0));
    auto controller = std::make_shared<CPlayerController>();
    player->setController(controller);
    controller->setTarget(player, Coords(4, 0, 0));

    auto first_step = resolve_coords(controller->control(player));
    expect_true(first_step == Coords(4, 0, 0),
                "weighted pathing should cross the cheap waypoint edge rather than the expensive band or detour");
    player->moveTo(first_step);
    controller->onStepCommitted(player, first_step);

    expect_true(player->getCoords() == Coords(4, 0, 0), "the weighted edge crossing should reach the target");
    expect_true(controller->isCompleted(player), "reaching the target through the edge should complete the controller");
    expect_true(map->getTiles().size() == tiles_before, "weighted edge pathing should not materialize extra tiles");
}

void test_player_controller_uses_navigation_neighbors_for_cross_level_route() {
    auto game = std::make_shared<CGame>();
    auto map = open_tile_map(game, 3, 1, 2);
    auto player = player_at(game, Coords(0, 0, 0));
    auto controller = std::make_shared<CPlayerController>();
    player->setController(controller);

    add_navigation_edge(map, Coords(1, 0, 0), Coords(1, 0, 1));
    controller->setTarget(player, Coords(2, 0, 1));

    auto first = resolve_coords(controller->control(player));
    expect_true(first == Coords(1, 0, 0), "player navigation route should first approach the authored edge");
    player->moveTo(first);
    controller->onStepCommitted(player, first);

    auto second = resolve_coords(controller->control(player));
    expect_true(second == Coords(1, 0, 1), "player navigation route should cross the authored z-level edge");
    player->moveTo(second);
    controller->onStepCommitted(player, second);

    auto third = resolve_coords(controller->control(player));
    expect_true(third == Coords(2, 0, 1), "player navigation route should finish on the target level");
}

void test_target_controller_flow_field_uses_navigation_neighbors_for_cross_level_pursuit() {
    auto game = std::make_shared<CGame>();
    auto map = open_tile_map(game, 3, 1, 2);
    add_navigation_edge(map, Coords(1, 0, 0), Coords(1, 0, 1));

    auto target = std::make_shared<CMapObject>();
    target->setGame(game);
    target->setName("unitTargetAcrossLevels");
    target->setCoords(Coords(2, 0, 1));
    map->addObject(target);

    auto chaser = creature_at(0, 0, 0);
    chaser->setGame(game);
    chaser->setName("unitChaserAcrossLevels");
    chaser->setHp(1);
    auto controller = std::make_shared<CTargetController>();
    controller->setTarget("unitTargetAcrossLevels");
    chaser->setController(controller);
    map->addObject(chaser);

    performance_guard::clearTargetFlowCache();
    auto first = resolve_coords(controller->control(chaser));
    expect_true(first == Coords(1, 0, 0), "target flow field should approach an authored z-level edge");
    chaser->moveTo(first);

    auto second = resolve_coords(controller->control(chaser));
    expect_true(second == Coords(1, 0, 1), "target flow field should cross the authored z-level edge");
}

void test_player_controller_respects_disabled_and_one_way_cross_level_edges() {
    auto game = std::make_shared<CGame>();
    auto map = open_tile_map(game, 3, 1, 2);
    add_navigation_edge(map, Coords(1, 0, 0), Coords(1, 0, 1), false, false);

    auto player = player_at(game, Coords(1, 0, 0));
    auto controller = std::make_shared<CPlayerController>();
    player->setController(controller);

    controller->setTarget(player, Coords(1, 0, 1));
    expect_true(resolve_coords(controller->control(player)) == Coords(1, 0, 0),
                "disabled cross-level edges should not produce a player route");

    map = open_tile_map(game, 3, 1, 2);
    add_navigation_edge(map, Coords(1, 0, 1), Coords(1, 0, 0));

    auto lower_player = player_at(game, Coords(1, 0, 0));
    auto lower_controller = std::make_shared<CPlayerController>();
    lower_player->setController(lower_controller);
    lower_controller->setTarget(lower_player, Coords(1, 0, 1));
    expect_true(resolve_coords(lower_controller->control(lower_player)) == Coords(1, 0, 0),
                "one-way drops should not be usable in reverse");

    auto upper_player = player_at(game, Coords(1, 0, 1));
    auto upper_controller = std::make_shared<CPlayerController>();
    upper_player->setController(upper_controller);
    upper_controller->setTarget(upper_player, Coords(1, 0, 0));
    expect_true(resolve_coords(upper_controller->control(upper_player)) == Coords(1, 0, 0),
                "one-way drops should route from the upper level to the lower level");
}

void test_player_controller_uses_bidirectional_cross_level_edge_both_ways() {
    auto game = std::make_shared<CGame>();
    auto map = open_tile_map(game, 3, 1, 2);
    add_navigation_edge(map, Coords(1, 0, 0), Coords(1, 0, 1), true);

    auto lower_player = player_at(game, Coords(0, 0, 0));
    auto lower_controller = std::make_shared<CPlayerController>();
    lower_player->setController(lower_controller);
    lower_controller->setTarget(lower_player, Coords(2, 0, 1));

    auto lower_first = resolve_coords(lower_controller->control(lower_player));
    expect_true(lower_first == Coords(1, 0, 0), "bidirectional stairs should be reachable from the lower level");
    lower_player->moveTo(lower_first);
    lower_controller->onStepCommitted(lower_player, lower_first);

    auto lower_second = resolve_coords(lower_controller->control(lower_player));
    expect_true(lower_second == Coords(1, 0, 1), "bidirectional stairs should cross upward");

    auto upper_player = player_at(game, Coords(2, 0, 1));
    auto upper_controller = std::make_shared<CPlayerController>();
    upper_player->setController(upper_controller);
    upper_controller->setTarget(upper_player, Coords(0, 0, 0));

    auto upper_first = resolve_coords(upper_controller->control(upper_player));
    expect_true(upper_first == Coords(1, 0, 1), "bidirectional stairs should be reachable from the upper level");
    upper_player->moveTo(upper_first);
    upper_controller->onStepCommitted(upper_player, upper_first);

    auto upper_second = resolve_coords(upper_controller->control(upper_player));
    expect_true(upper_second == Coords(1, 0, 0), "bidirectional stairs should cross downward");
}

void test_target_controller_flow_field_invalidates_when_cross_level_edge_is_added() {
    auto game = std::make_shared<CGame>();
    auto map = open_tile_map(game, 3, 1, 2);

    auto target = std::make_shared<CMapObject>();
    target->setGame(game);
    target->setName("unitTargetAfterEdgeChange");
    target->setCoords(Coords(1, 0, 1));
    map->addObject(target);

    auto chaser = creature_at(1, 0, 0);
    chaser->setGame(game);
    chaser->setName("unitChaserAfterEdgeChange");
    chaser->setHp(1);
    auto controller = std::make_shared<CTargetController>();
    controller->setTarget("unitTargetAfterEdgeChange");
    chaser->setController(controller);
    map->addObject(chaser);

    performance_guard::clearTargetFlowCache();
    expect_true(resolve_coords(controller->control(chaser)) == Coords(1, 0, 0),
                "target flow field should stay put before the cross-level edge exists");

    add_navigation_edge(map, Coords(1, 0, 0), Coords(1, 0, 1));
    expect_true(resolve_coords(controller->control(chaser)) == Coords(1, 0, 1),
                "target flow field should use a newly added cross-level edge");
}

void test_fight_controller_guard_paths_and_fallbacks() {
    auto attacker = creature_at(0, 0, 0);
    auto opponent = creature_at(1, 0, 0);
    auto extra = creature_at(2, 0, 0);

    auto fight_controller = std::make_shared<CFightController>();
    expect_true(!fight_controller->control(nullptr, opponent), "base fight controller should reject null attackers");
    expect_true(!fight_controller->control(attacker, nullptr), "base fight controller should reject null opponents");
    expect_true(fight_controller->control(attacker, opponent), "base fight controller should accept two creatures");
    fight_controller->start(attacker, opponent);
    fight_controller->end(attacker, opponent);
    fight_controller->setOpponents(attacker, {opponent, extra});
    expect_true(fight_controller->selectOpponent(attacker, {opponent, extra}, extra) == extra,
                "base fight controller should keep a current valid opponent");
    expect_true(fight_controller->selectOpponent(attacker, {opponent, extra}, nullptr) == opponent,
                "base fight controller should fall back to the first opponent");
    expect_true(fight_controller->selectOpponent(attacker, {}, nullptr) == nullptr,
                "base fight controller should return null for empty opponent lists");

    auto monster_controller = std::make_shared<CMonsterFightController>();
    expect_true(!monster_controller->control(nullptr, opponent),
                "monster fight controller should reject null attackers");
    expect_true(!monster_controller->control(attacker, nullptr),
                "monster fight controller should reject null opponents");
    expect_true(!monster_controller->control(attacker, opponent),
                "monster fight controller should do nothing without items or interactions");

    auto player_controller = std::make_shared<CPlayerFightController>();
    expect_true(!player_controller->control(nullptr, opponent), "player fight controller should reject null attackers");
    expect_true(!player_controller->control(attacker, nullptr), "player fight controller should reject null opponents");
    expect_true(!player_controller->control(attacker, opponent),
                "player fight controller should fail closed before a creature has a map");
    player_controller->start(nullptr, opponent);
    player_controller->start(attacker, opponent);
    player_controller->end(nullptr, opponent);
    player_controller->end(attacker, opponent);
    player_controller->setOpponents(attacker, {opponent});
    expect_true(player_controller->selectOpponent(attacker, {opponent}, nullptr) == opponent,
                "player fight controller should fall back to base opponent selection without a panel");
}

std::shared_ptr<CGame> fight_panel_game(const std::shared_ptr<CGui> &gui) {
    type_registration::registerGuiTypes();
    type_registration::registerGuiPanelTypes();
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    game->setGui(gui);
    map->setGame(game);
    gui->setGame(game);
    // CPlayerFightController::start() builds the panel via createObject<CGameFightPanel>("fightPanel").
    // The real game resolves that name through res/config/panels.json; without it, the object handler
    // falls back to class-name construction of "fightPanel" (not a registered class) and returns null,
    // crashing start(). Register a minimal class-only config so a real, child-less panel is created
    // (no JSON child views => no texture/renderer work during setEnemies()/refreshEncounterViews()).
    for (const auto &[name, builder] : *CTypes::builders()) {
        game->getObjectHandler()->registerType(name, builder);
    }
    auto fightPanelConfig = std::make_shared<json>();
    (*fightPanelConfig)["class"] = "CGameFightPanel";
    game->getObjectHandler()->registerConfig("fightPanel", fightPanelConfig);
    return game;
}

std::size_t count_fight_panels(const std::shared_ptr<CGui> &gui) {
    std::size_t count = 0;
    for (const auto &child : gui->getChildren()) {
        if (vstd::cast<CGameFightPanel>(child)) {
            ++count;
        }
    }
    return count;
}

std::shared_ptr<CCreature> map_creature(const std::shared_ptr<CGame> &game, const std::string &name, Coords coords) {
    auto creature = creature_at(coords.x, coords.y, coords.z);
    creature->setGame(game);
    creature->setName(name);
    creature->setHp(creature->getHpMax());
    game->getMap()->addObject(creature);
    return creature;
}

void test_player_fight_controller_start_is_idempotent_and_guards_invalid_encounters() {
    auto gui = std::make_shared<CGui>();
    auto game = fight_panel_game(gui);
    auto map = game->getMap();

    auto attacker = map_creature(game, "unitFightAttacker", Coords(0, 0, 0));
    auto opponent = map_creature(game, "unitFightOpponent", Coords(1, 0, 0));

    auto controller = std::make_shared<CPlayerFightController>();
    attacker->setFightController(controller);

    controller->start(attacker, opponent);
    expect_true(count_fight_panels(gui) == 1, "starting a fight should add exactly one fight panel to the GUI");

    // Starting a second fight must discard the first panel instead of leaking or duplicating it.
    controller->start(attacker, opponent);
    expect_true(count_fight_panels(gui) == 1,
                "starting a second fight should not leak or duplicate the fight panel under the GUI");

    controller->end(attacker, opponent);
    expect_true(count_fight_panels(gui) == 0, "ending a fight should remove the fight panel from the GUI");

    // Refuse to start with a missing opponent.
    controller->start(attacker, nullptr);
    expect_true(count_fight_panels(gui) == 0, "fight controller should not create a panel for a null opponent");
    expect_true(controller->isCancelled(attacker, opponent),
                "fight controller should fail closed when refusing to start");

    // Refuse to start when the opponent is not present in the active map.
    auto detached = creature_at(2, 0, 0);
    detached->setGame(game);
    detached->setName("unitDetachedOpponent");
    detached->setHp(detached->getHpMax());
    controller->start(attacker, detached);
    expect_true(count_fight_panels(gui) == 0,
                "fight controller should not bind a panel to an opponent absent from the active map");

    // Accept an engine-initiated fight that resolves on the encounter map even while the
    // active game map has advanced (e.g. a scene transition pending after the strike).
    // The guard must use the encounter map (me->getMap()), not game->getMap().
    auto pendingMap = std::make_shared<CMap>();
    pendingMap->setGame(game);
    game->setMap(pendingMap);
    controller->start(attacker, opponent);
    expect_true(count_fight_panels(gui) == 1,
                "fight controller should still start when the active game map has advanced past the encounter map");
    controller->end(attacker, opponent);
    expect_true(count_fight_panels(gui) == 0, "ending the transitional fight should remove the panel");
    game->setMap(map);

    // Refuse to start when the GUI is missing.
    auto guiless = std::make_shared<CGame>();
    auto guiless_map = std::make_shared<CMap>();
    guiless->setMap(guiless_map);
    guiless_map->setGame(guiless);
    auto guiless_attacker = map_creature(guiless, "unitNoGuiAttacker", Coords(0, 0, 0));
    auto guiless_opponent = map_creature(guiless, "unitNoGuiOpponent", Coords(1, 0, 0));
    auto guiless_controller = std::make_shared<CPlayerFightController>();
    guiless_controller->start(guiless_attacker, guiless_opponent);
    expect_true(guiless_controller->isCancelled(guiless_attacker, guiless_opponent),
                "fight controller should refuse to start without a GUI");
}

void test_player_fight_controller_end_is_idempotent_and_guards_invalid_encounters() {
    auto gui = std::make_shared<CGui>();
    auto game = fight_panel_game(gui);
    auto map = game->getMap();

    auto attacker = map_creature(game, "unitEndAttacker", Coords(0, 0, 0));
    auto opponent = map_creature(game, "unitEndOpponent", Coords(1, 0, 0));

    auto controller = std::make_shared<CPlayerFightController>();
    attacker->setFightController(controller);

    controller->start(attacker, opponent);
    expect_true(count_fight_panels(gui) == 1, "starting a fight should add exactly one fight panel to the GUI");

    controller->end(attacker, opponent);
    expect_true(count_fight_panels(gui) == 0, "ending a fight should remove the fight panel from the GUI");

    // A second end() must be a clean no-op: no panel remains and nothing crashes.
    controller->end(attacker, opponent);
    expect_true(count_fight_panels(gui) == 0, "ending a fight twice should leave no panel under the GUI");

    // end() before any start() (no panel) is a no-op.
    auto freshController = std::make_shared<CPlayerFightController>();
    freshController->end(attacker, opponent);
    expect_true(count_fight_panels(gui) == 0, "ending without a started fight should be a no-op");

    // end() must clear the panel even when the player is missing.
    controller->start(attacker, opponent);
    expect_true(count_fight_panels(gui) == 1, "restarting a fight should re-add the panel");
    controller->end(nullptr, opponent);
    expect_true(count_fight_panels(gui) == 0,
                "ending with a missing player should still remove the panel from the GUI");
    controller->end(nullptr, opponent);
    expect_true(count_fight_panels(gui) == 0, "ending twice with a missing player should leave no panel");

    // end() must clear the panel even after the player's map object was removed.
    controller->start(attacker, opponent);
    expect_true(count_fight_panels(gui) == 1, "restarting a fight should re-add the panel");
    map->removeObject(attacker);
    controller->end(attacker, opponent);
    expect_true(count_fight_panels(gui) == 0,
                "ending after the player object was removed from the map should still remove the panel");
    map->addObject(attacker);

    // end() must clear the panel even when the active game map has advanced past the encounter.
    controller->start(attacker, opponent);
    expect_true(count_fight_panels(gui) == 1, "restarting a fight should re-add the panel");
    auto pendingMap = std::make_shared<CMap>();
    pendingMap->setGame(game);
    game->setMap(pendingMap);
    controller->end(attacker, opponent);
    expect_true(count_fight_panels(gui) == 0,
                "ending after the active map advanced past the encounter should still remove the panel");
    game->setMap(map);

    // end() must not crash when the GUI/game backing the controller is gone.
    auto guiless = std::make_shared<CGame>();
    auto guiless_map = std::make_shared<CMap>();
    guiless->setMap(guiless_map);
    guiless_map->setGame(guiless);
    auto guiless_attacker = map_creature(guiless, "unitEndNoGuiAttacker", Coords(0, 0, 0));
    auto guiless_opponent = map_creature(guiless, "unitEndNoGuiOpponent", Coords(1, 0, 0));
    auto guiless_controller = std::make_shared<CPlayerFightController>();
    guiless_controller->start(guiless_attacker, guiless_opponent);
    guiless_controller->end(guiless_attacker, guiless_opponent);
    guiless_controller->end(guiless_attacker, guiless_opponent);
}

void test_monster_fight_controller_uses_mana_item_when_mana_is_low() {
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);

    auto monster = creature_at(0, 0, 0);
    monster->setGame(game);
    monster->getBaseStats()->setIntelligence(10);
    monster->setHp(monster->getHpMax());
    monster->setMana(0);

    auto opponent = creature_at(1, 0, 0);
    opponent->setGame(game);

    auto mana_potion = std::make_shared<CPotion>();
    mana_potion->setGame(game);
    mana_potion->setPower(5);
    mana_potion->addTag(CTag::Mana);
    monster->addItem(mana_potion);

    auto controller = std::make_shared<CMonsterFightController>();
    expect_true(controller->control(monster, opponent),
                "monster fight controller should use a mana item when mana is low");
    expect_true(monster->getItems().empty(), "used disposable mana item should be removed from inventory");
}

std::shared_ptr<CGame> fight_fixture_game() {
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    return game;
}

std::shared_ptr<CCreature> fight_fixture_monster(const std::shared_ptr<CGame> &game, int stamina, int hp) {
    auto monster = creature_at(0, 0, 0);
    monster->setGame(game);
    monster->getBaseStats()->setStamina(stamina);
    monster->setHp(hp);
    return monster;
}

std::shared_ptr<CCreature> fight_fixture_hitter(const std::shared_ptr<CGame> &game, int dmg) {
    auto opponent = creature_at(1, 0, 0);
    opponent->setGame(game);
    opponent->getBaseStats()->setDmgMin(dmg);
    opponent->getBaseStats()->setDmgMax(dmg);
    return opponent;
}

std::shared_ptr<CPotion> heal_potion(const std::shared_ptr<CGame> &game, int power) {
    auto potion = std::make_shared<CPotion>();
    potion->setGame(game);
    potion->setPower(power);
    potion->addTag(CTag::Heal);
    return potion;
}

void test_monster_fight_controller_attacks_hard_hitter_instead_of_wasting_heal() {
    auto game = fight_fixture_game();
    // hpMax 70, hp 35 (50%): the old fixed 75% threshold healed reflexively here.
    auto monster = fight_fixture_monster(game, 10, 35);
    // One expected landed hit removes 20 hp; the best heal restores ~14 (power 1 -> 20% of 70).
    auto opponent = fight_fixture_hitter(game, 20);
    monster->addItem(heal_potion(game, 1));
    monster->addAction(std::make_shared<CInteraction>());

    auto controller = std::make_shared<CMonsterFightController>();
    expect_true(controller->control(monster, opponent),
                "monster fight controller should attack a hard hitter instead of wasting the turn");
    expect_true(monster->getItems().size() == 1,
                "monster should not spend a heal that is outpaced by one expected enemy hit");
}

void test_monster_fight_controller_heals_when_heal_outpaces_incoming_damage() {
    auto game = fight_fixture_game();
    // hpMax 70, hp 20 (28%): hurt, but the expected 2 hp hit is not lethal.
    auto monster = fight_fixture_monster(game, 10, 20);
    auto opponent = fight_fixture_hitter(game, 2);
    // The strongest heal (power 5, capped by missing hp to 50) clearly outpaces the hit.
    auto weak = heal_potion(game, 1);
    auto strong = heal_potion(game, 5);
    monster->addItem(weak);
    monster->addItem(strong);
    monster->addAction(std::make_shared<CInteraction>());

    auto controller = std::make_shared<CMonsterFightController>();
    expect_true(controller->control(monster, opponent),
                "monster fight controller should heal when the heal is a net gain at low hp");
    expect_true(monster->getItems().size() == 1, "monster fight controller should use only one heal item per turn");
    expect_true(monster->hasItem(strong) && !monster->hasItem(weak),
                "monster fight controller should spend the least powerful heal item first");
}

void test_monster_fight_controller_heals_when_next_hit_would_kill() {
    auto game = fight_fixture_game();
    // hpMax 70, hp 10: the expected 25 hp hit is lethal, so healing is the only play
    // even though the best heal (~14) restores less than the hit removes.
    auto monster = fight_fixture_monster(game, 10, 10);
    auto opponent = fight_fixture_hitter(game, 25);
    monster->addItem(heal_potion(game, 1));
    monster->addAction(std::make_shared<CInteraction>());

    auto controller = std::make_shared<CMonsterFightController>();
    expect_true(controller->control(monster, opponent),
                "monster fight controller should act when the next hit would kill");
    expect_true(monster->getItems().empty(),
                "monster fight controller should heal when it would otherwise die to the next hit");
}

std::shared_ptr<CInteraction> caster_interaction(const std::shared_ptr<CGame> &game, int manaCost,
                                                 std::shared_ptr<CEffect> effect) {
    // Build through the object factory (like createObject in test_core/test_object) so the
    // interaction and its effect carry the meta initialization CInteraction::onAction relies on
    // when it clones the effect (a bare make_shared effect throws bad_any_cast on clone<CEffect>()).
    auto interaction = game->createObject<CInteraction>("CInteraction");
    interaction->setManaCost(manaCost);
    if (effect) {
        interaction->setEffect(effect);
    }
    return interaction;
}

std::shared_ptr<CEffect> opponent_debuff(const std::shared_ptr<CGame> &game, int duration) {
    auto effect = game->createObject<CEffect>("CEffect");
    effect->setDuration(duration);
    return effect;
}

void test_monster_fight_controller_ranks_interactions_by_weakening() {
    auto game = fight_fixture_game();
    auto monster = creature_at(0, 0, 0);
    monster->setGame(game);
    // A single landed hit lands 10 damage; the opponent has no armor/resist.
    monster->getBaseStats()->setStamina(10);
    monster->getBaseStats()->setDmgMax(10);
    monster->setHp(monster->getHpMax());
    // Enough mana for the strong (10) and weak (50) spells, but not the debuff bomb (100).
    monster->getBaseStats()->setIntelligence(100);
    monster->setMana(60);

    auto opponent = creature_at(1, 0, 0);
    opponent->setGame(game);
    opponent->getBaseStats()->setStamina(10);

    // Distinct names keep the three apart in the effective interaction set, which
    // dedupes by typeId then name: bare interactions share the empty-name key and
    // would collapse to one (real config-backed interactions carry distinct typeIds).
    // Weak but expensive: no lingering effect, so its weakening value is just the hit.
    auto weakPricey = caster_interaction(game, 50, nullptr);
    weakPricey->setName("weakPricey");
    // Strong but cheap: a 3-turn opponent debuff makes it the most weakening cast.
    auto strongCheap = caster_interaction(game, 10, opponent_debuff(game, 3));
    strongCheap->setName("strongCheap");
    // Strongest on paper (5-turn debuff) but unaffordable, so it must be skipped.
    auto strongestUnaffordable = caster_interaction(game, 100, opponent_debuff(game, 5));
    strongestUnaffordable->setName("strongestUnaffordable");
    monster->addAction(weakPricey);
    monster->addAction(strongCheap);
    monster->addAction(strongestUnaffordable);

    auto controller = std::make_shared<CMonsterFightController>();
    expect_true(controller->control(monster, opponent), "monster fight controller should cast a weakening interaction");
    // Casting spends the chosen spell's mana: 60 - 10 uniquely identifies the cheap,
    // strongly-weakening spell over the pricey weak one (would leave 10) and proves the
    // unaffordable debuff bomb (needs 100) was filtered out by mana affordability.
    expect_true(monster->getMana() == 50,
                "monster fight controller should pick the most weakening affordable interaction, not the priciest");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_movement_controller_null_and_no_map_paths();
    test_npc_random_controller_clears_current_tile_path();
    test_npc_random_controller_clears_stale_blocked_path();
    test_ground_controller_ignores_stale_transition_generation();
    test_player_controller_prefers_longer_lower_cost_route();
    test_npc_random_controller_prefers_longer_lower_cost_route();
    test_target_controller_flow_field_prefers_longer_lower_cost_route();
    test_player_controller_prefers_cheap_navigation_edge_over_expensive_band();
    test_player_controller_uses_navigation_neighbors_for_cross_level_route();
    test_target_controller_flow_field_uses_navigation_neighbors_for_cross_level_pursuit();
    test_player_controller_respects_disabled_and_one_way_cross_level_edges();
    test_player_controller_uses_bidirectional_cross_level_edge_both_ways();
    test_target_controller_flow_field_invalidates_when_cross_level_edge_is_added();
    test_fight_controller_guard_paths_and_fallbacks();
    test_player_fight_controller_start_is_idempotent_and_guards_invalid_encounters();
    test_player_fight_controller_end_is_idempotent_and_guards_invalid_encounters();
    test_monster_fight_controller_uses_mana_item_when_mana_is_low();
    test_monster_fight_controller_attacks_hard_hitter_instead_of_wasting_heal();
    test_monster_fight_controller_heals_when_heal_outpaces_incoming_damage();
    test_monster_fight_controller_heals_when_next_hit_would_kill();
    test_monster_fight_controller_ranks_interactions_by_weakening();

    return finish_tests();
}
