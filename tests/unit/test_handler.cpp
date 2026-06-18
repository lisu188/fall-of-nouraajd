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

#include "handler/CGuiHandler.h"
#include "handler/CFightHandler.h"
#include "handler/CQuestHandler.h"
#include "handler/CRngHandler.h"
#include "handler/CScriptHandler.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CItem.h"
#include "test_harness.h"

#include <pybind11/embed.h>
#include <memory>
#include <set>
#include <string>

namespace {

class NoProgressFightController : public CFightController {
  public:
    int start_count = 0;
    int end_count = 0;

    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return true; }

    void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { start_count++; }

    void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { end_count++; }
};

class KillingFightController : public NoProgressFightController {
  public:
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature> opponent) override {
        if (opponent) {
            opponent->setHp(0);
        }
        return true;
    }
};

class LethalEffect : public CEffect {
  public:
    void onEffect() override {
        if (auto victim = getVictim()) {
            victim->setHp(0);
        }
    }
};

class CountingEffect : public CEffect {
  public:
    int ticks = 0;

    void onEffect() override { ticks++; }
};

std::shared_ptr<CGame> load_empty_game() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGame(game, "empty");
    return game;
}

std::shared_ptr<CCreature> add_test_creature(const std::shared_ptr<CGame> &game, const std::string &name, int x = 0,
                                             int y = 0) {
    auto creature = game->createObject<CCreature>("CCreature");
    creature->setName(name);
    creature->getBaseStats()->setAgility(10);
    creature->getBaseStats()->setHit(100);
    creature->getBaseStats()->setCrit(0);
    creature->getBaseStats()->setDmgMin(0);
    creature->getBaseStats()->setDmgMax(0);
    creature->setHp(10);
    creature->setFightController(std::make_shared<NoProgressFightController>());
    creature->setPosX(x);
    creature->setPosY(y);
    creature->setPosZ(0);
    game->getMap()->addObject(creature);
    creature->setHp(10);
    return creature;
}

std::shared_ptr<CItem> add_unit_loot(const std::shared_ptr<CGame> &game, const std::shared_ptr<CCreature> &creature,
                                     const std::string &name) {
    auto item = game->createObject<CItem>("CItem");
    item->setName(name);
    item->setTypeId(name);
    creature->addItem(item);
    return item;
}

std::shared_ptr<LethalEffect> attach_lethal_effect(const std::shared_ptr<CCreature> &victim,
                                                   const std::shared_ptr<CCreature> &caster) {
    auto effect = std::make_shared<LethalEffect>();
    effect->setDuration(1);
    effect->setName("unitLethalEffect");
    effect->setTypeId("unitLethalEffect");
    effect->setCaster(caster);
    effect->setVictim(victim);
    victim->addEffect(effect);
    return effect;
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

void test_handler_constructors_are_covered_by_native_tests() {
    CQuestHandler quest_handler;
    CRngHandler rng_handler;
    CGuiHandler gui_handler;

    expect_true(CGuiHandler::static_meta()->name() == "CGuiHandler",
                "GUI handler metadata should expose its type name");
    expect_true(gui_handler.meta()->inherits("CGameObject"), "GUI handler metadata should preserve its object base");
    gui_handler.showMessage("native handler constructor coverage");
    gui_handler.showInfo("native handler info coverage");
    expect_true(!gui_handler.showQuestion("native handler question coverage"),
                "headless GUI handler questions should return false");
    expect_true(rng_handler.getRandomLoot(0).empty(), "default RNG handler should return no loot without a game");
    expect_true(rng_handler.getRandomEncounter(0).empty(),
                "default RNG handler should return no encounters without a game");
    (void)quest_handler;
}

void test_fight_handler_rejects_stale_and_cross_map_participants() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitIdentityAttacker");
    auto stale = add_test_creature(game, "unitReplaceableOpponent", 1, 0);
    map->removeObject(stale);

    auto replacement = add_test_creature(game, "unitReplaceableOpponent", 1, 0);
    map->removeObject(stale);
    expect_true(map->getObjectByName("unitReplaceableOpponent") == replacement,
                "removeObject should not erase a same-name replacement through a stale reference");

    expect_true(CFightHandler::fightManyOutcome(attacker, {stale}) == CFightOutcome::invalid,
                "stale same-name opponents should be rejected before combat starts");
    expect_true(map->getObjectByName("unitReplaceableOpponent") == replacement,
                "combat with a stale opponent should not mutate the replacement");

    map->removeObjectByName("unitReplaceableOpponent");
    expect_true(map->getObjectByName("unitReplaceableOpponent") == nullptr,
                "removeObjectByName should remain the explicit name-based removal API");

    auto second_game = load_empty_game();
    auto cross_map = add_test_creature(second_game, "unitCrossMapOpponent", 1, 0);
    expect_true(CFightHandler::fightManyOutcome(attacker, {cross_map}) == CFightOutcome::invalid,
                "cross-map opponents should fail closed");
    expect_true(map->getObjectByName(attacker->getName()) == attacker,
                "cross-map rejection should leave the attacker map unchanged");
    expect_true(second_game->getMap()->getObjectByName(cross_map->getName()) == cross_map,
                "cross-map rejection should leave the opponent map unchanged");
}

void test_fight_handler_attributes_lethal_effects_to_valid_casters() {
    auto game = load_empty_game();
    auto attacker = add_test_creature(game, "unitEffectVictim");
    auto selected = add_test_creature(game, "unitASelectedOpponent", 1, 0);
    auto caster = add_test_creature(game, "unitZActualCaster", 1, 0);
    add_unit_loot(game, attacker, "unitCasterOwnedLoot");
    attach_lethal_effect(attacker, caster);

    const auto outcome = CFightHandler::fightManyOutcome(attacker, {selected, caster});

    expect_true(outcome == CFightOutcome::attackerDefeat, "attacker death from an effect should be attackerDefeat");
    expect_true(caster->countItems("unitCasterOwnedLoot") == 1,
                "the effect caster should receive transferable loot from the defeated attacker");
    expect_true(selected->countItems("unitCasterOwnedLoot") == 0,
                "the selected UI target should not receive an effect kill it did not cause");

    auto second_game = load_empty_game();
    auto effect_attacker = add_test_creature(second_game, "unitEffectAttacker");
    auto effect_victim = add_test_creature(second_game, "unitEffectOpponent", 1, 0);
    add_unit_loot(second_game, effect_victim, "unitDelayedOpponentLoot");
    attach_lethal_effect(effect_victim, effect_attacker);

    const auto victory = CFightHandler::fightManyOutcome(effect_attacker, {effect_victim});

    expect_true(victory == CFightOutcome::attackerVictory, "opponent effect death should resolve as attacker victory");
    expect_true(effect_attacker->countItems("unitDelayedOpponentLoot") == 1,
                "attacker-owned delayed effects should grant opponent loot once");
    expect_true(second_game->getMap()->getObjectByName(effect_victim->getName()) == nullptr,
                "effect-killed opponents should be removed once");

    auto invalid_game = load_empty_game();
    auto invalid_victim = add_test_creature(invalid_game, "unitInvalidCasterVictim");
    auto unrelated = add_test_creature(invalid_game, "unitUnrelatedOpponent", 1, 0);
    auto stale_caster = add_test_creature(invalid_game, "unitStaleCaster", 2, 0);
    add_unit_loot(invalid_game, invalid_victim, "unitInvalidCasterLoot");
    attach_lethal_effect(invalid_victim, stale_caster);
    invalid_game->getMap()->removeObject(stale_caster);

    const auto invalid_outcome = CFightHandler::fightManyOutcome(invalid_victim, {unrelated});

    expect_true(invalid_outcome == CFightOutcome::attackerDefeat,
                "invalid-caster lethal effects should still resolve the loser");
    expect_true(unrelated->countItems("unitInvalidCasterLoot") == 0,
                "invalid effect casters should not cause unrelated opponents to receive loot");
    expect_true(invalid_game->getMap()->getObjectByName(invalid_victim->getName()) == nullptr,
                "losers killed by invalid-caster effects should still be cleaned up");
}

void test_fight_handler_reports_explicit_outcomes_and_final_status() {
    auto victory_game = load_empty_game();
    auto victor = add_test_creature(victory_game, "unitOutcomeVictor");
    victor->setFightController(std::make_shared<KillingFightController>());
    auto defeated = add_test_creature(victory_game, "unitOutcomeDefeated", 1, 0);
    auto victory_controller = std::dynamic_pointer_cast<KillingFightController>(victor->getFightController());

    const auto victory = CFightHandler::fightManyOutcome(victor, {defeated});

    expect_true(victory == CFightOutcome::attackerVictory, "direct attacker victory should be reported explicitly");
    expect_true(victory_controller->start_count == 1 && victory_controller->end_count == 1,
                "attacker controller should start and end exactly once on victory");
    expect_true(victory_game->getMap()->getStringProperty("combatStatus").find("survives the encounter") !=
                    std::string::npos,
                "attacker victory should preserve the survivor status text");

    auto stalemate_game = load_empty_game();
    auto stalled_attacker = add_test_creature(stalemate_game, "unitStalledAttacker");
    auto stalled_defender = add_test_creature(stalemate_game, "unitStalledDefender", 1, 0);
    const auto stalemate_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(stalled_attacker->getFightController());

    const auto stalemate = CFightHandler::fightManyOutcome(stalled_attacker, {stalled_defender});

    expect_true(stalemate == CFightOutcome::stalemate, "no-progress combat should report stalemate");
    expect_true(!CFightHandler::fightMany(stalled_attacker, {stalled_defender}),
                "legacy fightMany should still return false for unresolved combat");
    expect_true(stalemate_controller->start_count == 2 && stalemate_controller->end_count == 2,
                "controller cleanup should also run for the legacy stalemate call");

    auto player_game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(player_game, "empty", "Warrior");
    auto player_map = player_game->getMap();
    auto player = player_map->getPlayer();
    player->setHp(1);
    player->setFightController(std::make_shared<NoProgressFightController>());
    auto killer = add_test_creature(player_game, "unitPlayerDefeatKiller", 1, 0);
    killer->setFightController(std::make_shared<KillingFightController>());

    const auto defeat = CFightHandler::fightManyOutcome(player, {killer});
    const auto status = player_map->getStringProperty("combatStatus");

    expect_true(defeat == CFightOutcome::attackerDefeat, "player defeat should remain visible after respawn");
    expect_true(player_map->getObjectByName("player") == player && player->isAlive() && player->getHp() == 1,
                "player defeat should keep the existing respawn behavior");
    expect_true(status.find("survives the encounter") == std::string::npos,
                "defeated respawned players must not be reported as surviving");
    expect_true(status.find("defeated") != std::string::npos, "final defeat status should be explicit");
}

void test_fight_handler_counts_effect_duration_as_progress() {
    auto game = load_empty_game();
    auto attacker = add_test_creature(game, "unitTimedEffectAttacker");
    auto defender = add_test_creature(game, "unitTimedEffectDefender", 1, 0);
    auto effect = std::make_shared<CountingEffect>();
    effect->setDuration(25);
    effect->setName("unitLongCountingEffect");
    effect->setTypeId("unitLongCountingEffect");
    effect->setVictim(attacker);
    attacker->addEffect(effect);

    const auto outcome = CFightHandler::fightManyOutcome(attacker, {defender});

    expect_true(outcome == CFightOutcome::stalemate, "timed no-damage effects should still end in stalemate");
    expect_true(effect->ticks == 25, "duration changes should prevent stale termination before effect expiration");
    expect_true(attacker->getEffects().empty(), "expired effects should be removed before stale termination resumes");
    expect_true(game->getMap()->getObjectByName(attacker->getName()) == attacker &&
                    game->getMap()->getObjectByName(defender->getName()) == defender,
                "timed-effect stale handling should not remove living participants");
}

void test_player_respawn_normalizes_wrapped_entry_coords() {
    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "empty", "Warrior");
    auto map = game->getMap();
    auto player = map->getPlayer();

    map->setXBounds({{0, 1}});
    map->setYBounds({{0, 1}});
    map->setWrapX({{0, 1}});
    map->setEntryX(2);
    map->setEntryY(0);
    map->setEntryZ(0);

    map->removeObject(player);

    expect_true(map->getObjectByName("player") == player, "player destroy trigger should re-add the same player");
    expect_true(player->getCoords() == Coords(0, 0, 0),
                "player respawn should normalize wrapped entry coords before direct coordinate writes");
    expect_true(map->getObjectsAtCoords(Coords(0, 0, 0)).contains(player),
                "player respawn should keep the normalized coordinate cache in sync");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_script_handler_executes_commands_and_wraps_functions();
    test_handler_constructors_are_covered_by_native_tests();
    test_fight_handler_rejects_stale_and_cross_map_participants();
    test_fight_handler_attributes_lethal_effects_to_valid_casters();
    test_fight_handler_reports_explicit_outcomes_and_final_status();
    test_fight_handler_counts_effect_duration_as_progress();
    test_player_respawn_normalizes_wrapped_entry_coords();

    return finish_tests();
}
