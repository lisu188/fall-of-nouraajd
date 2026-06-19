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
#include "core/CPlaytestTrace.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "test_harness.h"

#include <SDL.h>
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

class CompletedQuest : public CQuest {
  public:
    int complete_count = 0;

    bool isCompleted() override { return true; }

    void onComplete() override { complete_count++; }
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

    expect_true(CFightHandler::fightManyOutcome(attacker, {stale}) == CFightOutcome::Invalid,
                "stale same-name opponents should be rejected before combat starts");
    expect_true(map->getObjectByName("unitReplaceableOpponent") == replacement,
                "combat with a stale opponent should not mutate the replacement");

    map->removeObjectByName("unitReplaceableOpponent");
    expect_true(map->getObjectByName("unitReplaceableOpponent") == nullptr,
                "removeObjectByName should remain the explicit name-based removal API");

    auto second_game = load_empty_game();
    auto cross_map = add_test_creature(second_game, "unitCrossMapOpponent", 1, 0);
    expect_true(CFightHandler::fightManyOutcome(attacker, {cross_map}) == CFightOutcome::Invalid,
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

    expect_true(outcome == CFightOutcome::AttackerDefeat, "attacker death from an effect should be AttackerDefeat");
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

    expect_true(victory == CFightOutcome::AttackerVictory, "opponent effect death should resolve as attacker victory");
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

    expect_true(invalid_outcome == CFightOutcome::AttackerDefeat,
                "invalid-caster lethal effects should still resolve the loser");
    expect_true(unrelated->countItems("unitInvalidCasterLoot") == 0,
                "invalid effect casters should not cause unrelated opponents to receive loot");
    expect_true(invalid_game->getMap()->getObjectByName(invalid_victim->getName()) == nullptr,
                "losers killed by invalid-caster effects should still be cleaned up");
}

void test_fight_handler_reports_explicit_outcomes_and_final_status() {
    const CFightResult default_result;
    expect_true(default_result.outcome == CFightOutcome::Invalid && default_result.rounds == 0,
                "default fight results should construct as invalid with no rounds");
    expect_true(!default_result.resolved() && !default_result.attackerSucceeded(),
                "default fight results should not collapse invalid combat into a resolved bool");

    auto victory_game = load_empty_game();
    auto victor = add_test_creature(victory_game, "unitOutcomeVictor");
    victor->setFightController(std::make_shared<KillingFightController>());
    auto defeated = add_test_creature(victory_game, "unitOutcomeDefeated", 1, 0);
    auto victory_controller = std::dynamic_pointer_cast<KillingFightController>(victor->getFightController());
    const CFightResult cancelled_result{CFightOutcome::Cancelled, 3, victor, defeated};
    expect_true(cancelled_result.outcome == CFightOutcome::Cancelled && cancelled_result.rounds == 3,
                "fight results should construct with explicit cancelled outcome data");

    const auto victory = CFightHandler::fightManyResult(victor, {defeated});

    expect_true(victory.outcome == CFightOutcome::AttackerVictory,
                "direct attacker victory should be reported explicitly");
    expect_true(victory.rounds == 1, "direct attacker victory should report the completed round count");
    expect_true(victory.survivor == victor && victory.opponent == defeated,
                "direct attacker victory should report survivor and opponent metadata");
    expect_true(victory.resolved() && victory.attackerSucceeded(),
                "result helpers should identify successful resolved combat");
    expect_true(CFightHandler::fightManyOutcome(victor, {defeated}) == CFightOutcome::Invalid,
                "enum compatibility wrapper should still be constructible for invalid post-victory input");
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

    const auto stalemate = CFightHandler::fightManyResult(stalled_attacker, {stalled_defender});

    expect_true(stalemate.outcome == CFightOutcome::Stalled, "no-progress combat should report stalled outcome");
    expect_true(stalemate.rounds == 20, "stalled combat should report the stale round budget consumed");
    expect_true(stalemate.survivor == stalled_attacker && stalemate.opponent == stalled_defender,
                "stalled combat should keep participant metadata instead of only returning false");
    expect_true(!stalemate.resolved() && !stalemate.attackerSucceeded(),
                "result helpers should keep stalled combat separate from resolved combat");
    expect_true(!CFightHandler::fightMany(stalled_attacker, {stalled_defender}),
                "legacy fightMany should still return false for unresolved combat");
    expect_true(stalemate_controller->start_count == 2 && stalemate_controller->end_count == 2,
                "controller cleanup should also run for the legacy stalemate call");

    auto legacy_victory_game = load_empty_game();
    auto legacy_victor = add_test_creature(legacy_victory_game, "unitLegacyOutcomeVictor");
    legacy_victor->setFightController(std::make_shared<KillingFightController>());
    auto legacy_defeated = add_test_creature(legacy_victory_game, "unitLegacyOutcomeDefeated", 1, 0);
    expect_true(CFightHandler::fight(legacy_victor, legacy_defeated),
                "legacy two-creature bool wrapper should still return true for resolved victory");

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

    expect_true(defeat == CFightOutcome::AttackerDefeat, "player defeat should remain visible after respawn");
    expect_true(player_map->getObjectByName("player") == player && player->isAlive() && player->getHp() == 1,
                "player defeat should keep the existing respawn behavior");
    expect_true(status.find("survives the encounter") == std::string::npos,
                "defeated respawned players must not be reported as surviving");
    expect_true(status.find("defeated") != std::string::npos, "final defeat status should be explicit");
}

void test_fight_handler_reports_cancelled_quit_event() {
    expect_true(SDL_InitSubSystem(SDL_INIT_EVENTS) == 0, "SDL event subsystem should initialize for quit events");
    SDL_FlushEvent(SDL_QUIT);

    auto game = load_empty_game();
    auto attacker = add_test_creature(game, "unitCancelledAttacker");
    auto defender = add_test_creature(game, "unitCancelledDefender", 1, 0);
    const auto attacker_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(attacker->getFightController());

    SDL_Event quit_event{};
    quit_event.type = SDL_QUIT;
    expect_true(SDL_PushEvent(&quit_event) == 1, "SDL_QUIT event should be queued for cancellation coverage");

    const auto result = CFightHandler::fightManyResult(attacker, {defender});
    SDL_FlushEvent(SDL_QUIT);

    expect_true(result.outcome == CFightOutcome::Cancelled, "queued SDL_QUIT should report cancelled combat");
    expect_true(result.rounds == 0, "cancelled combat before a turn should report no completed rounds");
    expect_true(result.survivor == attacker && result.opponent == defender,
                "cancelled combat should keep participant metadata");
    expect_true(!result.resolved() && !result.attackerSucceeded(),
                "cancelled combat should stay distinct from resolved bool outcomes");
    expect_true(attacker_controller->start_count == 1 && attacker_controller->end_count == 1,
                "controller cleanup should run when combat is cancelled");
    expect_true(game->getMap()->getStringProperty("combatStatus").find("interrupted") != std::string::npos,
                "cancelled combat should publish the interrupted status text");
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

    expect_true(outcome == CFightOutcome::Stalled, "timed no-damage effects should still end in stalled outcome");
    expect_true(effect->ticks == 25, "duration changes should prevent stale termination before effect expiration");
    expect_true(attacker->getEffects().empty(), "expired effects should be removed before stale termination resumes");
    expect_true(game->getMap()->getObjectByName(attacker->getName()) == attacker &&
                    game->getMap()->getObjectByName(defender->getName()) == defender,
                "timed-effect stale handling should not remove living participants");
}

void test_playtest_trace_records_native_limits_and_quest_completion() {
    CPlaytestTrace::configure(true, "", 2);
    CPlaytestTrace::recordJson("native_empty_fields", "");
    CPlaytestTrace::recordJson("native_array_fields", "[1]");
    CPlaytestTrace::record("native_over_limit");
    CPlaytestTrace::record("native_after_truncation");

    const auto limited_records = CPlaytestTrace::records();
    bool saw_truncation = false;
    for (const auto &line : limited_records) {
        const auto record = json::parse(line);
        saw_truncation = saw_truncation || record.value("event", std::string()) == "trace_truncated";
    }
    expect_true(limited_records.size() == 3 && saw_truncation,
                "playtest trace should append one truncation record after the configured limit");

    const auto drained = CPlaytestTrace::drain();
    expect_true(drained.size() == limited_records.size() && CPlaytestTrace::records().empty(),
                "drain should return and clear buffered trace records");

    CPlaytestTrace::configure(true, "", 100);
    expect_true(CPlaytestTrace::objectRef(nullptr).is_null(), "null object refs should serialize as JSON null");
    expect_true(CPlaytestTrace::objectRefs({}).empty(), "empty object ref collections should serialize as arrays");
    expect_true(CPlaytestTrace::itemRefs({}).empty(), "empty item ref collections should serialize as arrays");

    json mapless_fields = {{"coords", CPlaytestTrace::coords(Coords(1, 2, 3))}};
    CPlaytestTrace::addMapContext(mapless_fields, nullptr);
    expect_true(!mapless_fields.contains("map"), "map context should not be added for null maps");

    auto game = CGameLoader::loadGame();
    CGameLoader::startGameWithPlayer(game, "empty", "Warrior");
    auto player = game->getMap()->getPlayer();
    auto quest = std::make_shared<CompletedQuest>();
    quest->setName("unitCompletedQuest");
    quest->setTypeId("unitCompletedQuest");
    player->setQuests({quest});

    player->checkQuests();

    expect_true(quest->complete_count == 1, "completed quest callbacks should run exactly once");
    expect_true(player->getQuests().empty(), "completed quests should leave the active quest set");
    expect_true(player->getCompletedQuests().count(quest) == 1, "completed quests should move to the completed set");

    bool saw_completion = false;
    for (const auto &line : CPlaytestTrace::drain()) {
        const auto record = json::parse(line);
        saw_completion =
            saw_completion || (record.value("event", std::string()) == "quest_completed" &&
                               record.value("quest", std::string()) == "unitCompletedQuest" && record.contains("map"));
    }
    expect_true(saw_completion, "quest completion should be recorded with map context when tracing is enabled");
    CPlaytestTrace::configure(false);
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
    test_fight_handler_reports_cancelled_quit_event();
    test_fight_handler_counts_effect_duration_as_progress();
    test_playtest_trace_records_native_limits_and_quest_completion();
    test_player_respawn_normalizes_wrapped_entry_coords();

    return finish_tests();
}
