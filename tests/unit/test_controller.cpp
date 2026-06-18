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
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "veventloop.h"

#include <pybind11/embed.h>

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

std::shared_ptr<CMap> open_tile_map(const std::shared_ptr<CGame> &game, int width, int height) {
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, width - 1}});
    map->setYBounds({{0, height - 1}});
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            map->addTile(tile(true), x, y, 0);
        }
    }
    return map;
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

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_movement_controller_null_and_no_map_paths();
    test_npc_random_controller_clears_current_tile_path();
    test_npc_random_controller_clears_stale_blocked_path();
    test_fight_controller_guard_paths_and_fallbacks();
    test_monster_fight_controller_uses_mana_item_when_mana_is_low();

    return finish_tests();
}
