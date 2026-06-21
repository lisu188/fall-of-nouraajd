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
#include "core/CStats.h"
#include "gui/CGui.h"
#include "gui/panel/CGameFightPanel.h"
#include "object/CCreature.h"
#include "object/CInteraction.h"
#include "object/CEffect.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "object/CTrigger.h"
#include "test_harness.h"

#include <SDL.h>
#include <pybind11/embed.h>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <utility>

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

class SelfDefeatFightController : public NoProgressFightController {
  public:
    bool control(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature>) override {
        if (actor) {
            actor->setHp(0);
        }
        return true;
    }
};

class CancellingFightController : public NoProgressFightController {
  public:
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return false; }

    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return true; }
};

class ReplacingOnStartFightController : public NoProgressFightController {
  public:
    std::shared_ptr<NoProgressFightController> replacement = std::make_shared<NoProgressFightController>();

    void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        NoProgressFightController::start(me, opponent);
        if (me) {
            me->setFightController(replacement);
        }
    }
};

void set_environment_variable(const std::string &name, const std::optional<std::string> &value) {
#ifdef _WIN32
    _putenv_s(name.c_str(), value ? value->c_str() : "");
#else
    if (value) {
        setenv(name.c_str(), value->c_str(), 1);
    } else {
        unsetenv(name.c_str());
    }
#endif
}

class ScopedEnvironmentVariable {
  public:
    ScopedEnvironmentVariable(std::string name, std::optional<std::string> value) : name(std::move(name)) {
        if (const char *existing = std::getenv(this->name.c_str())) {
            previous = std::string(existing);
        }
        set_environment_variable(this->name, value);
    }

    ~ScopedEnvironmentVariable() { set_environment_variable(name, previous); }

  private:
    std::string name;
    std::optional<std::string> previous;
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

void initialize_test_creature_stats(const std::shared_ptr<CCreature> &creature) {
    creature->setBaseStats(std::make_shared<CStats>());
    creature->setLevelStats(std::make_shared<CStats>());
    creature->getBaseStats()->setMainStat("strength");
    creature->getBaseStats()->setStamina(10);
    creature->getBaseStats()->setStrength(10);
    creature->getBaseStats()->setAgility(10);
    creature->getBaseStats()->setHit(100);
    creature->getBaseStats()->setCrit(0);
    creature->getBaseStats()->setDmgMin(0);
    creature->getBaseStats()->setDmgMax(0);
}

std::shared_ptr<CPlayer> add_test_player(const std::shared_ptr<CGame> &game) {
    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    initialize_test_creature_stats(player);
    player->setHp(10);
    game->getMap()->setPlayer(player);
    player->setController(std::make_shared<CPlayerController>());
    player->setFightController(std::make_shared<CPlayerFightController>());
    player->setHp(10);
    return player;
}

std::shared_ptr<CCreature> add_test_creature(const std::shared_ptr<CGame> &game, const std::string &name, int x = 0,
                                             int y = 0) {
    auto creature = std::make_shared<CCreature>();
    creature->setGame(game);
    creature->setName(name);
    initialize_test_creature_stats(creature);
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
    auto item = std::make_shared<CItem>();
    item->setGame(game);
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

void expect_controller_lifecycle(const std::shared_ptr<NoProgressFightController> &controller, int starts, int ends,
                                 const char *message) {
    expect_true(controller && controller->start_count == starts && controller->end_count == ends, message);
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

std::shared_ptr<CTrigger> make_unit_trigger(const std::string &name, const std::string &typeId) {
    auto trigger = std::make_shared<CTrigger>();
    trigger->setType("CTrigger");
    trigger->setName(name);
    trigger->setTypeId(typeId);
    trigger->setObject("unitObject");
    trigger->setEvent(CGameEvent::CType::onEnter);
    return trigger;
}

void test_event_handler_trigger_registration_uses_named_comparison_helpers() {
    CEventHandler handler;
    auto first = make_unit_trigger("unitDuplicateTrigger", "unitDuplicateTriggerType");
    auto duplicate = make_unit_trigger("unitDuplicateTrigger", "unitDuplicateTriggerType");
    auto same_type_different_name = make_unit_trigger("unitDistinctTrigger", "unitDuplicateTriggerType");

    handler.registerTrigger(first);
    handler.registerTrigger(duplicate);
    expect_true(handler.getTriggers().size() == 1,
                "trigger registration should de-duplicate matching configured trigger registrations");

    handler.registerTrigger(first);
    expect_true(handler.getTriggers().size() == 1,
                "trigger registration should de-duplicate the exact same trigger instance");

    handler.registerTrigger(same_type_different_name);
    expect_true(handler.getTriggers().size() == 2,
                "trigger registration should preserve distinct trigger names with the same configured type id");
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
    auto defeated_controller = std::dynamic_pointer_cast<NoProgressFightController>(defeated->getFightController());
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
    expect_controller_lifecycle(victory_controller, 1, 1,
                                "attacker controller should start and end exactly once on victory");
    expect_controller_lifecycle(defeated_controller, 1, 1,
                                "opponent controller should start and end exactly once on victory");
    expect_true(victory_game->getMap()->getStringProperty("combatStatus").find("survives the encounter") !=
                    std::string::npos,
                "attacker victory should preserve the survivor status text");
    expect_true(CFightHandler::fightManyOutcome(victor, {defeated}) == CFightOutcome::Invalid,
                "enum compatibility wrapper should still be constructible for invalid post-victory input");

    auto stalemate_game = load_empty_game();
    auto stalled_attacker = add_test_creature(stalemate_game, "unitStalledAttacker");
    auto stalled_defender = add_test_creature(stalemate_game, "unitStalledDefender", 1, 0);
    const auto stalemate_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(stalled_attacker->getFightController());
    const auto stalemate_defender_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(stalled_defender->getFightController());

    const auto stalemate = CFightHandler::fightManyResult(stalled_attacker, {stalled_defender});

    expect_true(stalemate.outcome == CFightOutcome::Stalled, "no-progress combat should report stalled outcome");
    expect_true(stalemate.rounds == 20, "stalled combat should report the stale round budget consumed");
    expect_true(stalemate.survivor == stalled_attacker && stalemate.opponent == stalled_defender,
                "stalled combat should keep participant metadata instead of only returning false");
    expect_true(!stalemate.resolved() && !stalemate.attackerSucceeded(),
                "result helpers should keep stalled combat separate from resolved combat");
    expect_true(!CFightHandler::fightMany(stalled_attacker, {stalled_defender}),
                "legacy fightMany should still return false for unresolved combat");
    expect_controller_lifecycle(stalemate_controller, 2, 2,
                                "attacker cleanup should also run for the legacy stalemate call");
    expect_controller_lifecycle(stalemate_defender_controller, 2, 2,
                                "opponent cleanup should also run for the legacy stalemate call");
    expect_true(stalemate_game->getMap()->getStringProperty("combatStatus").find("stalled after 20 rounds") !=
                    std::string::npos,
                "stale-loop termination should publish a diagnostic stalled status");

    auto legacy_victory_game = load_empty_game();
    auto legacy_victor = add_test_creature(legacy_victory_game, "unitLegacyOutcomeVictor");
    legacy_victor->setFightController(std::make_shared<KillingFightController>());
    auto legacy_defeated = add_test_creature(legacy_victory_game, "unitLegacyOutcomeDefeated", 1, 0);
    expect_true(CFightHandler::fight(legacy_victor, legacy_defeated),
                "legacy two-creature bool wrapper should still return true for resolved victory");

    auto player_game = load_empty_game();
    auto player_map = player_game->getMap();
    auto player = add_test_player(player_game);
    player->setHp(1);
    player->setFightController(std::make_shared<NoProgressFightController>());
    const auto player_controller = std::dynamic_pointer_cast<NoProgressFightController>(player->getFightController());
    auto killer = add_test_creature(player_game, "unitPlayerDefeatKiller", 1, 0);
    killer->setFightController(std::make_shared<KillingFightController>());
    const auto killer_controller = std::dynamic_pointer_cast<KillingFightController>(killer->getFightController());

    const auto defeat = CFightHandler::fightManyOutcome(player, {killer});
    const auto status = player_map->getStringProperty("combatStatus");

    expect_true(defeat == CFightOutcome::AttackerDefeat, "player defeat should remain visible after respawn");
    expect_controller_lifecycle(player_controller, 1, 1,
                                "attacker controller should start and end exactly once on defeat");
    expect_controller_lifecycle(killer_controller, 1, 1,
                                "opponent controller should start and end exactly once on defeat");
    expect_true(player_map->getObjectByName("player") == player && player->isAlive() && player->getHp() == 1,
                "player defeat should keep the existing respawn behavior");
    expect_true(status.find("survives the encounter") == std::string::npos,
                "defeated respawned players must not be reported as surviving");
    expect_true(status.find("defeated") != std::string::npos, "final defeat status should be explicit");

    auto self_defeat_game = load_empty_game();
    auto self_defeating_attacker = add_test_creature(self_defeat_game, "unitSelfDefeatingAttacker");
    self_defeating_attacker->setFightController(std::make_shared<SelfDefeatFightController>());
    add_unit_loot(self_defeat_game, self_defeating_attacker, "unitSelfDefeatLoot");
    auto surviving_defender = add_test_creature(self_defeat_game, "unitSelfDefeatDefender", 1, 0);
    const auto self_defeat_controller =
        std::dynamic_pointer_cast<SelfDefeatFightController>(self_defeating_attacker->getFightController());
    const auto surviving_defender_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(surviving_defender->getFightController());

    const auto self_defeat = CFightHandler::fightManyResult(self_defeating_attacker, {surviving_defender});

    expect_true(self_defeat.outcome == CFightOutcome::AttackerDefeat,
                "attackers defeated during their own action should report AttackerDefeat");
    expect_true(self_defeat.survivor == surviving_defender && self_defeat.opponent == self_defeating_attacker,
                "self-defeat should attribute the surviving opponent in result metadata");
    expect_controller_lifecycle(self_defeat_controller, 1, 1,
                                "self-defeat should still end the attacker controller exactly once");
    expect_controller_lifecycle(surviving_defender_controller, 1, 1,
                                "self-defeat should still end the defender controller exactly once");
    expect_true(surviving_defender->countItems("unitSelfDefeatLoot") == 1,
                "self-defeat should grant transferable loot to the surviving opponent");
    expect_true(self_defeat_game->getMap()->getObjectByName(self_defeating_attacker->getName()) == nullptr,
                "self-defeat should remove the defeated attacker from the map");
}

void test_fight_handler_reports_invalid_result_metadata() {
    const auto null_result = CFightHandler::fightManyResult(std::shared_ptr<CCreature>(), {});
    expect_true(null_result.outcome == CFightOutcome::Invalid && null_result.rounds == 0,
                "null attackers should return an invalid empty result");
    expect_true(!null_result.survivor && !null_result.opponent,
                "null attackers should not report stale survivor metadata");

    auto detached = std::make_shared<CCreature>();
    detached->setName("unitDetachedAttacker");
    detached->setFightController(std::make_shared<NoProgressFightController>());
    const auto detached_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(detached->getFightController());
    const auto detached_result = CFightHandler::fightManyResult(detached, {});
    expect_true(detached_result.outcome == CFightOutcome::Invalid,
                "attackers without an active map registration should return invalid");
    expect_controller_lifecycle(detached_controller, 0, 0,
                                "invalid detached combat should not start or end controllers");

    auto game = load_empty_game();
    auto attacker = add_test_creature(game, "unitInvalidMetadataAttacker");
    const auto attacker_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(attacker->getFightController());
    game->getMap()->setStringProperty("combatStatus", "previous encounter status");
    const auto empty_opponents = CFightHandler::fightManyResult(attacker, {});
    expect_true(empty_opponents.outcome == CFightOutcome::Invalid,
                "combat without active opponents should return invalid");
    expect_controller_lifecycle(attacker_controller, 0, 0,
                                "invalid empty-opponent combat should not start or end controllers");
    expect_true(game->getMap()->getStringProperty("combatStatus").empty(),
                "invalid combat without active opponents should clear previous combat status");

    auto controllerless = add_test_creature(game, "unitControllerlessAttacker", 2, 0);
    auto defender = add_test_creature(game, "unitControllerlessDefender", 3, 0);
    controllerless->setFightController(nullptr);
    game->getMap()->setStringProperty("combatStatus", "previous encounter status");
    const auto controllerless_result = CFightHandler::fightManyResult(controllerless, {defender});
    expect_true(controllerless_result.outcome == CFightOutcome::Invalid,
                "attackers without fight controllers should return invalid");
    expect_true(game->getMap()->getStringProperty("combatStatus").empty(),
                "invalid combat without a fight controller should clear previous combat status");
    expect_true(game->getMap()->getObjectByName(defender->getName()) == defender,
                "invalid controller checks should not mutate active opponents");
}

void test_fight_handler_reports_cancelled_quit_event() {
    expect_true(SDL_InitSubSystem(SDL_INIT_EVENTS) == 0, "SDL event subsystem should initialize for quit events");
    SDL_FlushEvent(SDL_QUIT);

    auto game = load_empty_game();
    auto attacker = add_test_creature(game, "unitCancelledAttacker");
    auto defender = add_test_creature(game, "unitCancelledDefender", 1, 0);
    const auto attacker_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(attacker->getFightController());
    const auto defender_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(defender->getFightController());

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
    expect_controller_lifecycle(attacker_controller, 1, 1, "attacker cleanup should run when combat is cancelled");
    expect_controller_lifecycle(defender_controller, 1, 1, "opponent cleanup should run when combat is cancelled");
    expect_true(game->getMap()->getStringProperty("combatStatus").find("cancelled") != std::string::npos,
                "cancelled combat should publish the cancelled status text");
}

void test_fight_handler_ends_original_started_controllers() {
    auto victory_game = load_empty_game();
    auto victor = add_test_creature(victory_game, "unitOriginalEndVictor");
    victor->setFightController(std::make_shared<KillingFightController>());
    auto defeated = add_test_creature(victory_game, "unitOriginalEndDefeated", 1, 0);
    auto defeated_controller = std::make_shared<ReplacingOnStartFightController>();
    defeated->setFightController(defeated_controller);

    const auto victory = CFightHandler::fightManyResult(victor, {defeated});

    expect_true(victory.outcome == CFightOutcome::AttackerVictory,
                "controller replacement victory fixture should resolve");
    expect_controller_lifecycle(defeated_controller, 1, 1,
                                "victory cleanup should end the controller object that was started");
    expect_controller_lifecycle(defeated_controller->replacement, 0, 0,
                                "victory cleanup should not end a replacement controller that was never started");

    expect_true(SDL_InitSubSystem(SDL_INIT_EVENTS) == 0, "SDL event subsystem should initialize for quit events");
    SDL_FlushEvent(SDL_QUIT);
    auto cancel_game = load_empty_game();
    auto cancel_attacker = add_test_creature(cancel_game, "unitOriginalEndCancelAttacker");
    auto cancel_defender = add_test_creature(cancel_game, "unitOriginalEndCancelDefender", 1, 0);
    auto cancel_defender_controller = std::make_shared<ReplacingOnStartFightController>();
    cancel_defender->setFightController(cancel_defender_controller);

    SDL_Event quit_event{};
    quit_event.type = SDL_QUIT;
    expect_true(SDL_PushEvent(&quit_event) == 1, "SDL_QUIT event should be queued for replacement cleanup coverage");

    const auto cancelled = CFightHandler::fightManyResult(cancel_attacker, {cancel_defender});
    SDL_FlushEvent(SDL_QUIT);

    expect_true(cancelled.outcome == CFightOutcome::Cancelled,
                "controller replacement cancellation fixture should report cancellation");
    expect_controller_lifecycle(cancel_defender_controller, 1, 1,
                                "cancelled cleanup should end the controller object that was started");
    expect_controller_lifecycle(cancel_defender_controller->replacement, 0, 0,
                                "cancelled cleanup should not end a replacement controller that was never started");

    auto stalled_game = load_empty_game();
    auto stalled_attacker = add_test_creature(stalled_game, "unitOriginalEndStalledAttacker");
    auto stalled_defender = add_test_creature(stalled_game, "unitOriginalEndStalledDefender", 1, 0);
    auto stalled_defender_controller = std::make_shared<ReplacingOnStartFightController>();
    stalled_defender->setFightController(stalled_defender_controller);

    const auto stalled = CFightHandler::fightManyResult(stalled_attacker, {stalled_defender});

    expect_true(stalled.outcome == CFightOutcome::Stalled,
                "controller replacement stalled fixture should report a stall");
    expect_controller_lifecycle(stalled_defender_controller, 1, 1,
                                "stalled cleanup should end the controller object that was started");
    expect_controller_lifecycle(stalled_defender_controller->replacement, 0, 0,
                                "stalled cleanup should not end a replacement controller that was never started");
}

void test_fight_handler_reports_cancelled_closed_fight_panel() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto game = load_empty_game();
    CGameLoader::loadGui(game);
    auto player = add_test_player(game);

    player->setHp(10);
    auto action = std::make_shared<CInteraction>();
    action->setGame(game);
    action->setName("unitPanelCancelledAction");
    action->setManaCost(0);
    player->addAction(action);

    auto defender = add_test_creature(game, "unitPanelCancelledDefender", 1, 0);
    auto gui = game->getGui();
    auto controller = std::dynamic_pointer_cast<CPlayerFightController>(player->getFightController());
    expect_true(controller != nullptr, "player should use a player fight controller");
    controller->start(player, defender);
    const auto defender_controller =
        std::dynamic_pointer_cast<NoProgressFightController>(defender->getFightController());

    auto panel = vstd::cast<CGameFightPanel>(gui->findChild("CGameFightPanel"));
    expect_true(panel != nullptr, "fight panel should exist after player fight controller starts");
    if (panel) {
        panel->close();
        expect_true(panel->isCancelled(), "closing a fight panel should mark pending action selection cancelled");
    }
    expect_true(!controller->control(player, defender), "closed fight panel should not select an action");
    expect_true(controller->isCancelled(player, defender), "closed fight panel should cancel player control");
    controller->end(player, defender);

    player->setFightController(std::make_shared<CancellingFightController>());
    const auto handler_controller = std::dynamic_pointer_cast<CancellingFightController>(player->getFightController());
    const auto result = CFightHandler::fightManyResult(player, {defender});
    expect_true(result.outcome == CFightOutcome::Cancelled, "closed fight panel should cancel combat immediately");
    expect_true(result.rounds == 1, "panel cancellation during the first action should report the active round");
    expect_true(result.survivor == player && result.opponent == defender,
                "panel cancellation should keep participant metadata");
    expect_controller_lifecycle(handler_controller, 1, 1, "attacker cleanup should run when combat is cancelled");
    expect_controller_lifecycle(defender_controller, 1, 1, "opponent cleanup should run when combat is cancelled");
    expect_true(game->getMap()->getStringProperty("combatStatus").find("cancelled") != std::string::npos,
                "panel cancellation should publish the cancelled status text");
}

void test_player_fight_controller_returns_cancelled_when_attached_fight_panel_cancels() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto game = load_empty_game();
    CGameLoader::loadGui(game);
    auto player = add_test_player(game);

    player->setHp(10);
    auto action = std::make_shared<CInteraction>();
    action->setGame(game);
    action->setName("unitAttachedPanelCancelAction");
    action->setManaCost(0);
    player->addAction(action);

    auto defender = add_test_creature(game, "unitAttachedPanelCancelDefender", 1, 0);
    auto controller = std::dynamic_pointer_cast<CPlayerFightController>(player->getFightController());
    expect_true(controller != nullptr, "player should use a player fight controller for attached panel cancellation");
    if (!controller) {
        return;
    }
    controller->start(player, defender);

    auto gui = game->getGui();
    auto panel = vstd::cast<CGameFightPanel>(gui->findChild("CGameFightPanel"));
    expect_true(panel != nullptr, "fight panel should exist before attached panel cancellation");
    if (!panel) {
        return;
    }

    panel->cancel();

    expect_true(!controller->control(player, defender),
                "attached fight panel cancellation should not report selected action progress");
    expect_true(controller->isCancelled(player, defender), "attached fight panel cancellation should cancel control");
    controller->end(player, defender);
}

void test_fight_handler_returns_cancelled_when_player_control_cancels() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto game = load_empty_game();
    CGameLoader::loadGui(game);
    auto player = add_test_player(game);
    player->setHp(10);

    auto action = std::make_shared<CInteraction>();
    action->setGame(game);
    action->setName("unitLoopPanelCancelAction");
    action->setManaCost(0);
    player->addAction(action);

    auto defender = add_test_creature(game, "unitLoopPanelCancelDefender", 1, 0);
    auto defender_controller = std::dynamic_pointer_cast<NoProgressFightController>(defender->getFightController());
    auto gui = game->getGui();
    expect_true(gui != nullptr, "handler-level panel cancellation regression requires a loaded GUI");
    expect_true(std::dynamic_pointer_cast<CPlayerFightController>(player->getFightController()) != nullptr,
                "handler-level panel cancellation should use the real player fight controller");

    auto cancellation_callback_ran = std::make_shared<bool>(false);
    auto panel_was_cancelled = std::make_shared<bool>(false);
    vstd::event_loop<>::instance()->invoke([game, cancellation_callback_ran, panel_was_cancelled]() {
        *cancellation_callback_ran = true;
        auto panel = game && game->getGui() ? vstd::cast<CGameFightPanel>(game->getGui()->findChild("CGameFightPanel"))
                                            : nullptr;
        if (panel) {
            panel->cancel();
            *panel_was_cancelled = panel->isCancelled();
        }
    });

    const auto result = CFightHandler::fightManyResult(player, {defender});

    expect_true(*cancellation_callback_ran, "fight panel cancellation should run while player control is waiting");
    expect_true(*panel_was_cancelled, "queued cancellation should cancel the active fight panel");
    expect_true(result.outcome == CFightOutcome::Cancelled,
                "player fight controller cancellation should return cancelled instead of falling through to stalled");
    expect_true(result.rounds == 1, "player fight controller cancellation should report the active combat round");
    expect_true(result.survivor == player && result.opponent == defender,
                "player fight controller cancellation should keep participant metadata");
    expect_true(gui && gui->findChild("CGameFightPanel") == nullptr,
                "player fight controller cleanup should close the cancelled fight panel");
    expect_controller_lifecycle(defender_controller, 1, 1,
                                "opponent cleanup should still run after player control cancellation");
    expect_true(game->getMap()->getStringProperty("combatStatus").find("cancelled") != std::string::npos,
                "player control cancellation should publish the cancelled status text");
}

void test_fight_panel_resets_status_between_sequential_encounters() {
    auto game = load_empty_game();
    auto encounterMap = game->getMap();

    auto first_victor = add_test_creature(game, "unitFirstStatusVictor");
    first_victor->setLabel("First status victor");
    first_victor->setFightController(std::make_shared<KillingFightController>());
    auto first_defeated = add_test_creature(game, "unitFirstStatusDefeated", 1, 0);

    const auto first = CFightHandler::fightManyResult(first_victor, {first_defeated});
    const auto first_status = encounterMap->getStringProperty("combatStatus");
    expect_true(first.outcome == CFightOutcome::AttackerVictory, "first status-isolation fight should resolve");
    expect_true(first_status.find("First status victor survives the encounter") != std::string::npos,
                "first fight should publish an intentional final status");

    auto second_victor = add_test_creature(game, "unitSecondStatusVictor", 2, 0);
    second_victor->setLabel("Second status victor");
    second_victor->setFightController(std::make_shared<KillingFightController>());
    auto second_defeated = add_test_creature(game, "unitSecondStatusDefeated", 3, 0);
    auto reopened_panel = game->createObject<CGameFightPanel>("CGameFightPanel");
    expect_true(reopened_panel != nullptr, "headless fight panel should be constructible for status isolation");
    if (!reopened_panel) {
        return;
    }

    reopened_panel->setEnemies({second_defeated});
    expect_true(encounterMap->getStringProperty("combatStatus").empty(),
                "opening a fight panel for a later encounter should not display previous final status");

    encounterMap->setStringProperty("combatStatus", "Previous victor survives the encounter.");
    reopened_panel->setEnemy(second_defeated);
    expect_true(encounterMap->getStringProperty("combatStatus").empty(),
                "setting a fight panel enemy directly should also clear previous combat status");

    encounterMap->setStringProperty("combatStatus", "Combat round 99 begins.");
    reopened_panel->close();
    expect_true(encounterMap->getStringProperty("combatStatus").empty(),
                "closing a fight panel should clear previous round status");

    const auto second = CFightHandler::fightManyResult(second_victor, {second_defeated});
    const auto second_status = encounterMap->getStringProperty("combatStatus");
    expect_true(second.outcome == CFightOutcome::AttackerVictory, "second status-isolation fight should resolve");
    expect_true(second_status.find("Second status victor survives the encounter") != std::string::npos,
                "second fight should publish its own final status");
    expect_true(second_status.find("First status victor") == std::string::npos,
                "second fight status should not include the previous encounter");
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

    auto game = load_empty_game();
    auto player = add_test_player(game);
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

void test_playtest_trace_environment_targets_and_fallback_ids() {
#ifdef _WIN32
    return;
#else
    {
        ScopedEnvironmentVariable traceEnabled("GAME_PLAYTEST_TRACE", "OFF");
        ScopedEnvironmentVariable traceFile("GAME_PLAYTEST_TRACE_FILE", std::nullopt);
        CPlaytestTrace::configureFromEnvironment();
        expect_true(!CPlaytestTrace::enabled(), "disabled trace environment values should disable tracing");
        CPlaytestTrace::record("disabled_trace_should_not_record");
        expect_true(CPlaytestTrace::records().empty(), "disabled tracing should ignore records");
    }

    {
        ScopedEnvironmentVariable traceEnabled("GAME_PLAYTEST_TRACE", "stdout");
        ScopedEnvironmentVariable traceFile("GAME_PLAYTEST_TRACE_FILE", std::nullopt);
        CPlaytestTrace::configureFromEnvironment();
        CPlaytestTrace::record("stdout_target");
        expect_true(!CPlaytestTrace::drain().empty(), "stdout trace environment target should enable tracing");
    }

    CPlaytestTrace::configure(true, "stderr");
    CPlaytestTrace::record("stderr_target");
    expect_true(!CPlaytestTrace::drain().empty(), "stderr trace target should still keep buffered records");

    const auto tracePath =
        std::filesystem::temp_directory_path() / ("playtest-trace-unit-" + std::to_string(SDL_GetTicks64()) + ".jsonl");
    CPlaytestTrace::configure(true, tracePath.generic_string());
    CPlaytestTrace::record("file_target");
    std::ifstream stream(tracePath);
    std::string line;
    std::getline(stream, line);
    expect_true(line.find("file_target") != std::string::npos, "file trace target should append JSON lines");
    std::filesystem::remove(tracePath);

    auto namedObject = std::make_shared<CGameObject>();
    const auto longName = std::string(200, 'n');
    namedObject->setName(longName);
    const auto namedRef = CPlaytestTrace::objectRef(namedObject);
    expect_true(namedRef.value("id", std::string()).size() == 160,
                "trace object refs should truncate long fallback names");
    expect_true(namedRef.value("name", std::string()).size() == 160,
                "trace object refs should truncate long object names");

    auto typedObject = std::make_shared<CGameObject>();
    typedObject->setName("");
    typedObject->setType("UnitTraceType");
    const auto typedRef = CPlaytestTrace::objectRef(typedObject);
    expect_true(typedRef.value("id", std::string()) == "UnitTraceType",
                "trace object refs should fall back to object type when id and name are empty");
    expect_true(typedRef.value("type", std::string()) == "UnitTraceType",
                "trace object refs should include the runtime object type");

    CPlaytestTrace::configure(false);
#endif
}

void test_fight_handler_records_outcome_trace_metadata() {
    CPlaytestTrace::configure(true);
    try {
        auto game = load_empty_game();
        auto victor = add_test_creature(game, "unitTraceOutcomeVictor");
        victor->setFightController(std::make_shared<KillingFightController>());
        auto defeated = add_test_creature(game, "unitTraceOutcomeDefeated", 1, 0);
        add_unit_loot(game, defeated, "unitTraceOutcomeLoot");

        const auto result = CFightHandler::fightManyResult(victor, {defeated});
        const auto records = CPlaytestTrace::drain();

        bool found_finished = false;
        for (const auto &record : records) {
            const auto parsed = json::parse(record);
            if (parsed.value("event", std::string()) != "combat_finished") {
                continue;
            }
            found_finished = true;
            expect_true(parsed.value("outcome", 0) == static_cast<int>(CFightOutcome::AttackerVictory),
                        "combat_finished traces should include the explicit fight outcome");
            expect_true(parsed.value("rounds", 0) == result.rounds,
                        "combat_finished traces should include the resolved round count");
            expect_true(parsed.contains("survivor") &&
                            parsed["survivor"].value("name", std::string()) == victor->getName(),
                        "combat_finished traces should include the survivor reference");
        }
        expect_true(found_finished, "combat should emit a combat_finished trace while tracing is enabled");
    } catch (...) {
        CPlaytestTrace::configure(false);
        throw;
    }
    CPlaytestTrace::configure(false);
}

void test_player_respawn_normalizes_wrapped_entry_coords() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto player = add_test_player(game);

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
    test_event_handler_trigger_registration_uses_named_comparison_helpers();
    test_fight_handler_rejects_stale_and_cross_map_participants();
    test_fight_handler_attributes_lethal_effects_to_valid_casters();
    test_fight_handler_reports_explicit_outcomes_and_final_status();
    test_fight_handler_reports_invalid_result_metadata();
    test_fight_handler_reports_cancelled_quit_event();
    test_fight_handler_ends_original_started_controllers();
    test_fight_handler_reports_cancelled_closed_fight_panel();
    test_player_fight_controller_returns_cancelled_when_attached_fight_panel_cancels();
    test_fight_handler_returns_cancelled_when_player_control_cancels();
    test_fight_panel_resets_status_between_sequential_encounters();
    test_fight_handler_counts_effect_duration_as_progress();
    test_playtest_trace_records_native_limits_and_quest_completion();
    test_playtest_trace_environment_targets_and_fallback_ids();
    test_fight_handler_records_outcome_trace_metadata();
    test_player_respawn_normalizes_wrapped_entry_coords();

    return finish_tests();
}
