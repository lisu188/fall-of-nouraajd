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
#include "handler/CEventHandler.h"
#include "handler/CFightHandler.h"
#include "handler/CObjectHandler.h"
#include "handler/CQuestHandler.h"
#include "handler/CRngHandler.h"
#include "handler/CScriptHandler.h"
#include "handler/CTooltipHandler.h"
#include "core/CController.h"
#include "core/CAsync.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CJsonUtil.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CSceneManager.h"
#include "seven_suns_warning_fixture.h"
#include "seven_suns_merchant_fixture.h"
#include "handler/CSevenSunsMerchantStock.h"
#include "handler/CSevenSunsMerchantStockData.h"
#include "core/CPlaytestTrace.h"
#include "core/CProvider.h"
#include "core/CPythonOverrides.h"
#include "core/CSaveFormat.h"
#include "core/CSlotConfig.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "gui/CGui.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameCampaignBrowserPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/panel/CGamePanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureRace.h"
#include "object/CInteraction.h"
#include "object/CEffect.h"
#include "object/CEvent.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CWaitState.h"
#include "object/CQuest.h"
#include "object/CTrigger.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "native_test_profile.h"
#if defined(_WIN32)
#include "native_crash_diagnostics.h"
#endif

#include <SDL.h>
#include <pybind11/embed.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <future>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <type_traits>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

void testScriptFlowBootstrapDoesNotRequireGameplayModule() {
    const auto modules = pybind11::module_::import("sys").attr("modules").cast<pybind11::dict>();
    expect_true(!modules.contains("_game"), "pure UI startup must not load or register gameplay bindings");
    auto game = std::make_shared<CGame>();
    auto callback = pybind11::cpp_function([] { return pybind11::none(); });
    auto flow = game->getScriptHandler()->createCallbackFlow(callback, game);
    expect_true(flow && !flow->next(nullptr), "a native callback flow must start in the standalone handler test");
    flow.reset();
    game->getContext()->shutdown();
}

class DiagnosedNativeTestProfile : public CNativeTestProfile {
  public:
    using CNativeTestProfile::CNativeTestProfile;

    template <typename Action> auto run(const char *name, Action &&action) -> std::invoke_result_t<Action> {
        std::cout << "[handler-test] ENTER " << name << std::endl;
        if constexpr (std::is_void_v<std::invoke_result_t<Action>>) {
            CNativeTestProfile::run(name, std::forward<Action>(action));
            std::cout << "[handler-test] EXIT " << name << std::endl;
        } else {
            decltype(auto) result = CNativeTestProfile::run(name, std::forward<Action>(action));
            std::cout << "[handler-test] EXIT " << name << std::endl;
            return result;
        }
    }
};

DiagnosedNativeTestProfile &nativeTestProfile() {
    static DiagnosedNativeTestProfile profile("handler");
    return profile;
}

void testGameplayMetadataIsAvailableBeforePluginLoading() {
    const auto expectMetadata = []<typename T>(const char *message) {
        using Pointer = std::shared_ptr<T>;
        using Set = std::set<Pointer>;
        using Map = std::map<std::string, Pointer>;
        expect_true(CTypes::is_pointer_type<Pointer>() && CTypes::is_array_type<Set>() && CTypes::is_map_type<Map>() &&
                        CTypes::findCodec(typeid(Pointer)) && CTypes::findCodec(typeid(Set)) &&
                        CTypes::findCodec(typeid(Map)),
                    message);
        expect_true(!CTypes::builders()->contains(T::static_meta()->name()),
                    "gameplay builders must remain unavailable until the native plugin registers them");
    };
    expectMetadata.operator()<CFightController>("fight controller metadata must exist before plugin loading");
    expectMetadata.operator()<CMonsterFightController>(
        "derived fight controller metadata must exist before plugin loading");
    expectMetadata.operator()<CCreatureRace>("race metadata must exist before plugin loading");
    expectMetadata.operator()<CCreatureClass>("class metadata must exist before plugin loading");
    expectMetadata.operator()<CInteraction>("interaction metadata must exist before plugin loading");
    expectMetadata.operator()<CWrapper<CInteraction>>("wrapped interaction metadata must exist before plugin loading");

    auto controller = std::make_shared<CMonsterFightController>();
    auto interaction = std::make_shared<CWrapper<CInteraction>>();
    try {
        expect_true(vstd::any_cast<std::shared_ptr<CFightController>>(std::any(controller)) == controller &&
                        vstd::any_cast<std::shared_ptr<CGameObject>>(std::any(controller)) == controller &&
                        vstd::any_cast<std::shared_ptr<CInteraction>>(std::any(interaction)) == interaction &&
                        vstd::any_cast<std::shared_ptr<CGameObject>>(std::any(interaction)) == interaction,
                    "gameplay metadata must register the complete controller and wrapper base chains");
    } catch (const std::bad_any_cast &) {
        expect_true(false, "gameplay metadata must register the complete controller and wrapper base chains");
    }
}

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

class WindowlessFightTestGui : public CGui {
  public:
    WindowlessFightTestGui() : CGui(WithoutWindow{}) {}
};

class TurnHookRegistrationProbe : public CMapObject {
  public:
    std::function<void()> hook;

    void onTurn(std::shared_ptr<CGameEvent>) override { hook(); }
};

class DestroyHookProbe : public CMapObject {
  public:
    int destroyed = 0;
    std::function<void()> hook;

    void onDestroy(std::shared_ptr<CGameEvent>) override {
        ++destroyed;
        if (hook) {
            hook();
        }
    }
};

class StepHookShutdownProbe : public CTile {
  public:
    int steps = 0;
    std::shared_ptr<CGameContext> context;

    void onStep(std::shared_ptr<CCreature>) override {
        ++steps;
        context->shutdown();
    }
};

template <typename Predicate> bool pumpHandlerUntil(Predicate ready) {
    auto loop = vstd::event_loop<>::instance();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (!ready() && std::chrono::steady_clock::now() < deadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    return static_cast<bool>(ready());
}

class StepHookCallbackProbe : public CTile {
  public:
    std::function<void()> hook;
    int steps = 0;

    void onStep(std::shared_ptr<CCreature>) override {
        ++steps;
        if (hook) {
            hook();
        }
    }
};

struct AsyncTriggerProbe {
    std::vector<std::string> entered;
    std::set<std::string> released;
};

vstd::task<void> awaitTriggerProbe(std::shared_ptr<AsyncTriggerProbe> probe, std::string name,
                                   std::function<void()> onStart = {}) {
    probe->entered.push_back(name);
    if (onStart) {
        onStart();
    }
    auto loop = vstd::event_loop<>::instance();
    co_await vstd::until(loop, [probe, name] { return probe->released.contains(name); });
}

class SuspendedEntryTraceProbe : public CEvent {
  public:
    std::shared_ptr<AsyncTriggerProbe> probe;

    vstd::task<void> onEnterAsync(std::shared_ptr<CGameEvent>) override { return awaitTriggerProbe(probe, "hook"); }
};

class SuspendedTraceFightController : public NoProgressFightController {
  public:
    std::shared_ptr<AsyncTriggerProbe> probe;

    vstd::task<bool> controlAsync(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        return [](std::shared_ptr<AsyncTriggerProbe> state) -> vstd::task<bool> {
            co_await awaitTriggerProbe(std::move(state), "control");
            co_return true;
        }(probe);
    }
};

struct FightThreadProbe {
    std::thread::id startedOn;
    std::thread::id panelCreatedOn;
    std::atomic<int> starts = 0;
    std::atomic<int> panels = 0;
};

class ThreadCheckedPlayerFightController : public CPlayerFightController {
  public:
    explicit ThreadCheckedPlayerFightController(std::shared_ptr<FightThreadProbe> probe) : probe(std::move(probe)) {}

    void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        probe->startedOn = std::this_thread::get_id();
        CPlayerFightController::start(std::move(me), std::move(opponent));
        probe->starts.fetch_add(1, std::memory_order_release);
    }

  private:
    std::shared_ptr<FightThreadProbe> probe;
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

class QuestLifecycleProbe : public CQuest {
  public:
    int check_count = 0;
    int complete_count = 0;
    std::vector<bool> captures;
    std::function<void()> check_callback;
    std::function<void()> complete_callback;
    std::function<void()> capture_callback;

    bool isCompleted() override {
        check_count++;
        if (check_callback) {
            check_callback();
        }
        return true;
    }

    void onComplete() override {
        complete_count++;
        if (complete_callback) {
            complete_callback();
        }
    }

    void captureJournal(bool completed) override {
        captures.push_back(completed);
        if (capture_callback) {
            capture_callback();
        }
    }
};

std::shared_ptr<CGame> load_empty_game() {
    auto game = nativeTestProfile().run("CGameLoader::loadGame", [] { return CGameLoader::loadGame(); });
    nativeTestProfile().run("CGameLoader::startGame(empty)", [&] { CGameLoader::startGame(game, "empty"); });
    return game;
}

void attachFightPanelGuiFixture(const std::shared_ptr<CGame> &game) {
    auto gui = std::make_shared<CGui>();
    gui->setGame(game);
    game->setGui(gui);

    // Authored GUI visibility scripts require Python bindings for native GUI types.
    // These cancellation tests exercise the real panel without unrelated scripted child views.
    auto fight_panel_config = std::make_shared<json>();
    (*fight_panel_config)["class"] = "CGameFightPanel";
    game->getObjectHandler()->registerConfig("fightPanel", fight_panel_config);
}

std::shared_ptr<CGame> makeWindowlessFightGame() {
    vstd::event_loop<>::instance()->resetQuit();
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    auto gui = std::make_shared<WindowlessFightTestGui>();
    gui->setGame(game);
    game->setGui(gui);
    auto objects = game->getObjectHandler();
    objects->registerType("CPlayerController", [] { return std::make_shared<CPlayerController>(); });
    objects->registerType("CPlayerFightController", [] { return std::make_shared<CPlayerFightController>(); });
    objects->registerType("CGameLootPanel", [] { return std::make_shared<CGameLootPanel>(); });
    objects->registerConfig("lootPanel", std::make_shared<json>(json{{"class", "CGameLootPanel"}}));
    objects->registerConfig("fightPanel", std::make_shared<json>(json{{"class", "CGameFightPanel"}}));
    return game;
}

void testSyncGuiWaitReleasesLastGameOwner() {
    auto loop = vstd::event_loop<>::instance();
    for (const bool dropFinalOwner : {false, true}) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto gui = game->getGui();
        auto handler = game->getGuiHandler();
        game->getObjectHandler()->registerType("CGameTextPanel", [] { return std::make_shared<CGameTextPanel>(); });
        game->getObjectHandler()->registerConfig("textPanel",
                                                 std::make_shared<json>(json{{"class", "CGameTextPanel"}}));
        std::weak_ptr<CGame> lifetime = game;
        auto retainedOwner = dropFinalOwner ? std::shared_ptr<CGame>{} : game;
        bool callbackRan = false;
        bool panelOpened = false;
        bool ownerExpiredInCallback = false;
        bool contextActiveInCallback = false;
        expect_true(loop->invoke([&] {
            callbackRan = true;
            auto panel = vstd::cast<CGameTextPanel>(gui->findChild("CGameTextPanel"));
            panelOpened = panel != nullptr;
            game.reset();
            ownerExpiredInCallback = lifetime.expired();
            contextActiveInCallback = context->isActive();
            if (dropFinalOwner && !ownerExpiredInCallback) {
                // Bound the old ownership failure instead of leaving its modal waiting forever.
                context->shutdown();
            } else if (!dropFinalOwner && panel) {
                panel->close();
            }
        }),
                    "a synchronous GUI wait must pump the queued owner-release callback");
        handler->showMessage("Release the final owner while this native modal waits");
        expect_true(callbackRan && panelOpened && ownerExpiredInCallback == dropFinalOwner &&
                        contextActiveInCallback != dropFinalOwner && gui->getChildren().empty(),
                    "synchronous GUI waits must permit final game destruction without cancelling a retained session");
        retainedOwner.reset();
        expect_true(lifetime.expired() && !context->isActive(),
                    "releasing the final external game owner must shut down and release its native session");
        context->shutdown();
    }
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
    static_assert(!std::is_copy_constructible_v<CScriptHandler>);
    static_assert(!std::is_copy_assignable_v<CScriptHandler>);
    static_assert(!std::is_move_constructible_v<CScriptHandler>);
    static_assert(!std::is_move_assignable_v<CScriptHandler>);
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
    handler.execute_command({"capture", "say \"hello\"", "\"quoted\""});
    expect_true(handler.get_object<std::string>("captured") == "say \"hello\":\"quoted\"",
                "execute_command should escape embedded quotes once and preserve the Python arguments");

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

    CScriptHandler surviving_handler;
    handler.releaseState();
    handler.releaseState();
    bool released_state_rejected = false;
    try {
        handler.execute_script("released_handler_used = True");
    } catch (const std::runtime_error &) {
        released_state_rejected = true;
    }
    expect_true(released_state_rejected, "a released handler must reject use after repeated release");
    surviving_handler.execute_script("surviving_handler_value = 29");
    expect_true(surviving_handler.get_object<int>("surviving_handler_value") == 29,
                "releasing one handler must not release another handler's runtime state");
}

void test_handler_constructors_are_covered_by_native_tests() {
    CQuestHandler quest_handler;
    CRngHandler rng_handler;
    auto gui_handler = std::make_shared<CGuiHandler>();

    expect_true(CGuiHandler::static_meta()->name() == "CGuiHandler",
                "GUI handler metadata should expose its type name");
    expect_true(gui_handler->meta()->inherits("CGameObject"), "GUI handler metadata should preserve its object base");
    gui_handler->showMessage("native handler constructor coverage");
    gui_handler->showInfo("native handler info coverage");
    // Headless campaign screens log the title/body/action content and return
    // immediately instead of blocking on input.
    gui_handler->showCampaignScreen("Chapter I - Hearthfall", "Ten years of exile end here.", "BEGIN");
    // The headless campaign browser resolves to the empty stable id immediately.
    expect_true(gui_handler->showCampaignSelection(nullptr, nullptr, nullptr).empty(),
                "headless campaign selection should resolve to the empty stable id");
    expect_true(!gui_handler->showQuestion("native handler question coverage"),
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

void testObjectEntryTracePreservesActualCauseAndContactBeforeNpcDeparture() {
    auto game = load_empty_game();
    auto map = game->getMap();
    map->setMapName("unitObjectEntry");
    auto player = add_test_player(game);
    player->relocateWithoutMoveHooks(Coords(0, 0, 0));
    auto witness = add_test_creature(game, "unitMovingWitness", 1, 0);
    witness->setNpc(true);
    witness->setCanStep(true);
    int callbacks = 0;
    map->getEventHandler()->registerTrigger(
        std::make_shared<CCustomTrigger>(witness->getName(), CGameEvent::CType::onEnter, [&](auto object, auto event) {
            auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
            if (!caused || caused->getCause() != player)
                return;
            expect_true(object == witness,
                        "the normal native onEnter callback should retain its exact target and player cause");
            callbacks++;
        }));

    CPlaytestTrace::configure(true, "", 100, true);
    player->moveTo(1, 0, 0);
    witness->moveTo(2, 0, 0);
    int entries = 0;
    for (const auto &line : CPlaytestTrace::drain()) {
        const auto record = json::parse(line);
        if (record.value("event", std::string()) != "object_entered" ||
            record.at("target").value("name", std::string()) != witness->getName() ||
            record.at("cause").value("isPlayer", false) != true)
            continue;
        entries++;
        expect_true(record.at("target").dump() == CPlaytestTrace::objectRef(witness).dump() &&
                        record.at("cause").dump() == CPlaytestTrace::objectRef(player).dump(),
                    "entry evidence should preserve the exact native target and player identities");
        expect_true(record.at("cause").at("isPlayer").get<bool>() == true &&
                        record.at("targetCoords").dump() == CPlaytestTrace::coords(Coords(1, 0, 0)).dump() &&
                        record.at("causeCoords").dump() == record.at("targetCoords").dump(),
                    "entry evidence should retain actual contact before the witness's later movement");
        expect_true(record.at("map").get<std::string>() == map->getMapName() &&
                        record.at("turn").get<int>() == map->getTurn(),
                    "entry evidence should retain the active native map and turn");
    }
    CPlaytestTrace::configure(false);
    expect_true(callbacks == 1 && entries == 1 && player->getCoords() == Coords(1, 0, 0) &&
                    witness->getCoords() == Coords(2, 0, 0),
                "tracing should observe the completed callback without keeping the moving witness in place");
}

void testObjectEntryTraceRequiresOptInAndCanonicalColocatedCause() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto player = add_test_player(game);
    player->relocateWithoutMoveHooks(Coords(0, 0, 0));
    auto witness = add_test_creature(game, "unitTraceWitness", 1, 0);
    witness->setNpc(true);
    witness->setCanStep(true);
    int callbacks = 0;
    map->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
        witness->getName(), CGameEvent::CType::onEnter, [&](auto, auto) { callbacks++; }));
    CPlaytestTrace::configure(false);
    player->moveTo(1, 0, 0);
    expect_true(callbacks == 1 && CPlaytestTrace::records().empty(),
                "disabled entry tracing should preserve the native callback without recording anything");

    CPlaytestTrace::configure(true, "", 2, true);
    auto handler = map->getEventHandler();
    handler->gameEvent(nullptr, std::make_shared<CGameEvent>(CGameEvent::CType::onEnter));
    handler->gameEvent(witness, nullptr);
    handler->gameEvent(witness, std::make_shared<CGameEvent>(CGameEvent::CType::onEnter));
    handler->gameEvent(witness, std::make_shared<CGameEventCaused>(CGameEvent::CType::onEnter, nullptr));
    auto remote = add_test_creature(game, "unitRemoteCause", 3, 0);
    handler->gameEvent(witness, std::make_shared<CGameEventCaused>(CGameEvent::CType::onEnter, remote));
    auto detached = std::make_shared<CCreature>();
    detached->setGame(game);
    detached->setName(player->getName());
    detached->relocateWithoutMoveHooks(witness->getCoords());
    handler->gameEvent(witness, std::make_shared<CGameEventCaused>(CGameEvent::CType::onEnter, detached));
    for (const auto &line : CPlaytestTrace::drain())
        expect_true(json::parse(line).value("event", std::string()) != "object_entered",
                    "absent, remote or noncanonical causes must not become native contact evidence");

    handler->gameEvent(witness, std::make_shared<CGameEvent>(CGameEvent::CType::onTurn));
    expect_true(CPlaytestTrace::records().empty(), "unrelated native events must not become entry evidence");
    witness->moveTo(2, 0, 0);
    witness->moveTo(player->getCoords());
    int npc_entries = 0;
    const auto npc_records = CPlaytestTrace::drain();
    expect_true(npc_records.size() <= 2, "entry records must obey the existing bounded native trace limit");
    for (const auto &line : npc_records) {
        const auto record = json::parse(line);
        if (record.value("event", std::string()) == "object_entered") {
            npc_entries++;
            expect_true(record.at("cause").at("isPlayer").get<bool>() == false,
                        "an NPC moving onto the player must retain its NPC cause");
        }
    }
    CPlaytestTrace::configure(false);
    expect_true(npc_entries > 0, "valid NPC-caused entries should remain distinguishable from player-caused entries");
}

void testAsyncObjectEntryTraceWaitsForHooksAndPreservesContactOnResume() {
    for (const bool cancel : {false, true}) {
        auto game = load_empty_game();
        auto map = game->getMap();
        map->setMapName("unitSuspendedEntryTrace");
        map->setTurn(17);
        auto player = add_test_player(game);
        player->relocateWithoutMoveHooks(ZERO);
        auto probe = std::make_shared<AsyncTriggerProbe>();
        auto target = std::make_shared<SuspendedEntryTraceProbe>();
        target->probe = probe;
        target->setGame(game);
        target->setName("unitSuspendedEntryTarget");
        target->setCanStep(true);
        map->addObject(target);
        auto trigger = std::make_shared<CCustomTrigger>(
            target->getName(), "onEnter", [probe](auto, auto) { return awaitTriggerProbe(probe, "trigger"); });
        trigger->setName("unitSuspendedEntryTrigger");
        map->getEventHandler()->registerTrigger(trigger);
        const auto entries = [] {
            std::vector<json> found;
            for (const auto &line : CPlaytestTrace::records()) {
                auto record = json::parse(line);
                if (record.value("event", std::string()) == "object_entered") {
                    found.push_back(std::move(record));
                }
            }
            return found;
        };
        CPlaytestTrace::configure(true, "", 100, true);
        auto entry = game->getContext()->spawnTask(map->getEventHandler()->gameEventAsync(
            target, std::make_shared<CGameEventCaused>(CGameEvent::CType::onEnter, player)));
        expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || entry.finished(); }) &&
                        probe->entered == std::vector<std::string>{"hook"} && entries().empty(),
                    "an entry trace must wait for its asynchronous object hook without publishing completion");
        target->relocateWithoutMoveHooks(Coords(2, 0, 0));
        player->relocateWithoutMoveHooks(Coords(3, 0, 0));
        map->setTurn(99);
        if (cancel) {
            entry.requestStop();
        } else {
            probe->released.insert("hook");
            expect_true(pumpHandlerUntil([&] { return probe->entered.size() == 2 || entry.finished(); }) &&
                            probe->entered == std::vector<std::string>({"hook", "trigger"}) && entries().empty(),
                        "an entry trace must also wait for the ordered trigger snapshot after its object hook");
            probe->released.insert("trigger");
        }
        expect_true(pumpHandlerUntil([&] { return entry.finished(); }), "entry trace execution must finish boundedly");
        bool cancelled = false;
        if (entry.finished()) {
            try {
                entry.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        const auto records = entries();
        expect_true(cancelled == cancel && records.size() == (cancel ? 0U : 1U),
                    "a completed asynchronous entry records once and a cancelled entry records no completion");
        if (!records.empty()) {
            expect_true(records.front().at("targetCoords").dump() == CPlaytestTrace::coords(ZERO).dump() &&
                            records.front().at("causeCoords").dump() == CPlaytestTrace::coords(ZERO).dump() &&
                            records.front().at("turn").get<int>() == 17 &&
                            records.front().at("map").get<std::string>() == "unitSuspendedEntryTrace",
                        "resuming entry callbacks must retain owned contact/map/turn snapshots from before the yield");
        }
        CPlaytestTrace::configure(false);
        game->getContext()->shutdown();
    }
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

    CFightHandler::recordCombatStatus(victory_game->getMap(), "Previous encounter event");
    const auto victory = CFightHandler::fightManyResult(victor, {defeated});
    const auto combat_history = CFightHandler::getCombatHistory(victory_game->getMap());
    expect_true(
        combat_history.size() >= 3 && combat_history.front().starts_with("Combat round 1 begins.") &&
            combat_history.back() == victory_game->getMap()->getStringProperty("combatStatus") &&
            std::find(combat_history.begin(), combat_history.end(), "Previous encounter event") == combat_history.end(),
        "real encounters must reset old history and record authoritative round/action/outcome messages in order");
    expect_true(victory_game->getMap()->getNumericProperty("combatRound") == victory.rounds,
                "the combat display round must come from the resolved encounter loop");

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

void testAsyncEventsAwaitOrderedTriggerSnapshotsAfterObjectHooks() {
    auto loop = vstd::event_loop<>::instance();
    auto game = makeWindowlessFightGame();
    auto handler = game->getMap()->getEventHandler();
    auto object = std::make_shared<TurnHookRegistrationProbe>();
    object->setGame(game);
    object->setName("unitAsyncHook");
    auto probe = std::make_shared<AsyncTriggerProbe>();
    auto lateCalls = std::make_shared<int>(0);
    auto late =
        std::make_shared<CCustomTrigger>(object->getName(), "onTurn", [lateCalls](auto, auto) { ++*lateCalls; });
    late->setName("unitLateTrigger");
    std::weak_ptr<CEventHandler> weakHandler = handler;
    auto makeTrigger = [&](std::string name) {
        auto trigger =
            std::make_shared<CCustomTrigger>(object->getName(), "onTurn", [probe, weakHandler, late, name](auto, auto) {
                return awaitTriggerProbe(probe, name, [weakHandler, late] {
                    if (auto handler = weakHandler.lock()) {
                        handler->registerTrigger(late);
                    }
                });
            });
        trigger->setName(name);
        return trigger;
    };
    auto first = makeTrigger("unitFirstTrigger");
    auto addedByHook = makeTrigger("unitHookTrigger");
    handler->registerTrigger(first);
    object->hook = [handler, addedByHook] { handler->registerTrigger(addedByHook); };
    bool queued = false;
    loop->invoke([&queued] { queued = true; });
    auto waiting = game->getContext()->spawnTask(
        handler->gameEventAsync(object, std::make_shared<CGameEvent>(CGameEvent::CType::onTurn)));
    expect_true(!waiting.finished() && !queued, "spawning an event must return without pumping queued callbacks");
    expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || waiting.finished(); }) &&
                    probe->entered.size() == 1 && !waiting.finished(),
                "the outer loop must reach the first trigger before starting later captured triggers");
    if (!probe->entered.empty()) {
        probe->released.insert(probe->entered.front());
    }
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (probe->entered.size() < 2 && std::chrono::steady_clock::now() < deadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(probe->entered.size() == 2 && !waiting.finished() && *lateCalls == 0,
                "the hook-added trigger must join this event, while trigger-added observers wait for another event");
    probe->released.insert("unitFirstTrigger");
    probe->released.insert("unitHookTrigger");
    while (!waiting.finished() && std::chrono::steady_clock::now() < deadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(waiting.finished() && probe->entered.size() == 2 && *lateCalls == 0 && queued,
                "the event must finish each captured trigger once in sequence");
    if (waiting.finished()) {
        waiting.get();
    } else {
        waiting.requestStop();
        while (!waiting.finished()) {
            loop->runReady();
        }
    }
    game->getContext()->shutdown();

    auto turnGame = makeWindowlessFightGame();
    auto turnMap = turnGame->getMap();
    auto turnObject = std::make_shared<CMapObject>();
    turnObject->setGame(turnGame);
    turnObject->setName("unitSuspendedTurnObject");
    turnMap->addObject(turnObject);
    auto turnProbe = std::make_shared<AsyncTriggerProbe>();
    auto turnTrigger = std::make_shared<CCustomTrigger>(
        turnObject->getName(), "onTurn", [turnProbe](auto, auto) { return awaitTriggerProbe(turnProbe, "turn"); });
    turnTrigger->setName("unitSuspendedTurnTrigger");
    turnMap->getEventHandler()->registerTrigger(turnTrigger);
    const auto originalTurn = turnMap->getTurn();
    auto pendingTurn = turnGame->getContext()->spawnTask(turnMap->moveAsync());
    expect_true(pumpHandlerUntil([&] { return !turnProbe->entered.empty() || pendingTurn.finished(); }) &&
                    !pendingTurn.finished() && turnProbe->entered.size() == 1,
                "map turns must await their asynchronous event triggers");
    auto replacement = std::make_shared<CMap>();
    replacement->setGame(turnGame);
    turnGame->setMap(replacement);
    turnProbe->released.insert("turn");
    const auto turnDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (!pendingTurn.finished() && std::chrono::steady_clock::now() < turnDeadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(pendingTurn.finished() && turnMap->getTurn() == originalTurn,
                "a turn invalidated during a hook must not run old-map controllers or commit another turn");
    if (pendingTurn.finished()) {
        pendingTurn.get();
    }
    turnGame->getContext()->shutdown();
}

void testAsyncLeaveHooksRejectStaleMovesAndCleanCancellation() {
    enum class Finish { Commit, Relocate, Block, Transition, Cancel };
    auto loop = vstd::event_loop<>::instance();
    for (auto finish : {Finish::Commit, Finish::Relocate, Finish::Block, Finish::Transition, Finish::Cancel}) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto originTile = std::make_shared<CTile>();
        originTile->setCanStep(true);
        auto destinationTile = std::make_shared<CTile>();
        destinationTile->setCanStep(true);
        map->addTile(originTile, 0, 0, 0);
        map->addTile(destinationTile, 1, 0, 0);
        auto creature = add_test_creature(game, "unitAsyncLeaver");
        auto marker = std::make_shared<CEvent>();
        marker->setGame(game);
        marker->setName("unitAsyncLeaveMarker");
        map->addObject(marker);
        auto probe = std::make_shared<AsyncTriggerProbe>();
        auto trigger = std::make_shared<CCustomTrigger>(
            marker->getName(), "onLeave", [probe](auto, auto) { return awaitTriggerProbe(probe, "leave"); });
        trigger->setName("unitAsyncLeaveTrigger");
        map->getEventHandler()->registerTrigger(trigger);
        bool queued = false;
        loop->invoke([&queued] { queued = true; });
        auto waiting = game->getContext()->spawnTask(creature->moveToAsync(Coords(1, 0, 0)));
        expect_true(!waiting.finished() && !queued, "spawning movement must not pump unrelated queued callbacks");
        expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || waiting.finished(); }) &&
                        !waiting.finished() && probe->entered.size() == 1 && creature->getCoords() == Coords(0, 0, 0) &&
                        creature->getPendingMoveOrigin() == std::optional<Coords>(Coords(0, 0, 0)),
                    "a pending leave hook must suspend before committing movement");
        if (finish == Finish::Relocate) {
            creature->relocateWithoutMoveHooks(Coords(3, 0, 0));
        } else if (finish == Finish::Block) {
            destinationTile->setCanStep(false);
        } else if (finish == Finish::Transition) {
            auto replacement = std::make_shared<CMap>();
            replacement->setGame(game);
            game->setMap(replacement);
        } else if (finish == Finish::Cancel) {
            waiting.requestStop();
        }
        probe->released.insert("leave");
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while ((!waiting.finished() || !queued) && std::chrono::steady_clock::now() < deadline) {
            loop->runReady();
            game_async::waitForProgress();
        }
        expect_true(waiting.finished() && queued && !creature->getPendingMoveOrigin(),
                    "movement completion, stale rejection and cancellation must all clear the pending origin");
        const auto expected = finish == Finish::Commit     ? Coords(1, 0, 0)
                              : finish == Finish::Relocate ? Coords(3, 0, 0)
                                                           : Coords(0, 0, 0);
        expect_true(creature->getCoords() == expected,
                    "a leave hook must not commit a stale origin, blocked target or inactive map generation");
        if (waiting.finished()) {
            if (finish == Finish::Cancel) {
                bool cancelled = false;
                try {
                    waiting.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                }
                expect_true(cancelled, "cancelled leave hooks must preserve task cancellation");
            } else {
                waiting.get();
            }
        }
        game->getContext()->shutdown();
    }
}

void testArrivalHooksRejectChangedMapAndGeneration() {
    auto loop = vstd::event_loop<>::instance();
    auto detached = std::make_shared<CCreature>();
    std::weak_ptr<CCreature> lifetime = detached;
    auto lazyArrival = detached->afterMoveAsync();
    detached.reset();
    expect_true(!lifetime.expired(), "a lazy public arrival task must own its actor before execution starts");
    if (!lifetime.expired()) {
        vstd::task_group standalone;
        auto finished = standalone.spawn(std::move(lazyArrival), vstd::loopScheduler(loop));
        expect_true(finished.finished() && lifetime.expired(),
                    "a detached arrival must finish inline and release its owned actor");
    }
    for (bool fromTile : {false, true}) {
        for (bool changeGeneration : {false, true}) {
            auto game = makeWindowlessFightGame();
            auto map = game->getMap();
            auto creature = add_test_creature(game, "unitStaleArrival");
            auto tile = std::make_shared<StepHookCallbackProbe>();
            tile->setCanStep(true);
            map->addTile(tile, 1, 0, 0);
            auto replacement = std::make_shared<CMap>();
            replacement->setGame(game);
            auto changeOwner = [weakGame = std::weak_ptr<CGame>(game), replacement, changeGeneration] {
                auto owner = weakGame.lock();
                if (changeGeneration) {
                    owner->getContext()->advanceTransitionGeneration();
                } else {
                    owner->setMap(replacement);
                }
            };
            if (fromTile) {
                tile->hook = changeOwner;
            }
            int entries = 0;
            for (const auto &name : {"unitFirstArrival", "unitSecondArrival"}) {
                auto marker = std::make_shared<CEvent>();
                marker->setGame(game);
                marker->setName(name);
                marker->setPosX(1);
                map->addObject(marker);
                auto trigger = std::make_shared<CCustomTrigger>(name, "onEnter", [&entries, changeOwner](auto, auto) {
                    ++entries;
                    changeOwner();
                });
                trigger->setName(std::string(name) + "Trigger");
                map->getEventHandler()->registerTrigger(trigger);
            }
            auto move = game->getContext()->spawnTask(creature->moveToAsync(Coords(1, 0, 0)));
            expect_true(pumpHandlerUntil([&] { return move.finished(); }),
                        "a changed arrival owner must finish without waiting for later hooks");
            if (move.finished()) {
                move.get();
            }
            expect_true(tile->steps == 1 && entries == (fromTile ? 0 : 1) && !creature->getPendingMoveOrigin(),
                        "map or generation changes during tile/entry hooks must suppress every later arrival hook");
            game->getContext()->shutdown();
        }
    }
}

void testAsyncNamedSpawnsAwaitEntryWithoutPumping() {
    auto loop = vstd::event_loop<>::instance();
    for (bool cancel : {false, true}) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto targetTile = std::make_shared<CTile>();
        targetTile->setCanStep(true);
        map->addTile(targetTile, 1, 0, 0);
        auto created = std::make_shared<std::shared_ptr<CCreature>>();
        auto constructions = std::make_shared<int>(0);
        game->getObjectHandler()->registerType("unitAsyncSpawnType", [created, constructions] {
            auto creature = std::make_shared<CCreature>();
            creature->setName("unitAsyncSpawnedActor");
            initialize_test_creature_stats(creature);
            creature->setHp(10);
            *created = creature;
            ++*constructions;
            return creature;
        });
        auto marker = std::make_shared<CEvent>();
        marker->setGame(game);
        marker->setName("unitSpawnEntryMarker");
        marker->setPosX(1);
        map->addObject(marker);
        auto probe = std::make_shared<AsyncTriggerProbe>();
        auto trigger = std::make_shared<CCustomTrigger>(
            marker->getName(), "onEnter", [probe](auto, auto) { return awaitTriggerProbe(probe, "spawn"); });
        trigger->setName("unitSpawnEntryReceipt");
        map->getEventHandler()->registerTrigger(trigger);
        bool queued = false;
        loop->invoke([&queued] { queued = true; });
        auto spawn = game->getContext()->spawnTask(map->addObjectByNameAsync("unitAsyncSpawnType", Coords(1, 0, 0)));
        expect_true(!queued && *constructions == 1 && *created && !spawn.finished(),
                    "named spawning must construct/register inline and suspend movement without pumping queued work");
        expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || spawn.finished(); }) &&
                        probe->entered.size() == 1 && !spawn.finished() &&
                        map->getObjectByName((*created)->getName()) == *created &&
                        (*created)->getCoords() == Coords(1, 0, 0),
                    "spawned entry hooks must retain the exact registered actor at its committed destination");
        if (cancel) {
            spawn.requestStop();
        } else {
            probe->released.insert("spawn");
        }
        expect_true(pumpHandlerUntil([&] { return spawn.finished(); }) && !(*created)->getPendingMoveOrigin(),
                    "completion or cancellation must drain the spawn frame and its movement origin");
        bool cancelled = false;
        if (spawn.finished()) {
            try {
                expect_true(spawn.get() == "unitAsyncSpawnType", "successful spawn preserves its legacy name result");
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        expect_true(cancelled == cancel && *constructions == 1 && queued,
                    "spawn cancellation must propagate without cloning or constructing another actor");
        targetTile->setCanStep(false);
        auto blocked = game->getContext()->spawnTask(map->addObjectByNameAsync("unitAsyncSpawnType", Coords(1, 0, 0)));
        expect_true(blocked.finished() && blocked.get().empty() && *constructions == 1,
                    "blocked named spawns must reject before constructing an actor");
        game->getContext()->shutdown();
    }
}

void testAsyncRemovalAwaitsDestroyHooksAndFinalizesCancellation() {
    auto loop = vstd::event_loop<>::instance();
    for (bool respawn : {false, true}) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto object = std::make_shared<DestroyHookProbe>();
        object->setGame(game);
        object->setName("unitAsyncRemoval");
        map->addObject(object);
        if (respawn) {
            std::weak_ptr<CMap> weakMap = map;
            std::weak_ptr<DestroyHookProbe> weakObject = object;
            object->hook = [weakMap, weakObject] { weakMap.lock()->addObject(weakObject.lock()); };
        }
        auto probe = std::make_shared<AsyncTriggerProbe>();
        auto trigger = std::make_shared<CCustomTrigger>(
            object->getName(), "onDestroy", [probe](auto, auto) { return awaitTriggerProbe(probe, "destroy"); });
        trigger->setName("unitAsyncRemovalTrigger");
        map->getEventHandler()->registerTrigger(trigger);
        bool queued = false;
        loop->invoke([&queued] { queued = true; });
        auto pending = game->getContext()->spawnTask(map->removeObjectAsync(object));
        expect_true(!pending.finished() && !queued && !map->getObjectByName(object->getName()),
                    "removal must detach inline without pumping destruction hooks or unrelated work");
        expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || pending.finished(); }) &&
                        !pending.finished() && object->destroyed == 1 && probe->entered.size() == 1 &&
                        (map->getObjectByName(object->getName()) == object) == respawn,
                    "removal must await destruction hooks and preserve hook-respawned identity");
        pending.requestStop();
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while ((!pending.finished() || !queued) && std::chrono::steady_clock::now() < deadline) {
            loop->runReady();
            game_async::waitForProgress();
        }
        bool cancelled = false;
        if (pending.finished()) {
            try {
                pending.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        auto replacement = std::make_shared<CMap>();
        replacement->setGame(game);
        game->setMap(replacement);
        expect_true(cancelled && object->destroyed == 1 && object->getMap() == (respawn ? map : replacement),
                    "cancelled removal must release detached map ownership while retaining a hook-respawned owner");
        game->getContext()->shutdown();
    }

    auto game = makeWindowlessFightGame();
    auto winner = add_test_creature(game, "unitAsyncDestroyWinner");
    auto loser = add_test_creature(game, "unitAsyncDestroyLoser", 1, 0);
    loser->setHp(0);
    auto probe = std::make_shared<AsyncTriggerProbe>();
    auto trigger = std::make_shared<CCustomTrigger>(loser->getName(), "onDestroy",
                                                    [probe](auto, auto) { return awaitTriggerProbe(probe, "defeat"); });
    trigger->setName("unitAsyncDefeatDestroy");
    game->getMap()->getEventHandler()->registerTrigger(trigger);
    bool queued = false;
    loop->invoke([&queued] { queued = true; });
    auto defeat = game->getContext()->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
    expect_true(!defeat.finished() && !queued, "native defeat must return without pumping unrelated queued work");
    expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || defeat.finished(); }) && !defeat.finished() &&
                    probe->entered.size() == 1 && !game->getMap()->getObjectByName(loser->getName()),
                "native defeat must await destruction receipts without entering the synchronous removal adapter");
    probe->released.insert("defeat");
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (!defeat.finished() && std::chrono::steady_clock::now() < deadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(defeat.finished() && queued && probe->entered.size() == 1,
                "the outer loop must finish each defeated actor's destruction hook once");
    if (defeat.finished()) {
        defeat.get();
    }
    game->getContext()->shutdown();

    auto pickupGame = makeWindowlessFightGame();
    auto pickupMap = pickupGame->getMap();
    auto floor = std::make_shared<CTile>();
    floor->setCanStep(true);
    pickupMap->addTile(floor, 1, 0, 0);
    auto visitor = add_test_creature(pickupGame, "unitAsyncPickupVisitor");
    auto item = std::make_shared<CItem>();
    item->setGame(pickupGame);
    item->setName("unitAsyncPickupItem");
    item->setPosX(1);
    pickupMap->addObject(item);
    auto pickupProbe = std::make_shared<AsyncTriggerProbe>();
    auto pickupTrigger = std::make_shared<CCustomTrigger>(
        item->getName(), "onDestroy", [pickupProbe](auto, auto) { return awaitTriggerProbe(pickupProbe, "pickup"); });
    pickupTrigger->setName("unitAsyncPickupDestroy");
    pickupMap->getEventHandler()->registerTrigger(pickupTrigger);
    bool pickupQueued = false;
    loop->invoke([&pickupQueued] { pickupQueued = true; });
    auto pickup = pickupGame->getContext()->spawnTask(visitor->moveToAsync(Coords(1, 0, 0)));
    expect_true(!pickup.finished() && !pickupQueued, "native pickup must return without pumping unrelated queued work");
    expect_true(pumpHandlerUntil([&] { return !pickupProbe->entered.empty() || pickup.finished(); }) &&
                    !pickup.finished() && pickupProbe->entered.size() == 1 && visitor->hasInInventory(item) &&
                    !pickupMap->getObjectByName(item->getName()),
                "native item pickup must transfer the exact item then await destruction without nested polling");
    pickup.requestStop();
    const auto pickupDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while ((!pickup.finished() || !pickupQueued) && std::chrono::steady_clock::now() < pickupDeadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    bool pickupCancelled = false;
    if (pickup.finished()) {
        try {
            pickup.get();
        } catch (const vstd::task_cancelled &) {
            pickupCancelled = true;
        }
    }
    auto pickupReplacement = std::make_shared<CMap>();
    pickupReplacement->setGame(pickupGame);
    pickupGame->setMap(pickupReplacement);
    expect_true(
        pickupCancelled && visitor->hasInInventory(item) && item->getMap() == pickupReplacement &&
            !visitor->getPendingMoveOrigin() && pickupMap->getTurn() == 0,
        "cancelled pickup receipts must release old-map ownership without losing or cloning the inventory item");
    pickupGame->getContext()->shutdown();
}

void testAsyncEventHooksStopAfterContextShutdown() {
    auto loop = vstd::event_loop<>::instance();
    for (bool owned : {false, true}) {
        for (bool shutdownInObject : {false, true}) {
            auto game = makeWindowlessFightGame();
            auto context = game->getContext();
            auto handler = game->getMap()->getEventHandler();
            auto object = std::make_shared<TurnHookRegistrationProbe>();
            object->setGame(game);
            object->setName("unitShutdownEventObject");
            int objectCalls = 0;
            int triggerCalls = 0;
            object->hook = [&objectCalls, shutdownInObject, context] {
                ++objectCalls;
                if (shutdownInObject) {
                    context->shutdown();
                }
            };
            for (const auto &name : {"unitShutdownFirst", "unitShutdownSecond"}) {
                auto trigger =
                    std::make_shared<CCustomTrigger>(object->getName(), "onTurn", [&triggerCalls, context](auto, auto) {
                        ++triggerCalls;
                        context->shutdown();
                    });
                trigger->setName(name);
                handler->registerTrigger(trigger);
            }
            vstd::task_group standalone;
            auto task = handler->gameEventAsync(object, std::make_shared<CGameEvent>(CGameEvent::CType::onTurn));
            auto pending = owned ? context->spawnTask(std::move(task))
                                 : standalone.spawn(std::move(task), vstd::loopScheduler(loop));
            const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
            while (!pending.finished() && std::chrono::steady_clock::now() < deadline) {
                loop->runReady();
                game_async::waitForProgress();
            }
            bool cancelled = false;
            if (pending.finished()) {
                try {
                    pending.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                }
            }
            expect_true(cancelled && objectCalls == 1 && triggerCalls == (shutdownInObject ? 0 : 1),
                        "context shutdown in an object or trigger must stop later observers, even in an unowned task");
            context->shutdown();
        }
        auto game = makeWindowlessFightGame();
        auto creature = add_test_creature(game, "unitShutdownTileVisitor");
        auto tile = std::make_shared<StepHookShutdownProbe>();
        tile->context = game->getContext();
        vstd::task_group standalone;
        auto task = CEventHandler::tileStepAsync(tile, creature);
        auto pending = owned ? tile->context->spawnTask(std::move(task))
                             : standalone.spawn(std::move(task), vstd::loopScheduler(loop));
        for (int iteration = 0; iteration < 12; ++iteration) {
            loop->runReady();
        }
        bool cancelled = false;
        if (pending.finished()) {
            try {
                pending.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        auto rejected = standalone.spawn(CEventHandler::tileStepAsync(tile, creature), vstd::loopScheduler(loop));
        bool closedCancelled = false;
        if (rejected.finished()) {
            try {
                rejected.get();
            } catch (const vstd::task_cancelled &) {
                closedCancelled = true;
            }
        }
        expect_true(cancelled && closedCancelled && tile->steps == 1,
                    "tile hooks must propagate shutdown cancellation and reject another hook on the closed context");
        tile->context->shutdown();
    }
}

class DefeatContinuationCreature : public CCreature {
  public:
    std::function<void()> formatting;
    std::function<void()> gathering;

    std::string to_string() override {
        if (formatting) {
            auto callback = std::move(formatting);
            formatting = {};
            callback();
        }
        return CCreature::to_string();
    }

    std::set<std::shared_ptr<CItem>> getAllItems() override {
        if (gathering) {
            auto callback = std::move(gathering);
            gathering = {};
            callback();
        }
        return CCreature::getAllItems();
    }
};

class EquipmentTailItem : public CItem {
  public:
    std::function<void()> equipCallback;
    std::function<void()> unequipCallback;
    void onEquip(std::shared_ptr<CGameEvent>) override {
        if (equipCallback)
            equipCallback();
    }
    void onUnequip(std::shared_ptr<CGameEvent>) override {
        if (unequipCallback)
            unequipCallback();
    }
};

void testScopedEquipmentTailStopsAfterCallbackInvalidation() {
    const auto previousRng = vstd::rng();
    for (const bool unequip : {false, true}) {
        for (const int publication : {0, 1, 2, 3}) {
            auto game = makeWindowlessFightGame();
            auto context = game->getContext();
            auto map = game->getMap();
            auto winner = add_test_creature(game, "unitEquipmentTailWinner");
            auto loser = add_test_creature(game, "unitEquipmentTailLoser");
            loser->setLevel(0);
            loser->setSw(1);
            loser->setHp(0);
            auto objects = game->getObjectHandler();
            auto slots = std::make_shared<CSlotConfig>();
            auto slot = std::make_shared<CSlot>();
            slot->setTypes({"CItem"});
            slots->setConfiguration({{"0", slot}});
            objects->registerType("UnitEquipmentTailSlots", [slots] { return slots; });
            objects->registerConfig("slotConfiguration",
                                    std::make_shared<json>(json{{"class", "UnitEquipmentTailSlots"}}));
            auto incoming = std::make_shared<EquipmentTailItem>();
            incoming->setGame(game);
            incoming->setName("unitEquipmentTailIncoming");
            winner->addItem(incoming);
            auto previous = std::make_shared<EquipmentTailItem>();
            previous->setGame(game);
            previous->setName("unitEquipmentTailPrevious");
            if (unequip) {
                winner->addItem(previous);
                winner->equipItem("0", previous);
            }
            bool armed = false;
            bool used = false;
            int factories = 0;
            int callbacks = 0;
            int experienceAtCallback = -1;
            const auto invalidate = [&] {
                ++callbacks;
                experienceAtCallback = winner->getExp();
                if (publication == 1 || publication == 3) {
                    auto replacement = std::make_shared<CMap>();
                    replacement->setGame(game);
                    game->setMap(replacement);
                    game->setMap(map);
                } else if (publication == 2) {
                    auto replacement = std::make_shared<CMap>();
                    replacement->setGame(game);
                    game->setMap(replacement);
                } else {
                    game->setMap(map);
                }
                if (publication == 3)
                    throw std::runtime_error("unit equipment tail primary failure");
            };
            objects->registerType("AUnitEquipmentTailScopeRoot", [&] {
                auto root = std::make_shared<CItem>();
                root->setPower(1);
                if (armed && !used) {
                    used = true;
                    ++factories;
                    if (unequip)
                        previous->unequipCallback = invalidate;
                    else
                        incoming->equipCallback = invalidate;
                    winner->equipItem("0", incoming);
                }
                return root;
            });
            objects->registerConfig("AUnitEquipmentTailScopeRoot",
                                    std::make_shared<json>(json{{"class", "AUnitEquipmentTailScopeRoot"}}));
            auto rng = game->getRngHandler();
            expect_true(rng && callbacks == 0 && !used, "warm RNG before entering the measured private scope");
            armed = true;
            auto task = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
            expect_true(pumpHandlerUntil([&] { return task.finished(); }), "the finite equipment task must settle");
            bool cancelled = false;
            bool primary = false;
            if (task.finished()) {
                try {
                    task.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                } catch (const std::runtime_error &error) {
                    primary = std::string(error.what()) == "unit equipment tail primary failure";
                }
            }
            armed = false;
            expect_true(factories == 1 && callbacks == 1, "each control must execute one actual factory and hook");
            if (publication == 0) {
                expect_true(!cancelled && !primary && winner->getItemAtSlot("0") == incoming &&
                                !winner->getItems().contains(incoming) &&
                                (!unequip || winner->getItems().contains(previous)) &&
                                !map->getObjectByName(loser->getName()) && map->tryBeginSaveSnapshot().has_value(),
                            "same-pointer publication must preserve ordinary equipment and defeat completion");
            } else {
                expect_true(cancelled == (publication != 3) && primary == (publication == 3) &&
                                winner->getItems().contains(incoming) &&
                                winner->getItemAtSlot("0") == (unequip ? previous : nullptr) &&
                                !winner->getItems().contains(previous) && winner->getExp() == experienceAtCallback &&
                                map->getObjectByName(loser->getName()) == loser && !map->tryBeginSaveSnapshot(),
                            "stale equipment callbacks must stop before bag/slot writes and later defeat effects");
            }
            context->shutdown();
        }
    }
    vstd::rng() = previousRng;
}
void testOwnedDefeatStopsAfterCallbackPublicationBeforeFurtherRewards() {
    for (const bool atGathering : {false, true}) {
        for (const int publication : {0, 1, 2, 3}) {
            auto game = makeWindowlessFightGame();
            auto context = game->getContext();
            auto map = game->getMap();
            map->setBoolProperty("plugin_cityFixedLoot", true);
            auto winner = add_test_creature(game, "unitEpochRewardWinner");
            auto loser = std::make_shared<DefeatContinuationCreature>();
            loser->setGame(game);
            loser->setName("unitEpochRewardLoser");
            initialize_test_creature_stats(loser);
            map->addObject(loser);
            loser->setHp(0);
            auto item = add_unit_loot(game, loser, "unitEpochRewardItem");
            const auto experience = winner->getExp();
            const auto generation = context->captureTransitionGeneration();
            const auto epoch = game->getMapBindingEpoch();
            int calls = 0;
            int experienceAtCallback = -1;
            auto callback = [&] {
                ++calls;
                experienceAtCallback = winner->getExp();
                if (publication == 0) {
                    game->setMap(map);
                } else {
                    auto replacement = std::make_shared<CMap>();
                    replacement->setGame(game);
                    game->setMap(replacement);
                    if (publication != 2) {
                        game->setMap(map);
                    }
                }
                if (publication == 3) {
                    throw std::runtime_error("unit defeat callback primary failure");
                }
            };
            if (atGathering) {
                loser->gathering = callback;
            } else {
                loser->formatting = callback;
            }
            auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
            bool cancelled = false;
            bool primary = false;
            expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                        "callback publication controls must finish without a modal or nested event pump");
            if (owner.finished()) {
                try {
                    owner.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                } catch (const std::runtime_error &error) {
                    primary = std::string(error.what()) == "unit defeat callback primary failure";
                }
            }
            expect_true(calls == 1 && context->isTransitionGenerationCurrent(generation) &&
                            game->getMapBindingEpoch() == epoch + (publication == 0   ? 0
                                                                   : publication == 2 ? 1
                                                                                      : 2),
                        "actual public map publication must distinguish no-op, replacement and away/back epochs");
            if (publication == 0) {
                expect_true(!cancelled && !primary && winner->hasInInventory(item) &&
                                !map->getObjectByName(loser->getName()) && map->tryBeginSaveSnapshot().has_value(),
                            "same-pointer publication must preserve ordinary complete defeat rewards and admission");
            } else {
                expect_true(cancelled == (publication != 3) && primary == (publication == 3) &&
                                winner->getExp() == experienceAtCallback &&
                                (atGathering || winner->getExp() == experience) && loser->hasInInventory(item) &&
                                !winner->hasInInventory(item) && map->getObjectByName(loser->getName()) == loser &&
                                !map->tryBeginSaveSnapshot(),
                            "a callback must stop subsequent XP/item/removal effects and retain uncertain admission");
            }
            context->shutdown();
        }
    }
}

void testOwnedDefeatLootContinuationRejectsStalePublicationAndCancellation() {
    for (const bool stale : {false, true}) {
        for (const bool stop : {false, true}) {
            auto game = makeWindowlessFightGame();
            auto context = game->getContext();
            auto map = game->getMap();
            map->setBoolProperty("plugin_cityFixedLoot", true);
            auto winner = add_test_player(game);
            auto loser = add_test_creature(game, "unitEpochLootLoser", 1, 0);
            auto item = add_unit_loot(game, loser, "unitEpochLootItem");
            loser->setHp(0);
            auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
            expect_true(
                pumpHandlerUntil([&] { return game->getGui()->findChild("CGameLootPanel") || owner.finished(); }),
                "the continuation fixture must enter the actual native loot await");
            auto panel = vstd::cast<CGameLootPanel>(game->getGui()->findChild("CGameLootPanel"));
            expect_true(panel && !owner.finished() && !winner->hasInInventory(item) && !loser->hasInInventory(item) &&
                            !map->tryBeginSaveSnapshot(),
                        "the real pending loot receipt must own removed items and admission before continuation");
            if (!panel) {
                context->shutdown();
                continue;
            }
            const auto experience = winner->getExp();
            const auto epoch = game->getMapBindingEpoch();
            if (stale) {
                auto replacement = std::make_shared<CMap>();
                replacement->setGame(game);
                game->setMap(replacement);
                game->setMap(map);
            }
            if (stop) {
                owner.requestStop();
            } else {
                panel->close();
            }
            bool cancelled = false;
            expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                        "actual loot continuation or cancellation must drain the owned task");
            if (owner.finished()) {
                try {
                    owner.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                }
            }
            expect_true(game->getMapBindingEpoch() == epoch + (stale ? 2 : 0) && cancelled == (stale || stop) &&
                            winner->getExp() == experience,
                        "publication cancellation must remain distinct from a live requested cancellation");
            if (stale) {
                expect_true(!winner->hasInInventory(item) && !loser->hasInInventory(item) &&
                                map->getObjectByName(loser->getName()) == loser && !map->tryBeginSaveSnapshot(),
                            "neither child grant nor parent compensation may mutate after an away/back loot await");
            } else {
                expect_true(
                    winner->hasInInventory(item) && winner->countItems("unitEpochLootItem") == 1 &&
                        !map->getObjectByName(loser->getName()) && map->tryBeginSaveSnapshot().has_value(),
                    "live cancellation must retain existing exactly-once grant/removal/certification semantics");
            }
            context->shutdown();
        }
    }
}

void testOwnedDefeatRemovalCannotCertifyAnAwayBackPublication() {
    for (const bool stale : {false, true}) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto map = game->getMap();
        map->setBoolProperty("plugin_cityFixedLoot", true);
        auto winner = add_test_creature(game, "unitEpochRecoveryWinner", 1, 0);
        auto player = add_test_player(game);
        auto item = add_unit_loot(game, player, "unitEpochRecoveryItem");
        std::shared_ptr<CCustomTrigger> restart;
        for (const auto &trigger : map->getEventHandler()->getTriggers()) {
            if (trigger->getObject() == "player" && trigger->getEvent() == "onDestroy") {
                restart = std::dynamic_pointer_cast<CCustomTrigger>(trigger);
            }
        }
        expect_true(restart != nullptr, "the epoch fixture must wrap the actual canonical player's restart slot");
        if (!restart) {
            context->shutdown();
            continue;
        }
        auto nativeRestart = std::make_shared<CCustomTrigger>(*restart);
        auto gate = std::make_shared<AsyncTriggerProbe>();
        *restart =
            CCustomTrigger("player", "onDestroy", [gate, nativeRestart](auto object, auto event) -> vstd::task<void> {
                co_await awaitTriggerProbe(gate, "epochRecovery");
                co_await nativeRestart->triggerAsync(object, event);
            });
        restart->setName("unitEpochRecoveryRestartWrapper");
        player->setHp(0);
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, player));
        expect_true(pumpHandlerUntil([&] { return !gate->entered.empty() || owner.finished(); }) &&
                        gate->entered.size() == 1 && !owner.finished(),
                    "the epoch witness must suspend the actual removal before native restart");
        const auto experience = winner->getExp();
        const auto generation = context->captureTransitionGeneration();
        const auto epoch = game->getMapBindingEpoch();
        if (stale) {
            auto replacement = std::make_shared<CMap>();
            replacement->setGame(game);
            game->setMap(replacement);
            game->setMap(map);
        }
        gate->released.insert("epochRecovery");
        bool cancelled = false;
        expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                    "the one wrapped restart must drain exactly once");
        if (owner.finished()) {
            try {
                owner.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        expect_true(context->isTransitionGenerationCurrent(generation) &&
                        game->getMapBindingEpoch() == epoch + (stale ? 2 : 0) && cancelled == stale &&
                        winner->getExp() == experience && winner->hasInInventory(item) &&
                        winner->countItems("unitEpochRecoveryItem") == 1 && gate->entered.size() == 1 &&
                        map->getAssignedPlayer() == player && map->getObjectByName("player") == player &&
                        player->getHp() == 1,
                    "real restart effects may complete, but an epoch change cannot inherit the old certificate");
        expect_true(player->getStringProperty("uiDefeatReceipt").empty() == stale &&
                        map->tryBeginSaveSnapshot().has_value() == !stale,
                    "only the unchanged publication may store the recovered receipt and release admission");
        context->shutdown();
    }
}

void testOwnedDefeatGuardsLazyRngFactoryEnumeration() {
    const auto previousRng = vstd::rng();
    for (const int phase : {0, 1, 2, 3}) {
        for (const int publication : {0, 1, 2, 3}) {
            auto game = makeWindowlessFightGame();
            auto context = game->getContext();
            auto map = game->getMap();
            auto winner = add_test_creature(game, "unitLazyFactoryWinner");
            auto loser = add_test_creature(game, "unitLazyFactoryLoser");
            loser->setHp(0);
            auto objects = game->getObjectHandler();
            int firstItem = 0;
            int sentinelItem = 0;
            int firstCreature = 0;
            int sentinelCreature = 0;
            int calls = 0;
            int sentinelAtCallback = -1;
            int experienceAtCallback = -1;
            const auto epoch = game->getMapBindingEpoch();
            auto callback = [&] {
                ++calls;
                sentinelAtCallback = phase == 3 ? sentinelCreature : sentinelItem;
                experienceAtCallback = winner->getExp();
                if (publication == 0) {
                    game->setMap(map);
                } else {
                    auto replacement = std::make_shared<CMap>();
                    replacement->setGame(game);
                    game->setMap(replacement);
                    if (publication != 2) {
                        game->setMap(map);
                    }
                }
                if (publication == 3) {
                    throw std::runtime_error("unit lazy RNG factory primary failure");
                }
            };
            objects->registerType("AUnitDefeatItemFactory", [&] {
                ++firstItem;
                if (phase < 3 && firstItem == phase + 1) {
                    callback();
                }
                auto item = std::make_shared<CItem>();
                item->setPower(1);
                return item;
            });
            objects->registerType("ZUnitDefeatItemSentinel", [&] {
                ++sentinelItem;
                auto item = std::make_shared<CItem>();
                item->setPower(1);
                return item;
            });
            objects->registerType("BUnitDefeatCreatureFactory", [&] {
                ++firstCreature;
                if (phase == 3 && firstCreature == 4) {
                    callback();
                }
                auto creature = std::make_shared<CCreature>();
                creature->setNpc(true);
                return creature;
            });
            objects->registerType("ZUnitDefeatCreatureSentinel", [&] {
                ++sentinelCreature;
                auto creature = std::make_shared<CCreature>();
                creature->setNpc(true);
                return creature;
            });
            for (const std::string name : {"AUnitDefeatItemFactory", "ZUnitDefeatItemSentinel",
                                           "BUnitDefeatCreatureFactory", "ZUnitDefeatCreatureSentinel"}) {
                objects->registerConfig(name, std::make_shared<json>(json{{"class", name}}));
                expect_true(objects->getConfig(name) && objects->getClass(name) == name,
                            "the lazy fixture must bind every registered constructor through actual class metadata");
            }
            expect_true(firstItem == 0 && sentinelItem == 0 && firstCreature == 0 && sentinelCreature == 0,
                        "the lazy factory fixture must begin with no constructor or RNG-service warmup");
            auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
            bool cancelled = false;
            bool primary = false;
            expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                        "guarded lazy RNG initialization must finish without a modal or nested pump");
            if (owner.finished()) {
                try {
                    owner.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                } catch (const std::runtime_error &error) {
                    primary = std::string(error.what()) == "unit lazy RNG factory primary failure";
                }
            }
            expect_true(calls == 1 && game->getMapBindingEpoch() == epoch + (publication == 0   ? 0
                                                                             : publication == 2 ? 1
                                                                                                : 2),
                        "actual prototype/item/creature factory callbacks must publish the expected native epoch");
            if (publication == 0) {
                expect_true(!cancelled && !primary && !map->getObjectByName(loser->getName()) &&
                                map->tryBeginSaveSnapshot().has_value(),
                            "same-pointer factory callbacks must preserve normal initialization and defeat settlement");
            } else {
                const int sentinelAfter = phase == 3 ? sentinelCreature : sentinelItem;
                expect_true(sentinelAfter == sentinelAtCallback && cancelled == (publication != 3) &&
                                primary == (publication == 3) && winner->getExp() == experienceAtCallback &&
                                map->getObjectByName(loser->getName()) == loser && !map->tryBeginSaveSnapshot(),
                            "a stale or throwing factory must stop before the next constructor and retain uncertainty");
            }
            context->shutdown();
        }
    }
    vstd::rng() = previousRng;
}

void testOwnedDefeatStopsBeforeSecondRandomLootFactory() {
    const auto previousRng = vstd::rng();
    for (const int publication : {0, 1, 2, 3}) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto map = game->getMap();
        auto winner = add_test_creature(game, "unitTwoFactoryWinner");
        auto loser = add_test_creature(game, "unitTwoFactoryLoser");
        loser->setLevel(0);
        loser->setSw(2);
        loser->setHp(0);
        bool armed = false;
        int factories = 0;
        int secondConstructor = 0;
        int experienceAtCallback = -1;
        game->getObjectHandler()->registerType("AUnitTwoFactoryItem", [&] {
            if (armed) {
                ++factories;
                if (factories == 1) {
                    experienceAtCallback = winner->getExp();
                    if (publication == 0) {
                        game->setMap(map);
                    } else {
                        auto replacement = std::make_shared<CMap>();
                        replacement->setGame(game);
                        game->setMap(replacement);
                        if (publication != 2) {
                            game->setMap(map);
                        }
                    }
                    if (publication == 3) {
                        throw std::runtime_error("unit generated loot factory primary failure");
                    }
                } else {
                    ++secondConstructor;
                }
            }
            auto item = std::make_shared<CItem>();
            item->setPower(1);
            return item;
        });
        game->getObjectHandler()->registerConfig(
            "AUnitTwoFactoryItem", std::make_shared<json>(json{{"class", "AUnitTwoFactoryItem"}}));
        expect_true(game->getObjectHandler()->getConfig("AUnitTwoFactoryItem") &&
                        game->getObjectHandler()->getClass("AUnitTwoFactoryItem") == "AUnitTwoFactoryItem",
                    "the two-constructor fixture must populate the actual configured item table before arming");
        auto rng = game->getRngHandler();
        expect_true(rng && loser->getScale() == 2 && factories == 0,
                    "warm only the public RNG cache before arming an exact two-unit/power-one loot workload");
        armed = true;
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        bool cancelled = false;
        bool primary = false;
        expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                    "the two-constructor loot sentinel must finish without a modal or nested pump");
        if (owner.finished()) {
            try {
                owner.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            } catch (const std::runtime_error &error) {
                primary = std::string(error.what()) == "unit generated loot factory primary failure";
            }
        }
        if (publication == 0) {
            expect_true(!cancelled && !primary && factories == 2 && secondConstructor == 1 &&
                            winner->getItems().size() == 2 && !map->getObjectByName(loser->getName()) &&
                            map->tryBeginSaveSnapshot().has_value(),
                        "the unchanged random policy must create and grant both legitimate power-one items");
        } else {
            expect_true(factories == 1 && secondConstructor == 0 && cancelled == (publication != 3) &&
                            primary == (publication == 3) && winner->getItems().empty() &&
                            winner->getExp() == experienceAtCallback &&
                            map->getObjectByName(loser->getName()) == loser && !map->tryBeginSaveSnapshot(),
                        "publication in the first generated constructor must block the second and every later grant");
        }
        context->shutdown();
    }
    vstd::rng() = previousRng;
}

class DefeatMetaBarrierItem : public CItem {
  public:
    int metadataCalls = 0;
    std::function<void()> metadataCallback;

    std::shared_ptr<vstd::meta> meta() override {
        ++metadataCalls;
        if (metadataCallback) {
            auto callback = std::move(metadataCallback);
            metadataCallback = {};
            callback();
        }
        return CItem::meta();
    }
};

class DefeatCodecBoundaryProbe : public CSerializerBase {
  public:
    std::shared_ptr<const CSerializerBase> original;
    std::function<void()> callback;

    CSerializationResult<json> serialize(const std::any &value, CSerializationWriteContext &context) const override {
        return original->serialize(value, context);
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &value,
                                               CSerializationReadContext &context) const override {
        if (value.is_object() && value.contains("unitCodecProbe")) {
            callback();
            return std::any(std::make_shared<CStats>());
        }
        return original->deserialize(game, value, context);
    }
};

void testOwnedDefeatCodecBoundaryPreservesOriginalFailureAndStopsContinuation() {
    const auto previousRng = vstd::rng();
    for (const int publication : {0, 1, 2, 3}) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto map = game->getMap();
        auto winner = add_test_creature(game, "unitCodecBoundaryWinner");
        auto loser = add_test_creature(game, "unitCodecBoundaryLoser");
        loser->setLevel(0);
        loser->setSw(1);
        loser->setHp(0);
        bool armed = false;
        int calls = 0;
        int experienceAtCallback = -1;
        std::shared_ptr<CItem> constructed;
        auto objects = game->getObjectHandler();
        objects->registerType("AUnitCodecBoundaryItem", [&] {
            auto item = std::make_shared<CItem>();
            item->setPower(1);
            if (armed) {
                constructed = item;
            }
            return item;
        });
        objects->registerConfig(
            "AUnitCodecBoundaryItem",
            std::make_shared<json>(
                json{{"class", "AUnitCodecBoundaryItem"},
                     {"properties", json{{"bonus", json{{"unitCodecProbe", true}}}, {"zAfterCodec", 123}}}}));
        expect_true(objects->getConfig("AUnitCodecBoundaryItem") &&
                        objects->getClass("AUnitCodecBoundaryItem") == "AUnitCodecBoundaryItem",
                    "the codec callback must come from the actual configured item table");
        auto rng = game->getRngHandler();
        auto original = CTypes::findCodec(typeid(std::shared_ptr<CStats>));
        expect_true(rng && original && calls == 0, "warm ordinary malformed-property handling before arming the codec");
        if (!original) {
            context->shutdown();
            continue;
        }
        struct RestoreCodec {
            std::shared_ptr<const CSerializerBase> original;
            ~RestoreCodec() { CTypes::registerCodec(typeid(std::shared_ptr<CStats>), original); }
        } restore{original};
        auto probe = std::make_shared<DefeatCodecBoundaryProbe>();
        probe->original = original;
        probe->callback = [&] {
            ++calls;
            experienceAtCallback = winner->getExp();
            if (publication == 0) {
                game->setMap(map);
            } else {
                auto replacement = std::make_shared<CMap>();
                replacement->setGame(game);
                game->setMap(replacement);
                if (publication != 2) {
                    game->setMap(map);
                }
            }
            if (publication == 3) {
                throw std::runtime_error("unit codec boundary primary failure");
            }
        };
        CTypes::registerCodec(typeid(std::shared_ptr<CStats>), probe);
        armed = true;
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        bool cancelled = false;
        bool primary = false;
        expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                    "codec boundary controls must finish without a modal or a nested event pump");
        if (owner.finished()) {
            try {
                owner.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            } catch (const std::runtime_error &error) {
                primary = std::string(error.what()) == "unit codec boundary primary failure";
            }
        }
        expect_true(constructed && calls == 1, "the actual codec callback must execute exactly once");
        if (publication == 0) {
            expect_true(!cancelled && !primary && constructed->getNumericProperty("zAfterCodec") == 123 &&
                            winner->hasInInventory(constructed) && map->tryBeginSaveSnapshot().has_value(),
                        "a current codec callback must retain ordinary assignment and defeat completion");
        } else {
            expect_true(cancelled == (publication != 3) && primary == (publication == 3) && constructed &&
                            constructed->getNumericProperty("zAfterCodec") == 0 && winner->getItems().empty() &&
                            winner->getExp() == experienceAtCallback &&
                            map->getObjectByName(loser->getName()) == loser && !map->tryBeginSaveSnapshot(),
                        "a throwing stale codec must preserve its original primary and block every later setter");
        }
        CTypes::registerCodec(typeid(std::shared_ptr<CStats>), original);
        context->shutdown();
    }
    vstd::rng() = previousRng;
}

void testOwnedDefeatNestedFactoryStopsBeforeNextPropertyAndConstructor() {
    const auto previousRng = vstd::rng();
    for (const int publication : {0, 1, 2, 3}) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto map = game->getMap();
        auto winner = add_test_creature(game, "unitNestedFactoryWinner");
        auto loser = add_test_creature(game, "unitNestedFactoryLoser");
        loser->setLevel(0);
        loser->setSw(1);
        loser->setHp(0);
        auto objects = game->getObjectHandler();
        bool armed = false;
        int firstConstructor = 0;
        int secondConstructor = 0;
        int experienceAtCallback = -1;
        std::shared_ptr<CItem> constructed;
        objects->registerType("AUnitNestedRootItem", [&] {
            auto item = std::make_shared<CItem>();
            item->setPower(1);
            if (armed) {
                constructed = item;
            }
            return item;
        });
        objects->registerType("BUnitNestedFirstChild", [&] {
            if (armed) {
                ++firstConstructor;
                experienceAtCallback = winner->getExp();
                if (publication == 0) {
                    game->setMap(map);
                } else {
                    auto replacement = std::make_shared<CMap>();
                    replacement->setGame(game);
                    game->setMap(replacement);
                    if (publication != 2) {
                        game->setMap(map);
                    }
                }
                if (publication == 3) {
                    throw std::runtime_error("unit nested factory primary failure");
                }
            }
            return std::make_shared<CGameObject>();
        });
        objects->registerType("ZUnitNestedSecondChild", [&] {
            if (armed) {
                ++secondConstructor;
            }
            return std::make_shared<CGameObject>();
        });
        const json properties{{"aFirstChild", json{{"class", "BUnitNestedFirstChild"}}},
                              {"mAfterFirstScalar", 123},
                              {"power", json{{"class", "BUnitNestedFirstChild"}}},
                              {"zSecondChild", json{{"class", "ZUnitNestedSecondChild"}}}};
        std::vector<std::string> propertyOrder;
        for (auto [key, value] : properties.items()) {
            propertyOrder.push_back(key);
        }
        expect_true(propertyOrder ==
                        std::vector<std::string>{"aFirstChild", "mAfterFirstScalar", "power", "zSecondChild"},
                    "the actual configured property iteration must place the scalar between the two child factories");
        objects->registerConfig("AUnitNestedRootItem", std::make_shared<json>(json{{"class", "AUnitNestedRootItem"},
                                                                                   {"properties", properties}}));
        for (const std::string name : {"BUnitNestedFirstChild", "ZUnitNestedSecondChild"}) {
            objects->registerConfig(name, std::make_shared<json>(json{{"class", name}}));
        }
        for (const std::string name : {"AUnitNestedRootItem", "BUnitNestedFirstChild", "ZUnitNestedSecondChild"}) {
            expect_true(objects->getConfig(name) && objects->getClass(name) == name,
                        "each nested sentinel must have an actual native constructor and matching class configuration");
        }
        auto rng = game->getRngHandler();
        expect_true(rng && loser->getScale() == 1 && firstConstructor == 0 && secondConstructor == 0,
                    "public warmup must finish before the measured one-component nested factory workload is armed");
        armed = true;
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        bool cancelled = false;
        bool primary = false;
        expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                    "nested factory controls must finish without a modal or a nested event pump");
        if (owner.finished()) {
            try {
                owner.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            } catch (const std::runtime_error &error) {
                primary = std::string(error.what()) == "unit nested factory primary failure";
            }
        }
        expect_true(constructed && firstConstructor == 1,
                    "the first actual nested constructor must run once so the blocked sentinel cannot pass vacuously");
        if (publication == 0) {
            expect_true(!cancelled && !primary && secondConstructor == 1 &&
                            constructed->getNumericProperty("mAfterFirstScalar") == 123 &&
                            constructed->getPower() == 1 && winner->hasInInventory(constructed) &&
                            !map->getObjectByName(loser->getName()) && map->tryBeginSaveSnapshot().has_value(),
                        "same-pointer control must retain ordinary non-strict malformed-property skip and full defeat");
        } else {
            expect_true(
                cancelled == (publication != 3) && primary == (publication == 3) && secondConstructor == 0 &&
                    constructed && constructed->getNumericProperty("mAfterFirstScalar") == 0 &&
                    winner->getItems().empty() && winner->getExp() == experienceAtCallback &&
                    map->getObjectByName(loser->getName()) == loser && !map->tryBeginSaveSnapshot(),
                "nested publication or original failure must stop both the intermediate scalar and second factory");
        }
        expect_true(objects->getType("AUnitNestedRootItem") != nullptr,
                    "the private synchronous construction scope must expire after the owned task unwinds");
        context->shutdown();
    }
    vstd::rng() = previousRng;
}

void testOwnedDefeatFirstMetadataCallbackStopsBeforeSecondMetadataAndSetter() {
    const auto previousRng = vstd::rng();
    for (const int publication : {0, 1, 2, 3}) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto map = game->getMap();
        auto winner = add_test_creature(game, "unitMetaFactoryWinner");
        auto loser = add_test_creature(game, "unitMetaFactoryLoser");
        loser->setLevel(0);
        loser->setSw(1);
        loser->setHp(0);
        bool armed = false;
        bool callbackUsed = false;
        int callbacks = 0;
        int metadataCallsAtSetterExit = -1;
        int experienceAtCallback = -1;
        std::shared_ptr<DefeatMetaBarrierItem> constructed;
        auto objects = game->getObjectHandler();
        objects->registerType("AUnitMetadataBarrierItem", [&] {
            auto item = std::make_shared<DefeatMetaBarrierItem>();
            item->setPower(1);
            if (armed && !callbackUsed) {
                callbackUsed = true;
                constructed = item;
                item->metadataCalls = 0;
                item->metadataCallback = [&] {
                    ++callbacks;
                    experienceAtCallback = winner->getExp();
                    if (publication == 0) {
                        game->setMap(map);
                    } else {
                        auto replacement = std::make_shared<CMap>();
                        replacement->setGame(game);
                        game->setMap(replacement);
                        if (publication != 2) {
                            game->setMap(map);
                        }
                    }
                    if (publication == 3) {
                        throw std::runtime_error("unit metadata callback primary failure");
                    }
                };
                try {
                    item->setNumericProperty("unitMetaTarget", 123);
                    metadataCallsAtSetterExit = item->metadataCalls;
                } catch (...) {
                    metadataCallsAtSetterExit = item->metadataCalls;
                    throw;
                }
            }
            return item;
        });
        objects->registerConfig("AUnitMetadataBarrierItem",
                                std::make_shared<json>(json{{"class", "AUnitMetadataBarrierItem"}}));
        expect_true(objects->getConfig("AUnitMetadataBarrierItem") &&
                        objects->getClass("AUnitMetadataBarrierItem") == "AUnitMetadataBarrierItem",
                    "the measured meta callback must be reachable from the actual configured random item table");
        auto rng = game->getRngHandler();
        expect_true(rng && !callbackUsed && callbacks == 0,
                    "warm public prototype enumeration before arming the actual reflected setter callback");
        armed = true;
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        bool cancelled = false;
        bool primary = false;
        expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                    "first-meta controls must finish without a modal or nested event pump");
        if (owner.finished()) {
            try {
                owner.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            } catch (const std::runtime_error &error) {
                primary = std::string(error.what()) == "unit metadata callback primary failure";
            }
        }
        expect_true(constructed && callbacks == 1,
                    "the first real virtual metadata callback must execute once before testing its continuation");
        if (publication == 0) {
            expect_true(!cancelled && !primary && metadataCallsAtSetterExit == 2 &&
                            constructed->getNumericProperty("unitMetaTarget") == 123 &&
                            winner->hasInInventory(constructed) && !map->getObjectByName(loser->getName()) &&
                            map->tryBeginSaveSnapshot().has_value(),
                        "same-pointer metadata callback must preserve the original two-meta setter path and grant");
        } else {
            expect_true(
                cancelled == (publication != 3) && primary == (publication == 3) && metadataCallsAtSetterExit == 1 &&
                    constructed && constructed->getNumericProperty("unitMetaTarget") == 0 &&
                    winner->getItems().empty() && winner->getExp() == experienceAtCallback &&
                    map->getObjectByName(loser->getName()) == loser && !map->tryBeginSaveSnapshot(),
                "first-meta publication must block the second metadata callback and the actual property setter");
        }
        context->shutdown();
    }
    vstd::rng() = previousRng;
}

class DefeatGraphActorCallback : public CCreature {
  public:
    std::function<void()> bindingCallback;
    void setGame(std::shared_ptr<CGame> game) override {
        CGameObject::setGame(std::move(game));
        if (bindingCallback) {
            auto callback = std::move(bindingCallback);
            bindingCallback = {};
            callback();
        }
    }
};

void testOwnedDefeatGraphActorBindingPreservesPrimaryBeforeRootAndProperties() {
    const auto previousRng = vstd::rng();
    for (const int publication : {0, 1, 2, 3}) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto map = game->getMap();
        auto winner = add_test_creature(game, "unitGraphCallbackWinner");
        auto loser = add_test_creature(game, "unitGraphCallbackLoser");
        loser->setLevel(0);
        loser->setSw(1);
        loser->setHp(0);
        bool armed = false;
        bool used = false;
        int callbacks = 0;
        int rootFactories = 0;
        int experienceAtCallback = -1;
        std::shared_ptr<DefeatGraphActorCallback> graphActor;
        auto objects = game->getObjectHandler();
        objects->registerType("AUnitGraphRootItem", [&] {
            if (armed) {
                ++rootFactories;
            }
            auto item = std::make_shared<CItem>();
            item->setPower(1);
            return item;
        });
        objects->registerType("BUnitGraphActorCallback", [&] {
            auto actor = std::make_shared<DefeatGraphActorCallback>();
            if (armed && !used) {
                used = true;
                graphActor = actor;
                actor->bindingCallback = [&] {
                    ++callbacks;
                    experienceAtCallback = winner->getExp();
                    if (publication == 0) {
                        game->setMap(map);
                    } else {
                        auto replacement = std::make_shared<CMap>();
                        replacement->setGame(game);
                        game->setMap(replacement);
                        if (publication != 2) {
                            game->setMap(map);
                        }
                    }
                    if (publication == 3) {
                        throw std::runtime_error("unit graph actor binding primary failure");
                    }
                };
            }
            return actor;
        });
        auto actors = json::array();
        actors[actors.size()] = json{{"class", "BUnitGraphActorCallback"},
                                     {"effectActorId", 1},
                                     {"properties", json{{"unitAfterBinding", 123}}}};
        objects->registerConfig("AUnitGraphRootItem", std::make_shared<json>(json{
                                                          {"class", "AUnitGraphRootItem"},
                                                          {"effectGraph", json{{"version", 1}, {"actors", actors}}}}));
        objects->registerConfig("BUnitGraphActorCallback",
                                std::make_shared<json>(json{{"class", "BUnitGraphActorCallback"}}));
        expect_true(
            objects->getConfig("AUnitGraphRootItem") &&
                objects->getClass("AUnitGraphRootItem") == "AUnitGraphRootItem" &&
                objects->getConfig("BUnitGraphActorCallback") &&
                objects->getClass("BUnitGraphActorCallback") == "BUnitGraphActorCallback",
            "the actual item config must carry a real effectGraph actor definition with a matching constructor");
        auto rng = game->getRngHandler();
        expect_true(rng && !used && callbacks == 0 && rootFactories == 0,
                    "warm public graph/prototype paths before arming the actual detached-actor setGame callback");
        armed = true;
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        bool cancelled = false;
        bool primary = false;
        expect_true(pumpHandlerUntil([&] { return owner.finished(); }),
                    "the effectGraph binding controls must finish without a modal or nested pump");
        if (owner.finished()) {
            try {
                owner.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            } catch (const std::runtime_error &error) {
                primary = std::string(error.what()) == "unit graph actor binding primary failure";
            }
        }
        expect_true(graphActor && callbacks == 1,
                    "the real preallocated actor setGame callback must run once before checking its continuation");
        if (!graphActor) {
            context->shutdown();
            continue;
        }
        if (publication == 0) {
            expect_true(!cancelled && !primary && rootFactories == 1 &&
                            graphActor->getNumericProperty("unitAfterBinding") == 123 &&
                            winner->getItems().size() == 1 && !map->getObjectByName(loser->getName()) &&
                            map->tryBeginSaveSnapshot().has_value(),
                        "same-pointer graph actor setup must retain ordinary graph finalization and defeat completion");
        } else {
            expect_true(
                cancelled == (publication != 3) && primary == (publication == 3) && rootFactories == 0 &&
                    graphActor->getNumericProperty("unitAfterBinding") == 0 && winner->getItems().empty() &&
                    winner->getExp() == experienceAtCallback && map->getObjectByName(loser->getName()) == loser &&
                    !map->tryBeginSaveSnapshot(),
                "graph actor rebind/error must latch before the root constructor, properties and later rewards");
        }
        context->shutdown();
    }
    vstd::rng() = previousRng;
}

bool rejectedDefeat(const vstd::task_handle<void> &call) {
    if (!pumpHandlerUntil([&] { return call.finished(); })) {
        return false;
    }
    try {
        call.get();
    } catch (const std::logic_error &) {
        return true;
    }
    return false;
}

void testDuplicateDefeatRejectsDuringRealLootAndRemoval() {
    auto game = makeWindowlessFightGame();
    auto context = game->getContext();
    auto map = game->getMap();
    map->setBoolProperty("plugin_cityFixedLoot", true);
    auto winner = add_test_player(game);
    auto loser = add_test_creature(game, "unitOwnedDefeatLoser", 1, 0);
    auto item = add_unit_loot(game, loser, "unitOwnedDefeatItem");
    loser->setHp(0);
    auto gate = std::make_shared<AsyncTriggerProbe>();
    map->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
        loser->getName(), "onDestroy", [gate](auto, auto) { return awaitTriggerProbe(gate, "remove"); }));
    auto first = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
    expect_true(pumpHandlerUntil([&] { return game->getGui()->findChild("CGameLootPanel") || first.finished(); }),
                "the owner must reach the real asynchronous reward receipt");
    auto panel = vstd::cast<CGameLootPanel>(game->getGui()->findChild("CGameLootPanel"));
    const auto experience = winner->getExp();
    expect_true(panel && !first.finished() && !map->tryBeginSaveSnapshot(),
                "ordinary-map reward work must own snapshot admission before any observer can resume");
    auto second = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
    expect_true(rejectedDefeat(second) && !first.finished() && winner->getExp() == experience,
                "a duplicate admitted during real loot suspension must reject without another experience grant");
    if (panel) {
        panel->close();
    }
    expect_true(pumpHandlerUntil([&] { return !gate->entered.empty() || first.finished(); }) &&
                    gate->entered.size() == 1 && !first.finished(),
                "the one public owner must await real destruction suspension");
    auto third = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
    expect_true(rejectedDefeat(third) && !first.finished() && !map->tryBeginSaveSnapshot(),
                "a duplicate during removal must reject promptly while the original recovery retains its lease");
    gate->released.insert("remove");
    expect_true(pumpHandlerUntil([&] { return first.finished(); }), "releasing the one receipt must finish its owner");
    if (first.finished()) {
        first.get();
    }
    expect_true(gate->entered.size() == 1 && winner->getExp() == experience && winner->hasInInventory(item) &&
                    winner->countItems("unitOwnedDefeatItem") == 1 && !map->getObjectByName(loser->getName()) &&
                    map->tryBeginSaveSnapshot().has_value(),
                "rejected duplicates must preserve one reward/item/removal and reopen certified snapshot admission");
    context->shutdown();
}

void testConcurrentPlayerDefeatPublishesOnlyRecoveredReceipt() {
    static_assert(std::is_copy_constructible_v<CCustomTrigger>);
    static_assert(std::is_copy_assignable_v<CCustomTrigger>);
    auto game = makeWindowlessFightGame();
    auto map = game->getMap();
    auto context = game->getContext();
    map->setBoolProperty("plugin_cityFixedLoot", true);
    auto winner = add_test_creature(game, "unitOwnedPlayerDefeatWinner", 1, 0);
    auto player = add_test_player(game);
    expect_true(map->getPlayer() == player, "the real player must be canonical before any removal begins");
    auto gate = std::make_shared<AsyncTriggerProbe>();
    std::shared_ptr<CCustomTrigger> registeredRestart;
    for (const auto &trigger : map->getEventHandler()->getTriggers()) {
        if (trigger->getObject() == "player" && trigger->getEvent() == "onDestroy") {
            registeredRestart = std::dynamic_pointer_cast<CCustomTrigger>(trigger);
        }
    }
    expect_true(registeredRestart != nullptr, "the recovery regression requires the actual native restart callback");
    if (!registeredRestart) {
        context->shutdown();
        return;
    }
    auto nativeRestart = std::make_shared<CCustomTrigger>(*registeredRestart);
    // Replace the callback in its existing registry slot; no second native restart is registered.
    *registeredRestart =
        CCustomTrigger("player", "onDestroy", [gate, nativeRestart](auto object, auto event) -> vstd::task<void> {
            co_await awaitTriggerProbe(gate, "beforeRecovery");
            co_await nativeRestart->triggerAsync(object, event);
        });
    registeredRestart->setName("unitOwnedRestartWrapper");
    player->setHp(-500);
    auto item = add_unit_loot(game, player, "unitOwnedPlayerLoss");
    auto first = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, player));
    auto second = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, player));
    expect_true(rejectedDefeat(second) &&
                    pumpHandlerUntil([&] { return !gate->entered.empty() || first.finished(); }) &&
                    gate->entered.size() == 1 && !first.finished() && player->getHp() == -500 &&
                    player->getStringProperty("uiDefeatReceipt").empty(),
                "two admissions across real reward/removal awaits must publish no receipt before recovery");
    gate->released.insert("beforeRecovery");
    expect_true(pumpHandlerUntil([&] { return first.finished(); }),
                "the owner must drain actual native player restart");
    if (first.finished()) {
        first.get();
    }
    const auto receipt = json::parse(player->getStringProperty("uiDefeatReceipt"));
    expect_true(player->getHp() == 1 && player->getCoords() == map->getEntry() &&
                    receipt.at("hp").is_number_integer() && receipt.at("hp").get<int>() == 1 &&
                    receipt.at("lostItemCount").get<int>() == 1 && gate->entered.size() == 1 &&
                    winner->hasInInventory(item),
                "the sole stored receipt must describe completed recovery and original inventory loss");
    const auto stable = player->getStringProperty("uiDefeatReceipt");
    game_async::wait(context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, player)),
                     game_async::WaitMode::PostedWork);
    expect_true(player->getStringProperty("uiDefeatReceipt") == stable,
                "a late call after revival must not replace the completed receipt");
    context->shutdown();
}

void testDefeatCancellationAndFailureDrainOwnedRecovery() {
    for (const bool optedIn : {false, true}) {
        for (const int mode : {0, 1, 2, 3}) {
            auto game = makeWindowlessFightGame();
            auto context = game->getContext();
            auto map = game->getMap();
            map->setBoolProperty("plugin_cityFixedLoot", true);
            map->setBoolProperty("guardNativeEncounterSaves", optedIn);
            auto winner = add_test_player(game);
            auto loser = add_test_creature(game, "unitOwnedCancelLoser", 1, 0);
            auto item = add_unit_loot(game, loser, "unitOwnedCancelItem");
            loser->setHp(0);
            auto gate = std::make_shared<AsyncTriggerProbe>();
            map->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
                loser->getName(), "onDestroy", [gate, mode](auto, auto) -> vstd::task<void> {
                    co_await awaitTriggerProbe(gate, "cleanup");
                    if (mode == 2) {
                        throw std::runtime_error("unit owned destruction failure");
                    }
                }));
            auto first = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
            expect_true(
                pumpHandlerUntil([&] { return game->getGui()->findChild("CGameLootPanel") || first.finished(); }),
                "cancellation controls must enter the actual owner loot receipt");
            const auto experience = winner->getExp();
            expect_true(rejectedDefeat(context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser))),
                        "a duplicate must reject independently of opt-in save policy");
            if (mode == 1) {
                first.requestStop();
            } else if (auto panel = vstd::cast<CGameLootPanel>(game->getGui()->findChild("CGameLootPanel"))) {
                panel->close();
            }
            expect_true(pumpHandlerUntil([&] { return !gate->entered.empty() || first.finished(); }) &&
                            gate->entered.size() == 1 && !first.finished() && !map->tryBeginSaveSnapshot(),
                        "cancelled loot must retain native admission through mandatory removal cleanup");
            if (mode == 3) {
                context->advanceTransitionGeneration();
            }
            gate->released.insert("cleanup");
            expect_true(pumpHandlerUntil([&] { return first.finished(); }),
                        "cleanup must unwind before owner completion");
            bool cancelled = false;
            bool failed = false;
            if (first.finished()) {
                try {
                    first.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                } catch (const std::runtime_error &error) {
                    failed = std::string(error.what()) == "unit owned destruction failure";
                }
            }
            expect_true(
                cancelled == (mode == 1 || mode == 3) && failed == (mode == 2) && winner->hasInInventory(item) &&
                    winner->countItems("unitOwnedCancelItem") == 1 && winner->getExp() == experience &&
                    gate->entered.size() == 1 && map->tryBeginSaveSnapshot().has_value() == (mode < 2),
                "original failure/cancellation must preserve one reward and quarantine only uncertified cleanup");
            if (mode >= 2) {
                loser->setBoolProperty("defeatResolutionUncertain", false);
                expect_true(rejectedDefeat(context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser))) &&
                                winner->getExp() == experience && !map->tryBeginSaveSnapshot(),
                            "a caller property write cannot clear native uncertainty or replay rewards");
            }
            context->shutdown();
        }
    }
}

void testRecursiveDefeatRejectsBeforeItsOwnRecovery() {
    for (const bool propagate : {false, true}) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        map->setBoolProperty("plugin_cityFixedLoot", true);
        auto winner = add_test_creature(game, "unitRecursiveDefeatWinner");
        auto loser = add_test_creature(game, "unitRecursiveDefeatLoser", 1, 0);
        loser->setHp(0);
        int rejected = 0;
        map->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
            loser->getName(), "onDestroy", [winner, loser, &rejected, propagate](auto, auto) -> vstd::task<void> {
                try {
                    co_await CFightHandler::defeatedCreatureAsync(winner, loser);
                } catch (const std::logic_error &) {
                    ++rejected;
                    if (propagate) {
                        throw;
                    }
                }
            }));
        auto owner = game->getContext()->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        expect_true(pumpHandlerUntil([&] { return owner.finished(); }) && rejected == 1,
                    "an awaited destruction descendant must reject recursive finalization without a self-join");
        bool propagated = false;
        if (owner.finished()) {
            try {
                owner.get();
            } catch (const std::logic_error &error) {
                propagated = std::string(error.what()) == "defeat recovery already owns a participant";
            }
        }
        expect_true(propagated == propagate && map->tryBeginSaveSnapshot().has_value() == !propagate,
                    "a propagated callback rejection must preserve the original failure and quarantine started work");
        game->getContext()->shutdown();
    }
}

class ReentrantEncounterController : public NoProgressFightController {
  public:
    std::function<void()> reenter;
    void start(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> opponent) override {
        NoProgressFightController::start(actor, opponent);
        reenter();
    }
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature> opponent) override {
        reenter();
        opponent->setHp(0);
        return true;
    }
    void end(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> opponent) override {
        NoProgressFightController::end(actor, opponent);
        reenter();
    }
};

void testOverlappingEncounterCannotStartSharedControllers() {
    auto game = makeWindowlessFightGame();
    auto map = game->getMap();
    map->setBoolProperty("plugin_cityFixedLoot", true);
    auto actor = add_test_creature(game, "unitOwnedEncounterActor");
    auto opponent = add_test_creature(game, "unitOwnedEncounterOpponent", 1, 0);
    auto other = add_test_creature(game, "unitRejectedEncounterOpponent", 2, 0);
    auto rejected = std::dynamic_pointer_cast<NoProgressFightController>(other->getFightController());
    auto owner = std::make_shared<ReentrantEncounterController>();
    int rejectedCalls = 0;
    owner->reenter = [&] {
        const auto status = map->getStringProperty("combatStatus");
        const auto history = map->getStringProperty("combatHistory");
        auto duplicate = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(actor, {other}));
        expect_true(duplicate.finished() && duplicate.get().outcome == CFightOutcome::Cancelled &&
                        map->getStringProperty("combatStatus") == status &&
                        map->getStringProperty("combatHistory") == history,
                    "start/action/end reentry must preserve the first encounter's controller and status ownership");
        expect_true(rejectedDefeat(game->getContext()->spawnTask(CFightHandler::defeatedCreatureAsync(actor, other))),
                    "a public callback cannot bypass a private claimed-encounter finalizer");
        ++rejectedCalls;
    };
    actor->setFightController(owner);
    const auto result = CFightHandler::fightManyResult(actor, {opponent});
    expect_true(result.outcome == CFightOutcome::AttackerVictory && rejectedCalls == 3 && owner->start_count == 1 &&
                    owner->end_count == 1 && rejected->start_count == 0 && rejected->end_count == 0,
                "rejected overlap must never adopt or end the first encounter's controllers");
    actor->setFightController(std::make_shared<CancellingFightController>());
    const auto after = CFightHandler::fightManyResult(actor, {other});
    expect_true(after.outcome == CFightOutcome::Cancelled && rejected->start_count == 1 && rejected->end_count == 1,
                "certified cleanup must release claims for a later ordinary encounter");
    game->getContext()->shutdown();
}

void testDefeatAdmissionRefusalAndAbandonedOwnersPreserveBoundaries() {
    auto game = makeWindowlessFightGame();
    auto context = game->getContext();
    auto map = game->getMap();
    map->setBoolProperty("plugin_cityFixedLoot", true);
    auto winner = add_test_creature(game, "unitRefusedDefeatWinner");
    auto loser = add_test_creature(game, "unitRefusedDefeatLoser", 1, 0);
    auto item = add_unit_loot(game, loser, "unitRefusedDefeatItem");
    loser->setHp(0);
    const auto experience = winner->getExp();
    auto snapshot = map->tryBeginSaveSnapshot();
    auto refused = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
    bool refusedCancelled = false;
    if (pumpHandlerUntil([&] { return refused.finished(); })) {
        try {
            refused.get();
        } catch (const vstd::task_cancelled &) {
            refusedCancelled = true;
        }
    }
    expect_true(refusedCancelled && winner->getExp() == experience && loser->hasInInventory(item) &&
                    map->getObjectByName(loser->getName()) == loser,
                "exclusive admission refusal must precede reward, inventory and removal effects");
    snapshot.reset();
    std::promise<vstd::task_handle<void>> queuedOwner;
    std::jthread worker(
        [&] { queuedOwner.set_value(context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser))); });
    auto cancelled = queuedOwner.get_future().get();
    worker.join();
    cancelled.requestStop();
    cancelled = {};
    bool barrier = false;
    vstd::event_loop<>::instance()->invoke([&] { barrier = true; });
    expect_true(pumpHandlerUntil([&] { return barrier; }) && map->tryBeginSaveSnapshot().has_value() &&
                    winner->getExp() == experience && loser->hasInInventory(item),
                "dropping a cancelled worker-posted owner before effects must leave no claim, reward or quarantine");
    context->shutdown();

    auto lootGame = makeWindowlessFightGame();
    auto lootContext = lootGame->getContext();
    auto lootMap = lootGame->getMap();
    lootMap->setBoolProperty("plugin_cityFixedLoot", true);
    auto player = add_test_player(lootGame);
    auto lootLoser = add_test_creature(lootGame, "unitAbandonedLootLoser", 1, 0);
    auto lostItem = add_unit_loot(lootGame, lootLoser, "unitAbandonedLootItem");
    lootLoser->setHp(0);
    auto gate = std::make_shared<AsyncTriggerProbe>();
    lootMap->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
        lootLoser->getName(), "onDestroy", [gate](auto, auto) { return awaitTriggerProbe(gate, "abandonedCleanup"); }));
    auto owner = lootContext->spawnTask(CFightHandler::defeatedCreatureAsync(player, lootLoser));
    expect_true(pumpHandlerUntil([&] { return lootGame->getGui()->findChild("CGameLootPanel"); }),
                "the abandoned owner fixture must enter an actual started reward receipt");
    auto observer = owner;
    owner.requestStop();
    owner = {};
    expect_true(pumpHandlerUntil([&] { return !gate->entered.empty(); }) && !observer.finished() &&
                    !lootMap->tryBeginSaveSnapshot(),
                "dropping the initiating observer must retain the inline owner lease through mandatory cleanup");
    gate->released.insert("abandonedCleanup");
    bool cancelledAfterCleanup = false;
    if (pumpHandlerUntil([&] { return observer.finished(); })) {
        try {
            observer.get();
        } catch (const vstd::task_cancelled &) {
            cancelledAfterCleanup = true;
        }
    }
    std::weak_ptr<CCreature> weakLoser = lootLoser;
    lootLoser.reset();
    expect_true(cancelledAfterCleanup && gate->entered.size() == 1 && player->hasInInventory(lostItem) &&
                    lootMap->tryBeginSaveSnapshot().has_value() && weakLoser.expired(),
                "certified cancellation must release the actor/frame and reopen ordinary-map snapshots");
    lootContext->shutdown();
}

void testFailedOrdinaryDefeatRequiresVerifiedRestore() {
    auto game = load_empty_game();
    auto context = game->getContext();
    auto original = game->getMap();
    original->setMapName("test");
    original->setBoolProperty("plugin_cityFixedLoot", true);
    original->setBoolProperty("guardNativeEncounterSaves", false);
    add_test_player(game);
    auto authored = game->getConfigurationProvider()->getConfiguration("maps/test/map.json");
    expect_true(authored && authored->is_object(), "recovery requires the existing authored test-map resource");
    if (!authored || !authored->is_object()) {
        context->shutdown();
        return;
    }
    const auto slot =
        "defeat-owned-recovery-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    const bool ready = CMapLoader::saveWithResult(original, slot);
    expect_true(ready, "failed-defeat recovery requires a real checkpoint preceding the operation");
    if (!ready) {
        context->shutdown();
        return;
    }
    auto winner = add_test_creature(game, "unitFailedOrdinaryWinner");
    auto loser = add_test_creature(game, "unitFailedOrdinaryLoser", 1, 0);
    loser->setHp(0);
    auto item = add_unit_loot(game, loser, "unitFailedOrdinaryItem");
    original->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
        loser->getName(), "onDestroy", [](auto, auto) { throw std::runtime_error("unit ordinary recovery failure"); }));
    auto failed = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
    bool originalFailure = false;
    if (pumpHandlerUntil([&] { return failed.finished(); })) {
        try {
            failed.get();
        } catch (const std::runtime_error &error) {
            originalFailure = std::string(error.what()) == "unit ordinary recovery failure";
        }
    }
    const auto experience = winner->getExp();
    loser->setBoolProperty("defeatResolutionUncertain", false);
    original->setBoolProperty("guardNativeEncounterSaves", false);
    expect_true(originalFailure && winner->hasInInventory(item) && !original->tryBeginSaveSnapshot(),
                "ordinary-map partial failure must quarantine the captured native session, not a writable property");
    auto manual = std::make_shared<CMap>();
    manual->setGame(game);
    game->setMap(manual);
    expect_true(!manual->tryBeginSaveSnapshot() && winner->getExp() == experience,
                "manual map installation and actor property writes must not clear failed-operation admission");
    CGameLoader::loadSavedGame(game, slot + "-missing");
    expect_true(!game->getMap()->tryBeginSaveSnapshot(), "an unverified failed load must retain quarantine");
    CGameLoader::loadSavedGame(game, slot);
    const bool restored =
        game->getMap() != original && game->getMap() != manual && game->getMap()->tryBeginSaveSnapshot().has_value();
    expect_true(restored && !original->tryBeginSaveSnapshot(),
                "verified installation may reopen the session while the old map stays quarantined");
    if (restored) {
        auto resources = game->getResourcesProvider();
        for (const auto &relative : {CSaveFormat::primaryPath(slot), CSaveFormat::backupPath(slot)}) {
            const auto path = resources->getPath(relative);
            if (!path.empty()) {
                std::filesystem::remove(path);
            }
        }
    }
    context->shutdown();
}

void testDefeatCallbackShutdownKeepsContextTaskAncestry() {
    auto game = makeWindowlessFightGame();
    auto context = game->getContext();
    auto map = game->getMap();
    map->setBoolProperty("plugin_cityFixedLoot", true);
    auto winner = add_test_creature(game, "unitShutdownDefeatWinner");
    auto loser = add_test_creature(game, "unitShutdownDefeatLoser", 1, 0);
    loser->setHp(0);
    bool callbackReturned = false;
    map->getEventHandler()->registerTrigger(
        std::make_shared<CCustomTrigger>(loser->getName(), "onDestroy", [context, &callbackReturned](auto, auto) {
            context->shutdown();
            callbackReturned = true;
        }));
    auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
    bool cancelled = false;
    if (pumpHandlerUntil([&] { return owner.finished(); })) {
        try {
            owner.get();
        } catch (const vstd::task_cancelled &) {
            cancelled = true;
        }
    }
    expect_true(callbackReturned && cancelled && !context->isActive(),
                "actual callback shutdown must retain context ancestry and return without a synchronous self-wait");
}

class ThrowingOwnershipFightController : public NoProgressFightController {
  public:
    int phase = 0;
    void start(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> opponent) override {
        NoProgressFightController::start(actor, opponent);
        if (phase == 0) {
            throw std::runtime_error("unit owned start failure");
        }
    }
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        if (phase == 1) {
            throw std::runtime_error("unit owned action failure");
        }
        return false;
    }
    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return true; }
    void end(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> opponent) override {
        NoProgressFightController::end(actor, opponent);
        if (phase == 2) {
            throw std::runtime_error("unit owned end failure");
        }
    }
};

void testEncounterParticipantClaimsReleaseAfterThrowAndCancel() {
    for (int phase = 0; phase < 4; ++phase) {
        auto game = makeWindowlessFightGame();
        auto actor = add_test_creature(game, "unitThrowingOwnerActor");
        auto opponent = add_test_creature(game, "unitThrowingOwnerOpponent", 1, 0);
        auto controller = std::make_shared<ThrowingOwnershipFightController>();
        controller->phase = phase;
        actor->setFightController(controller);
        auto first = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(actor, {opponent}));
        bool failed = false;
        if (pumpHandlerUntil([&] { return first.finished(); })) {
            try {
                expect_true(first.get().outcome == CFightOutcome::Cancelled,
                            "the non-throwing control must preserve ordinary cancellation");
            } catch (const std::runtime_error &error) {
                const std::string expected[] = {"unit owned start failure", "unit owned action failure",
                                                "unit owned end failure"};
                failed = phase < 3 && std::string(error.what()) == expected[phase];
            }
        }
        expect_true(failed == (phase < 3) && controller->start_count == 1 && controller->end_count == 1,
                    "every entered controller must end once while preserving its primary failure/cancellation");
        auto replacement = std::make_shared<CancellingFightController>();
        actor->setFightController(replacement);
        expect_true(CFightHandler::fightManyResult(actor, {opponent}).outcome == CFightOutcome::Cancelled &&
                        replacement->start_count == 1 && replacement->end_count == 1,
                    "start/action/end failure and cancellation must release claims before the next encounter");
        game->getContext()->shutdown();
    }
}

void testEncounterOwnershipIgnoresSanitizedIneligibleCandidates() {
    auto game = makeWindowlessFightGame();
    auto context = game->getContext();
    auto hero = add_test_player(game);
    hero->setAffiliation("unitHeroSide");
    auto heroController = std::make_shared<CancellingFightController>();
    hero->setFightController(heroController);
    auto enemy = add_test_creature(game, "unitSanitizedEnemy", 1, 0);
    auto candidate = add_test_creature(game, "unitSanitizedCandidate", 2, 0);
    candidate->setAffiliation("unitOtherSide");
    auto candidateEnemy = add_test_creature(game, "unitSanitizedCandidateEnemy", 3, 0);
    auto gate = std::make_shared<AsyncTriggerProbe>();
    auto candidateController = std::make_shared<SuspendedTraceFightController>();
    candidateController->probe = gate;
    candidate->setFightController(candidateController);
    auto independent = context->spawnTask(CFightHandler::fightManyResultAsync(candidate, {candidateEnemy}));
    expect_true(pumpHandlerUntil([&] { return !gate->entered.empty() || independent.finished(); }) &&
                    !independent.finished(),
                "the sanitizer regression must retain one actual independent claimed encounter");
    const auto ignored = CFightHandler::fightManyWithAlliesResult(hero, {enemy}, {candidate});
    expect_true(ignored.outcome == CFightOutcome::Cancelled && heroController->start_count == 1 &&
                    heroController->end_count == 1 && candidateController->start_count == 1 &&
                    candidateController->end_count == 0,
                "an owned but unaffiliated candidate must be filtered before ownership admission");
    candidate->setAffiliation("unitHeroSide");
    const auto genuinelyShared = CFightHandler::fightManyWithAlliesResult(hero, {enemy}, {candidate});
    expect_true(genuinelyShared.outcome == CFightOutcome::Cancelled && heroController->start_count == 1 &&
                    heroController->end_count == 1 && candidateController->end_count == 0,
                "a genuinely admitted shared ally must reject before any new controller callbacks");
    independent.requestStop();
    if (pumpHandlerUntil([&] { return independent.finished(); })) {
        try {
            independent.get();
        } catch (const vstd::task_cancelled &) {
        }
    }
    context->shutdown();
}

void testDefeatRecoveryCertificationRejectsReplacedOrUnfinishedOwners() {
    for (int mode = 0; mode < 7; ++mode) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto context = game->getContext();
        map->setBoolProperty("plugin_cityFixedLoot", true);
        auto winner = add_test_creature(game, "unitCertifiedDefeatWinner", 1, 0);
        std::shared_ptr<CCreature> loser;
        auto gate = std::make_shared<AsyncTriggerProbe>();
        std::shared_ptr<CGame> restartGame;
        std::shared_ptr<CTrigger> nativeRestart;
        if (mode == 3) {
            loser = add_test_creature(game, "unitCertifiedNpcLoser", 2, 0);
            std::weak_ptr<CMap> weakMap = map;
            auto trigger = std::make_shared<CCustomTrigger>(
                loser->getName(), "onDestroy", [gate, weakMap](auto object, auto) -> vstd::task<void> {
                    weakMap.lock()->addObject(std::dynamic_pointer_cast<CMapObject>(object));
                    co_await awaitTriggerProbe(gate, "certify");
                });
            trigger->setName("unitRespawnedNpcWitness");
            map->getEventHandler()->registerTrigger(trigger);
        } else if (mode == 4) {
            map->setPermanentPlayerDeath(true);
            loser = add_test_player(game);
            auto trigger = std::make_shared<CCustomTrigger>(
                "player", "onDestroy", [gate](auto, auto) { return awaitTriggerProbe(gate, "certify"); });
            trigger->setName("unitTerminalOwnerControl");
            map->getEventHandler()->registerTrigger(trigger);
        } else {
            std::shared_ptr<CPlayer> player;
            std::shared_ptr<CCustomTrigger> registeredRestart;
            if (mode == 6) {
                player = std::make_shared<CPlayer>();
                player->setGame(game);
                initialize_test_creature_stats(player);
                player->setName("player");
                map->addObject(player);
                restartGame = makeWindowlessFightGame();
                add_test_player(restartGame);
            } else {
                player = add_test_player(game);
                expect_true(map->getPlayer() == player,
                            "the recovery control requires a canonical player before removal");
            }
            loser = player;
            auto nativeMap = restartGame ? restartGame->getMap() : map;
            for (const auto &trigger : nativeMap->getEventHandler()->getTriggers()) {
                if (trigger->getObject() == "player" && trigger->getEvent() == "onDestroy") {
                    registeredRestart = std::dynamic_pointer_cast<CCustomTrigger>(trigger);
                }
            }
            expect_true(registeredRestart != nullptr,
                        "the certified recovery witness requires the native restart callback");
            if (!registeredRestart) {
                context->shutdown();
                if (restartGame) {
                    restartGame->getContext()->shutdown();
                }
                continue;
            }
            nativeRestart = std::make_shared<CCustomTrigger>(*registeredRestart);
            std::weak_ptr<CMap> weakMap = map;
            auto callback = CCustomTrigger(
                "player", "onDestroy",
                [gate, nativeRestart, weakMap, winner, mode](auto object, auto event) -> vstd::task<void> {
                    auto map = weakMap.lock();
                    if (mode != 2 && mode != 5) {
                        co_await nativeRestart->triggerAsync(object, event);
                    }
                    if (mode == 1) {
                        co_await map->removeObjectAsync(winner);
                        auto replacement = std::make_shared<CCreature>();
                        replacement->setGame(map->getGame());
                        initialize_test_creature_stats(replacement);
                        replacement->setName(winner->getName());
                        replacement->setHp(10);
                        map->addObject(replacement);
                    } else if (mode == 5) {
                        auto replacement = std::make_shared<CPlayer>();
                        replacement->setGame(map->getGame());
                        initialize_test_creature_stats(replacement);
                        replacement->setHp(10);
                        map->setPlayer(replacement);
                    }
                    co_await awaitTriggerProbe(gate, "certify");
                });
            callback.setName("unitCertifiedRecoveryWrapper");
            if (mode == 6) {
                map->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(callback));
            } else {
                *registeredRestart = callback;
            }
        }
        loser->setHp(0);
        auto owner = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, loser));
        expect_true(pumpHandlerUntil([&] { return !gate->entered.empty() || owner.finished(); }) && !owner.finished(),
                    "certification must observe the real asynchronous removal boundary");
        gate->released.insert("certify");
        bool cancelled = false;
        if (pumpHandlerUntil([&] { return owner.finished(); })) {
            try {
                owner.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        const bool healthy = mode == 0 || mode == 4;
        expect_true(cancelled == !healthy && map->tryBeginSaveSnapshot().has_value() == healthy,
                    "removed/replaced winner, unfinished restart, resurrected NPC, replaced or uncached player must "
                    "not certify");
        if (!healthy && loser->isPlayer()) {
            expect_true(loser->getStringProperty("uiDefeatReceipt").empty(),
                        "an uncertified player recovery must not publish a stored recovery receipt");
        }
        if (mode == 0) {
            expect_true(loser->getHp() == 1 && map->getObjectByName("player") == loser,
                        "the ordinary native restart remains a healthy certified control");
        } else if (mode == 4) {
            expect_true(!loser->isAlive() && map->getDefeatedPlayer() == loser && !map->getObjectByName("player"),
                        "the exact retained dead permanent player remains a healthy terminal control");
        }
        context->shutdown();
        if (restartGame) {
            restartGame->getContext()->shutdown();
        }
    }
}

class DefeatEndAdmissionController : public KillingFightController {
  public:
    std::function<void()> onStart;
    std::function<void()> onEnd;
    void start(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> opponent) override {
        KillingFightController::start(actor, opponent);
        onStart();
    }
    void end(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> opponent) override {
        KillingFightController::end(actor, opponent);
        onEnd();
    }
};

void testInternalDefeatLeaseSurvivesParentControllerCleanup() {
    for (const bool optedIn : {false, true}) {
        for (const bool failEnd : {false, true}) {
            auto game = makeWindowlessFightGame();
            auto map = game->getMap();
            map->setBoolProperty("plugin_cityFixedLoot", true);
            map->setBoolProperty("guardNativeEncounterSaves", optedIn);
            auto winner = add_test_creature(game, "unitEndLeaseWinner");
            auto loser = add_test_creature(game, "unitEndLeaseLoser", 1, 0);
            auto controller = std::make_shared<DefeatEndAdmissionController>();
            bool startSaveAllowed = false;
            bool endSaveAllowed = true;
            controller->onStart = [&] { startSaveAllowed = map->tryBeginSaveSnapshot().has_value(); };
            controller->onEnd = [&] {
                endSaveAllowed = map->tryBeginSaveSnapshot().has_value();
                if (failEnd) {
                    throw std::runtime_error("unit post-defeat end failure");
                }
            };
            winner->setFightController(controller);
            auto encounter = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(winner, {loser}));
            bool originalFailure = false;
            if (pumpHandlerUntil([&] { return encounter.finished(); })) {
                try {
                    expect_true(encounter.get().outcome == CFightOutcome::AttackerVictory,
                                "the non-throwing encounter must keep its ordinary victory result");
                } catch (const std::runtime_error &error) {
                    originalFailure = std::string(error.what()) == "unit post-defeat end failure";
                }
            }
            expect_true(startSaveAllowed == !optedIn && !endSaveAllowed && originalFailure == failEnd &&
                            controller->start_count == 1 && controller->end_count == 1 &&
                            map->tryBeginSaveSnapshot().has_value() == !failEnd,
                        "healthy start timing stays opt-in, but an actual defeat lease must cover every end callback");
            game->getContext()->shutdown();
        }
    }
}

void testAsyncCombatAwaitsLootWithoutPumpingOrGrantingRewardsEarly() {
    auto loop = vstd::event_loop<>::instance();
    auto game = makeWindowlessFightGame();
    auto map = game->getMap();
    auto player = add_test_player(game);
    auto controller = std::make_shared<KillingFightController>();
    player->setFightController(controller);
    auto defeated = add_test_creature(game, "unitAsyncLootDefeated", 1, 0);
    auto item = add_unit_loot(game, defeated, "unitAsyncOwnedReward");
    const auto turn = map->getTurn();
    const auto exp = player->getExp();
    auto queuedCallbackRan = std::make_shared<bool>(false);
    std::weak_ptr<CGui> weakGui = game->getGui();
    auto legacyDismissal = loop->connectFrameCallback([weakGui](int) {
        if (auto gui = weakGui.lock()) {
            if (auto panel = vstd::cast<CGameLootPanel>(gui->findChild("CGameLootPanel"))) {
                panel->close();
            }
        }
    });
    loop->invoke([queuedCallbackRan] { *queuedCallbackRan = true; });
    auto waiting = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(player, {defeated}));
    expect_true(!*queuedCallbackRan && !waiting.finished(),
                "native combat must return without pumping unrelated queued work");
    expect_true(pumpHandlerUntil([&] { return game->getGui()->findChild("CGameLootPanel") || waiting.finished(); }),
                "the outer loop must reach combat's loot receipt");
    auto panel = vstd::cast<CGameLootPanel>(game->getGui()->findChild("CGameLootPanel"));
    expect_true(panel && !waiting.finished(), "combat must await dismissal of its loot panel");
    expect_true(
        player->getExp() > exp && !player->hasInInventory(item) &&
            map->getObjectByName(defeated->getName()) == defeated && map->getTurn() == turn,
        "loot presentation must retain experience timing while delaying item grant and removal until dismissal");
    if (panel) {
        expect_true(panel->getItems().contains(item), "the suspended loot panel must own the exact dropped item");
        panel->close();
    }
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while ((!waiting.finished() || !*queuedCallbackRan) && std::chrono::steady_clock::now() < deadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(waiting.finished(), "closing loot must let the combat coroutine finish");
    if (waiting.finished()) {
        const auto result = waiting.get();
        expect_true(result.outcome == CFightOutcome::AttackerVictory && result.rounds == 1,
                    "asynchronous loot dismissal must preserve the resolved combat result");
    }
    expect_true(
        *queuedCallbackRan && player->hasInInventory(item) && player->countItems("unitAsyncOwnedReward") == 1 &&
            map->getObjectByName(defeated->getName()) == nullptr && map->getTurn() == turn,
        "loot dismissal must grant the original item exactly once and remove the loser without advancing a turn");
    expect_controller_lifecycle(controller, 1, 1, "asynchronous reward completion must end its controller once");
    game->getContext()->shutdown();
}

void testWorkerStartedCombatDefersControllerAndPanelCreationToMain() {
    auto loop = vstd::event_loop<>::instance();
    const auto mainThread = std::this_thread::get_id();
    auto game = makeWindowlessFightGame();
    auto probe = std::make_shared<FightThreadProbe>();
    game->getObjectHandler()->registerType("CGameFightPanel", [probe] {
        probe->panelCreatedOn = std::this_thread::get_id();
        probe->panels.fetch_add(1, std::memory_order_release);
        return std::make_shared<CGameFightPanel>();
    });
    auto player = add_test_player(game);
    player->setFightController(std::make_shared<ThreadCheckedPlayerFightController>(probe));
    auto defender = add_test_creature(game, "unitWorkerCombatDefender", 1, 0);
    auto outcome = std::make_shared<std::promise<vstd::task_handle<CFightResult>>>();
    auto future = outcome->get_future();
    const bool submitted = game_async::workerPool()->submit([context = game->getContext(), player, defender, outcome] {
        pybind11::gil_scoped_acquire acquire;
        try {
            outcome->set_value(context->spawnTask(CFightHandler::fightManyResultAsync(player, {defender})));
        } catch (...) {
            outcome->set_exception(std::current_exception());
        }
    });
    std::future_status status;
    {
        pybind11::gil_scoped_release release;
        status = future.wait_for(std::chrono::seconds(2));
    }
    expect_true(submitted && status == std::future_status::ready, "the worker must start and suspend its combat task");
    if (!submitted || status != std::future_status::ready) {
        return;
    }
    auto waiting = future.get();
    expect_true(probe->starts.load(std::memory_order_acquire) == 0 &&
                    probe->panels.load(std::memory_order_acquire) == 0,
                "worker-started combat must defer controller start and GUI creation until the main loop runs");
    const auto openedDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while ((probe->starts.load(std::memory_order_acquire) == 0 || probe->panels.load(std::memory_order_acquire) == 0) &&
           !waiting.finished() && std::chrono::steady_clock::now() < openedDeadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(probe->starts.load(std::memory_order_acquire) == 1 && probe->startedOn == mainThread &&
                    probe->panels.load(std::memory_order_acquire) == 1 && probe->panelCreatedOn == mainThread,
                "the main thread must start combat controllers and construct their fight panel");
    if (auto panel = vstd::cast<CGameFightPanel>(game->getGui()->findChild("CGameFightPanel"))) {
        panel->close();
    }
    const auto closedDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (!waiting.finished() && std::chrono::steady_clock::now() < closedDeadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(waiting.finished() && waiting.get().outcome == CFightOutcome::Cancelled,
                "closing the worker-requested fight panel must finish combat as cancelled");
    expect_true(game->getGui()->getChildren().empty(), "cancelled worker-started combat must leave no fight panel");
    game->getContext()->shutdown();
}

class OwnedLootCompensationObserver : public CGameObject {
    V_META(OwnedLootCompensationObserver, CGameObject, V_METHOD(OwnedLootCompensationObserver, onInventoryChanged))

  public:
    std::function<void()> callback;
    void onInventoryChanged() {
        if (callback) {
            auto action = std::move(callback);
            callback = {};
            action();
        }
    }
};

void testOwnedLootCancellationCompensationRetainsExactItemsAndRejectsUncertainReplay() {
    CTypes::register_type_metadata<OwnedLootCompensationObserver, CGameObject>();
    auto loop = vstd::event_loop<>::instance();
    {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto player = add_test_player(game);
        auto originalFight = std::make_shared<KillingFightController>();
        player->setFightController(originalFight);
        const auto detached = map->detachPlayer();
        map->addObject(player);
        expect_true(detached == player && !map->getAssignedPlayer() && map->getObjectByName("player") == player,
                    "the positive cache-repair control must begin with a genuinely registered uncached player");
        const auto restored = map->getPlayer();
        expect_true(restored == player && map->getAssignedPlayer() == player &&
                        player->getFightController() != originalFight &&
                        std::dynamic_pointer_cast<CPlayerFightController>(player->getFightController()) != nullptr,
                    "an explicit active getPlayer must demonstrate actual native controller and cache restoration");
        game->getContext()->shutdown();
    }
    for (int mode = 0; mode != 12; ++mode) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto context = game->getContext();
        map->setBoolProperty("plugin_cityFixedLoot", true);
        auto player = add_test_player(game);
        player->setFightController(std::make_shared<KillingFightController>());
        auto loser = add_test_creature(game, "unitCompensatedLoser", 1, 0);
        std::set<std::shared_ptr<CItem>> owned;
        for (int index = 0; index != 2; ++index) {
            auto item = std::make_shared<CItem>();
            item->setGame(game);
            item->setName("unitCompensatedItem" + std::to_string(index));
            item->setTypeId(item->getName());
            loser->addItem(item);
            owned.insert(item);
        }
        auto first = *owned.begin();
        auto second = *owned.rbegin();
        auto destroyed = std::make_shared<int>(0);
        map->getEventHandler()->registerTrigger(
            std::make_shared<CCustomTrigger>(loser->getName(), "onDestroy", [destroyed](auto, auto) { ++*destroyed; }));
        auto waiting = context->spawnTask(CFightHandler::fightManyResultAsync(player, {loser}));
        const bool pending =
            pumpHandlerUntil([&] { return game->getGui()->findChild("CGameLootPanel") || waiting.finished(); }) &&
            game->getGui()->findChild("CGameLootPanel");
        expect_true(pending && !waiting.finished() && !player->hasInInventory(first) && !player->hasInInventory(second),
                    "compensation controls must suspend after exact possession removal and before any grant");
        if (!pending || waiting.finished()) {
            context->shutdown();
            continue;
        }
        const auto experience = player->getExp();
        const auto epoch = game->getMapBindingEpoch();
        const auto generation = context->getTransitionGeneration();
        auto callbackCount = std::make_shared<int>(0);
        auto callbackSawBothItems = std::make_shared<bool>(false);
        auto observer = std::make_shared<OwnedLootCompensationObserver>();
        observer->setGame(game);
        std::shared_ptr<CGame> otherGame;
        if (mode >= 7 && mode <= 9) {
            otherGame = std::make_shared<CGame>();
            observer->callback = [mode, callbackCount, callbackSawBothItems, otherGame, destroyed,
                                  weakGame = std::weak_ptr<CGame>(game), weakMap = std::weak_ptr<CMap>(map),
                                  weakPlayer = std::weak_ptr<CPlayer>(player),
                                  weakLoser = std::weak_ptr<CCreature>(loser), weakFirst = std::weak_ptr<CItem>(first),
                                  weakSecond = std::weak_ptr<CItem>(second)] {
                ++*callbackCount;
                auto game = weakGame.lock();
                auto map = weakMap.lock();
                auto player = weakPlayer.lock();
                auto loser = weakLoser.lock();
                auto first = weakFirst.lock();
                auto second = weakSecond.lock();
                if (!game || !map || !player || !loser || !first || !second) {
                    throw std::runtime_error("unit compensation observer lost its captured objects");
                }
                *callbackSawBothItems = player->hasInInventory(first) && player->hasInInventory(second) &&
                                        map->getObjectByName(loser->getName()) == loser && *destroyed == 0;
                if (mode == 7) {
                    player->removeItem(first);
                    throw std::runtime_error("unit deferred inventory observer failure after removal");
                } else if (mode == 8) {
                    player->setGame(otherGame);
                } else {
                    auto replacement = std::make_shared<CMap>();
                    replacement->setGame(game);
                    game->setMap(replacement);
                    game->setMap(map);
                }
            };
            player->connect("inventoryChanged", observer, "onInventoryChanged");
        }
        const auto movement = player->getController();
        const auto fight = player->getFightController();
        const auto triggers = map->getEventHandler()->getTriggers();
        const auto objects = map->getObjects();
        if (mode == 2) {
            game->setMap(map);
        } else if (mode == 3 || mode == 4) {
            auto replacement = std::make_shared<CMap>();
            replacement->setGame(game);
            game->setMap(replacement);
            if (mode == 3) {
                game->setMap(map);
            }
        } else if (mode == 5) {
            context->advanceTransitionGeneration();
        } else if (mode == 6) {
            otherGame = std::make_shared<CGame>();
            player->setGame(otherGame);
        } else if (mode >= 10) {
            const auto detached = map->detachPlayer();
            map->addObject(player);
            expect_true(detached == player && !map->getAssignedPlayer() && map->getObjectByName("player") == player,
                        "the closed cache control must retain the exact registered recipient with no assigned cache");
            if (mode == 11) {
                auto terminalAlias = std::make_shared<CPlayer>();
                terminalAlias->setGame(game);
                terminalAlias->setName("unitMalformedTerminalAlias");
                terminalAlias->setHp(0);
                map->setPermanentPlayerDeath(true);
                map->setDefeatedPlayer(terminalAlias);
                expect_true(map->getPermanentPlayerDeath() && !map->getAssignedPlayer() &&
                                map->getObjectByName("player") == player && terminalAlias != player &&
                                map->getDefeatedPlayer() == terminalAlias,
                            "the second null-cache control is a malformed public terminal alias, not a valid save");
            }
        }
        if (mode >= 10) {
            CPlaytestTrace::configure(true, "", 100, true);
        }
        if ((mode >= 1 && mode <= 6) || mode >= 10) {
            context->shutdown();
        } else {
            waiting.requestStop();
        }
        const bool finished = pumpHandlerUntil([&] { return waiting.finished(); });
        bool cancelled = false;
        bool unexpected = false;
        if (finished) {
            try {
                waiting.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            } catch (...) {
                unexpected = true;
            }
        }
        CPlaytestTrace::configure(false);
        const bool ownsFirst = player->hasInInventory(first);
        const bool ownsSecond = player->hasInInventory(second);
        const bool healthy = mode <= 2;
        std::cout << "owned loot compensation: mode=" << mode << " finished=" << finished << " cancelled=" << cancelled
                  << " unexpected=" << unexpected << " first=" << ownsFirst << " second=" << ownsSecond
                  << " callbacks=" << *callbackCount << " destroyed=" << *destroyed
                  << " epochDelta=" << game->getMapBindingEpoch() - epoch
                  << " generationDelta=" << context->getTransitionGeneration() - generation << '\n';
        expect_true(finished && cancelled && !unexpected && player->getExp() == experience,
                    "all compensation paths must retain the original cancellation and never repeat experience");
        expect_true(ownsFirst == (healthy || mode == 8 || mode == 9) &&
                        ownsSecond == (healthy || (mode >= 7 && mode <= 9)),
                    "only certified owners may settle exact items; an uncertain grant must never be replayed");
        const bool callbackMode = mode >= 7 && mode <= 9;
        expect_true(*callbackCount == (callbackMode ? 1 : 0) && (!callbackMode || *callbackSawBothItems),
                    "the queued observer must execute once after both exact grants but before loser removal");
        expect_true(*destroyed == (mode == 0 ? 1 : 0),
                    "shutdown, invalid ownership and failed grant compensation must not continue loser cleanup");
        if (mode >= 10) {
            expect_true(!map->getAssignedPlayer() && player->getController() == movement &&
                            player->getFightController() == fight && map->getObjects() == objects &&
                            map->getEventHandler()->getTriggers() == triggers,
                        "closed compensation must preserve the absent cache and exact controllers, registry and hooks");
        }
        if (!healthy || mode == 1 || mode == 2) {
            expect_true(!map->tryBeginSaveSnapshot(),
                        "started uncertain or inactive recovery must not admit an unverified snapshot");
        }
        waiting.requestStop();
        loop->runReady();
        expect_true(player->hasInInventory(first) == ownsFirst && player->hasInInventory(second) == ownsSecond &&
                        player->getExp() == experience && *destroyed == (mode == 0 ? 1 : 0),
                    "a repeated stop must not regrant a removed item or replay recovery effects");
        player->disconnect("inventoryChanged", observer, "onInventoryChanged");
        context->shutdown();
    }
}

void testCancelledLootSettlesStartedRewardsOnceAndSkipsQueuedCombat() {
    auto loop = vstd::event_loop<>::instance();
    for (const bool shutdown : {false, true}) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto context = game->getContext();
        auto player = add_test_player(game);
        player->setFightController(std::make_shared<KillingFightController>());
        auto defeated = add_test_creature(game, "unitCancelledLootDefeated", 1, 0);
        auto item = add_unit_loot(game, defeated, "unitCancelledOwnedReward");
        auto destroyed = std::make_shared<int>(0);
        map->getEventHandler()->registerTrigger(std::make_shared<CCustomTrigger>(
            defeated->getName(), CGameEvent::CType::onDestroy, [destroyed](auto, auto) { ++*destroyed; }));
        auto waiting = context->spawnTask(CFightHandler::fightManyResultAsync(player, {defeated}));
        expect_true(
            pumpHandlerUntil([&] { return game->getGui()->findChild("CGameLootPanel") || waiting.finished(); }) &&
                game->getGui()->findChild("CGameLootPanel"),
            "the outer loop must reach started loot before testing its cancellation settlement");
        const auto expAfterDefeat = player->getExp();
        expect_true(!waiting.finished() && !player->hasInInventory(item),
                    "reward cancellation regression must suspend before inventory settlement");
        if (shutdown) {
            context->shutdown();
        } else {
            waiting.requestStop();
        }
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while (!waiting.finished() && std::chrono::steady_clock::now() < deadline) {
            loop->runReady();
            game_async::waitForProgress();
        }
        bool cancelled = false;
        if (waiting.finished()) {
            try {
                waiting.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        expect_true(cancelled && player->hasInInventory(item) && player->countItems("unitCancelledOwnedReward") == 1 &&
                        player->getExp() == expAfterDefeat,
                    "cancelling started loot must settle the exact item once without duplicating experience");
        if (shutdown) {
            expect_true(!context->isActive() && *destroyed == 0,
                        "inactive-session reward cleanup must not invoke destruction hooks or reacquire services");
        } else {
            expect_true(context->isActive() && map->getObjectByName(defeated->getName()) == nullptr &&
                            *destroyed == 1 && game->getGui()->getChildren().empty(),
                        "individual cancellation must remove the loser and modal before finishing cleanup");
        }
        waiting.requestStop();
        loop->runReady();
        expect_true(player->countItems("unitCancelledOwnedReward") == 1 && player->getExp() == expAfterDefeat,
                    "repeated cancellation must not repeat reward settlement");
        context->shutdown();
    }

    {
        auto game = makeWindowlessFightGame();
        auto gui = game->getGui();
        game->getObjectHandler()->registerType("CGameTextPanel", [] { return std::make_shared<CGameTextPanel>(); });
        game->getObjectHandler()->registerConfig("textPanel",
                                                 std::make_shared<json>(json{{"class", "CGameTextPanel"}}));
        auto player = add_test_player(game);
        player->setFightController(std::make_shared<KillingFightController>());
        auto defeated = add_test_creature(game, "unitCancelledCleanupReceipt", 1, 0);
        auto item = add_unit_loot(game, defeated, "unitCancelledCleanupReward");
        int destroyed = 0;
        auto trigger = std::make_shared<CCustomTrigger>(
            defeated->getName(), "onDestroy",
            [&destroyed, weakGui = std::weak_ptr<CGuiHandler>(game->getGuiHandler())](auto, auto) {
                ++destroyed;
                return weakGui.lock()->showMessageAsync("Mandatory destruction receipt");
            });
        trigger->setName("unitCancelledCleanupReceiptTrigger");
        game->getMap()->getEventHandler()->registerTrigger(trigger);
        auto waiting = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(player, {defeated}));
        expect_true(pumpHandlerUntil([&] { return gui->findChild("CGameLootPanel"); }),
                    "the cleanup regression must reach the original loot receipt");
        waiting.requestStop();
        expect_true(pumpHandlerUntil([&] { return gui->findChild("CGameTextPanel") || waiting.finished(); }) &&
                        !waiting.finished() && destroyed == 1 && player->hasInInventory(item),
                    "individual cancellation must drain mandatory destruction after settling the original reward");
        game->getContext()->shutdown();
        expect_true(pumpHandlerUntil([&] { return waiting.finished(); }) && gui->getChildren().empty() &&
                        player->countItems("unitCancelledCleanupReward") == 1,
                    "context shutdown must cancel a suspended mandatory cleanup receipt without hanging execution");
        bool cancelled = false;
        if (waiting.finished()) {
            try {
                waiting.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        expect_true(cancelled, "mandatory cleanup must preserve the original combat cancellation");
    }

    auto game = makeWindowlessFightGame();
    auto player = add_test_player(game);
    player->setFightController(std::make_shared<KillingFightController>());
    auto defender = add_test_creature(game, "unitQueuedCombatDefender", 1, 0);
    auto item = add_unit_loot(game, defender, "unitQueuedCombatReward");
    const auto exp = player->getExp();
    auto queuedTask = [](std::shared_ptr<CPlayer> player,
                         std::shared_ptr<CCreature> defender) -> vstd::task<CFightResult> {
        co_await vstd::post(vstd::event_loop<>::instance());
        std::vector<std::shared_ptr<CCreature>> opponents{std::move(defender)};
        co_return co_await CFightHandler::fightManyResultAsync(player, std::move(opponents));
    }(player, defender);
    auto queued = game->getContext()->spawnTask(std::move(queuedTask));
    queued.requestStop();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (!queued.finished() && std::chrono::steady_clock::now() < deadline) {
        loop->runReady();
        game_async::waitForProgress();
    }
    expect_true(queued.finished() && player->getExp() == exp && defender->isAlive() && defender->hasInInventory(item) &&
                    !player->hasInInventory(item) && game->getGui()->getChildren().empty(),
                "cancelling queued combat must skip all controller, defeat, reward, and GUI work");
    game->getContext()->shutdown();
}

class SceneRequestFightController : public NoProgressFightController {
  public:
    std::function<void()> action;
    std::function<void()> cleanup;
    int actions = 0;

    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature> opponent) override {
        ++actions;
        action();
        opponent->setHp(0);
        return true;
    }

    void end(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) override {
        NoProgressFightController::end(first, second);
        if (cleanup) {
            cleanup();
        }
    }
};

void testQueuedSceneTransitionWaitsForOwnedDefeatAndControllerCleanup() {
    auto loop = vstd::event_loop<>::instance();
    for (int repetition = 0; repetition < 8; ++repetition) {
        auto game = makeWindowlessFightGame();
        const auto source = game->getMap();
        source->setMapName("unitCombatTransitionSource");
        source->setTurn(34);
        source->setBoolProperty("plugin_cityFixedLoot", true);
        const auto player = add_test_player(game);
        const auto destination = std::make_shared<CMap>();
        destination->setGame(game);
        destination->setMapName("unitCombatTransitionDestination");
        game->getContext()->getMapSessionStore()->put(destination);
        const auto scene = game->getSceneManager();
        auto attacker = add_test_creature(game, "unitSceneCombatAttacker", 2, 0);
        auto defender = add_test_creature(game, "unitSceneCombatDefender", 3, 0);
        auto outsider = add_test_creature(game, "unitSceneCombatOutsider", 4, 0);
        auto outsiderController = std::dynamic_pointer_cast<NoProgressFightController>(outsider->getFightController());
        attacker->getBaseStats()->setAgility(50);
        defender->getBaseStats()->setAgility(1);
        auto controller = std::make_shared<SceneRequestFightController>();
        attacker->setFightController(controller);
        auto probe = std::make_shared<AsyncTriggerProbe>();
        auto trigger = std::make_shared<CCustomTrigger>(
            defender->getName(), "onDestroy", [probe](auto, auto) { return awaitTriggerProbe(probe, "destroy"); });
        trigger->setName("unitSceneCombatDestroyGate");
        source->getEventHandler()->registerTrigger(trigger);
        int preparation = 0;
        int finished = 0;
        bool committed = false;
        controller->action = [&] {
            CMapTransitionRequest request;
            request.targetMap = destination->getMapName();
            request.reuseLoadedMap = true;
            request.beforePlayerEntry = [&] {
                ++preparation;
                expect_true(controller->end_count == 1 && probe->released.contains("destroy") &&
                                !source->getObjectByName(defender->getName()),
                            "queued commit must follow actual destruction and controller cleanup");
            };
            request.onFinished = [&](bool success) {
                ++finished;
                committed = success;
            };
            expect_true(scene->requestMapChange(game, std::move(request)) && game->getMap() == source &&
                            scene->getTransitionStateName() == "TransitionPending",
                        "controller transition request must remain queued on the source");
            auto overlap = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(outsider, {defender}));
            expect_true(overlap.finished() && overlap.get().outcome == CFightOutcome::Cancelled &&
                            controller->actions == 1 && outsiderController->start_count == 0 &&
                            outsiderController->end_count == 0,
                        "rejected shared-participant reentry must not retain another map deferral");
        };
        controller->cleanup = [&] {
            for (int pump = 0; pump < 4; ++pump) {
                loop->runReady();
            }
            expect_true(game->getMap() == source && preparation == 0 && finished == 0,
                        "controller end callbacks must retain the encounter's map deferral");
        };
        auto fight = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(attacker, {defender}));
        expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || fight.finished(); }) &&
                        probe->entered.size() == 1 && !fight.finished(),
                    "the native regression must reach a real suspended destruction hook");
        for (int pump = 0; pump < 16; ++pump) {
            loop->runReady();
        }
        expect_true(game->getMap() == source && preparation == 0 && finished == 0 && !defender->isAlive(),
                    "queued scene work must not interrupt the unfinished owned defeat");
        probe->released.insert("destroy");
        expect_true(pumpHandlerUntil([&] { return fight.finished(); }), "the owned defeat must settle boundedly");
        if (fight.finished()) {
            const auto result = fight.get();
            expect_true(result.outcome == CFightOutcome::AttackerVictory && controller->actions == 1 &&
                            controller->start_count == 1 && controller->end_count == 1 &&
                            source->getObjectByName(attacker->getName()) == attacker &&
                            !source->getObjectByName(defender->getName()),
                        "the unchanged combat victory and exact removal must survive the queued transition");
        }
        expect_true(pumpHandlerUntil([&] { return !scene->isTransitionPending(); }) && game->getMap() == destination &&
                        destination->getAssignedPlayer() == player && destination->getTurn() == 34 &&
                        preparation == 1 && finished == 1 && committed &&
                        source->getObjectByName(attacker->getName()) == attacker,
                    "each settled encounter must release exactly one queued commit without retained counter growth");
        game->getContext()->shutdown();
    }
}

void testQueuedSceneCombatDeferralReleasesAfterThrowAndKeepsDirectReplacementCancellation() {
    for (const bool directReplacement : {false, true}) {
        auto game = makeWindowlessFightGame();
        auto source = game->getMap();
        source->setMapName("unitInterruptedCombatSource");
        add_test_player(game);
        auto destination = std::make_shared<CMap>();
        destination->setGame(game);
        destination->setMapName("unitInterruptedCombatDestination");
        game->getContext()->getMapSessionStore()->put(destination);
        auto scene = game->getSceneManager();
        auto attacker = add_test_creature(game, "unitInterruptedCombatAttacker", 2, 0);
        auto defender = add_test_creature(game, "unitInterruptedCombatDefender", 3, 0);
        attacker->getBaseStats()->setAgility(50);
        auto controller = std::make_shared<SceneRequestFightController>();
        attacker->setFightController(controller);
        controller->action = [&] {
            if (directReplacement) {
                game->setMap(destination);
                return;
            }
            CMapTransitionRequest request;
            request.targetMap = destination->getMapName();
            request.reuseLoadedMap = true;
            expect_true(scene->requestMapChange(game, std::move(request)),
                        "the throwing controller must queue a scene");
            throw std::runtime_error("unit scene controller primary");
        };
        auto fight = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(attacker, {defender}));
        expect_true(pumpHandlerUntil([&] { return fight.finished(); }), "interrupted combat must unwind boundedly");
        bool originalError = false;
        bool cancelled = false;
        if (fight.finished()) {
            try {
                const auto result = fight.get();
                cancelled = result.outcome == CFightOutcome::Cancelled;
                expect_true(directReplacement && result.outcome == CFightOutcome::Cancelled,
                            "direct map replacement must still cancel owned defeat");
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            } catch (const std::runtime_error &error) {
                originalError = std::string(error.what()) == "unit scene controller primary";
            }
        }
        expect_true((directReplacement ? cancelled : originalError) && controller->end_count == 1,
                    "RAII deferral must preserve the original controller failure and one cleanup");
        if (!directReplacement) {
            expect_true(pumpHandlerUntil([&] { return !scene->isTransitionPending(); }) &&
                            game->getMap() == destination && defender->isAlive() &&
                            source->getObjectByName(defender->getName()) == defender,
                        "exception unwind must release the queued transition without defeating a living actor");
        }
        game->getContext()->shutdown();
    }
}

struct DefeatPresentationOrderProbe {
    int starts = 0;
    int controls = 0;
    int ends = 0;
    int browserFactories = 0;
    int browsers = 0;
    bool browserSawCleanup = false;
    bool browserSawFightPanel = false;
    bool browserSawSaveAdmission = false;
};

class PresentationSelfDefeatController : public CPlayerFightController {
  public:
    PresentationSelfDefeatController(std::shared_ptr<DefeatPresentationOrderProbe> probe, int mode)
        : probe(std::move(probe)), mode(mode) {}

    void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        ++probe->starts;
        CPlayerFightController::start(std::move(me), std::move(opponent));
    }

    vstd::task<bool> controlAsync(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature>) override {
        ++probe->controls;
        me->setHp(0);
        co_return true;
    }

    void end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        ++probe->ends;
        CPlayerFightController::end(me, std::move(opponent));
        if (mode == 1) {
            throw std::runtime_error("unit defeat presentation cleanup primary");
        }
        if (mode == 2) {
            me->getGame()->getContext()->advanceTransitionGeneration();
        }
    }

  private:
    std::shared_ptr<DefeatPresentationOrderProbe> probe;
    int mode;
};

class NativeDefeatChoiceFixture {
  public:
    NativeDefeatChoiceFixture() : ui(pybind11::module_::import("ui")), previous(ui.attr("showDefeatFlow")) {
        pybind11::dict scope;
        // Only the presentation entry is replaced. The real UiFlow, dispatcher, native panel,
        // and keyboard acknowledgement run without requiring the _game extension in this unit binary.
        pybind11::exec(R"(
def unitDefeatFlow(game):
    yield {"operation": "gui.showChoice", "args": ["Defeated", '[{"id":"continue","label":"Continue adventure"}]', "Continue", "Back"], "kwargs": {}}
)",
                       scope);
        ui.attr("showDefeatFlow") = scope["unitDefeatFlow"];
    }

    NativeDefeatChoiceFixture(const NativeDefeatChoiceFixture &) = delete;
    NativeDefeatChoiceFixture &operator=(const NativeDefeatChoiceFixture &) = delete;
    ~NativeDefeatChoiceFixture() { ui.attr("showDefeatFlow") = previous; }

  private:
    pybind11::object ui;
    pybind11::object previous;
};

class ObservedDefeatBrowserPanel : public CGameCampaignBrowserPanel {
  public:
    explicit ObservedDefeatBrowserPanel(std::shared_ptr<DefeatPresentationOrderProbe> probe)
        : probe(std::move(probe)) {}

    void setGame(std::shared_ptr<CGame> game) override {
        CGameCampaignBrowserPanel::setGame(game);
        if (!game) {
            return;
        }
        ++probe->browsers;
        probe->browserSawFightPanel = game->getGui()->findChild("CGameFightPanel") != nullptr;
        probe->browserSawCleanup = probe->ends == 1 && !probe->browserSawFightPanel;
        probe->browserSawSaveAdmission = game->getMap()->tryBeginSaveSnapshot().has_value();
    }

  private:
    std::shared_ptr<DefeatPresentationOrderProbe> probe;
};

void installDefeatBrowserObserver(const std::shared_ptr<CGame> &game,
                                  const std::shared_ptr<DefeatPresentationOrderProbe> &probe) {
    auto objects = game->getObjectHandler();
    objects->registerType("CGameFightPanel", [] { return std::make_shared<CGameFightPanel>(); });
    auto fight_panel = game->createObject<CGameFightPanel>("fightPanel");
    if (!fight_panel) {
        throw std::runtime_error("Native defeat presentation fixture has no fight panel factory.");
    }
    expect_true(!game->getGui()->findChild("CGameFightPanel"),
                "the fixture factory preflight must not attach a fight panel before controller start");
    objects->registerType("CGameCampaignBrowserPanel", [probe] {
        ++probe->browserFactories;
        return std::make_shared<ObservedDefeatBrowserPanel>(probe);
    });
    auto prototype = objects->getType("CGameCampaignBrowserPanel");
    if (!std::dynamic_pointer_cast<ObservedDefeatBrowserPanel>(prototype) || prototype->getGame()) {
        throw std::runtime_error("Native defeat presentation fixture needs an unbound observed browser prototype.");
    }
    expect_true(probe->browserFactories == 1 && probe->browsers == 0 && !probe->browserSawCleanup &&
                    !probe->browserSawFightPanel && !probe->browserSawSaveAdmission,
                "a real subtype-probe construction must not observe or count a presented browser");
    expect_true(!game->getGui()->findChild("CGameCampaignBrowserPanel"),
                "raw browser construction must not attach a presentation panel");
    game->getObjectHandler()->registerConfig("campaignBrowserPanel",
                                             std::make_shared<json>(json{{"class", "CGameCampaignBrowserPanel"}}));
    expect_true(game->getObjectHandler()->getClass("campaignBrowserPanel") == "CGameCampaignBrowserPanel",
                "the dispatcher ordering fixture must resolve its real native browser factory");
}

void testOwnedDefeatPresentationFollowsSuccessfulControllerCleanup() {
    NativeDefeatChoiceFixture uiFixture;
    auto loop = vstd::event_loop<>::instance();
    for (int mode = 0; mode != 4; ++mode) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        auto context = game->getContext();
        map->setBoolProperty("plugin_cityFixedLoot", true);
        map->setBoolProperty("guardNativeEncounterSaves", mode == 3);
        auto probe = std::make_shared<DefeatPresentationOrderProbe>();
        installDefeatBrowserObserver(game, probe);
        auto player = add_test_player(game);
        auto controller = std::make_shared<PresentationSelfDefeatController>(probe, mode);
        player->setFightController(controller);
        player->getBaseStats()->setAgility(100);
        auto winner = add_test_creature(game, "unitPresentationWinner", 1, 0);
        const auto gold = player->getGold();
        const auto turn = map->getTurn();
        auto combat = context->spawnTask(CFightHandler::fightManyResultAsync(player, {winner}));
        const bool finished =
            pumpHandlerUntil([&] { return combat.finished() && (mode == 1 || mode == 2 || probe->browsers != 0); });
        expect_true(finished && probe->starts == 1 && probe->controls == 1 && probe->ends == 1,
                    "the real player controller must start, self-defeat and finish cleanup exactly once");
        bool primary = false;
        if (combat.finished()) {
            try {
                const auto result = combat.get();
                expect_true(mode != 1 && result.outcome == CFightOutcome::AttackerDefeat,
                            "successful cleanup must preserve the recovered player's actual defeat result");
            } catch (const std::runtime_error &error) {
                primary = std::string(error.what()) == "unit defeat presentation cleanup primary";
            }
        }
        expect_true(primary == (mode == 1), "failed cleanup must retain its original exception identity");
        const bool presented = mode == 0 || mode == 3;
        expect_true(probe->browsers == (presented ? 1 : 0),
                    "only certified current cleanup may create one defeat browser, with or without save opt-in");
        expect_true(!presented || (probe->browserSawCleanup && probe->browserSawSaveAdmission),
                    "the native browser constructor must observe detached fight UI and released admission");
        expect_true(player->getHp() == 1 && map->getObjectByName("player") == player && player->getGold() == gold &&
                        map->getTurn() == turn,
                    "presentation ordering must not replay recovery, grant gold or advance the map");
        auto panel = std::dynamic_pointer_cast<CGameCampaignBrowserPanel>(
            game->getGui()->findChild("CGameCampaignBrowserPanel"));
        if (presented) {
            expect_true(panel && panel->getSelectedId() == "continue",
                        "the real dispatcher must attach its actual native stable-choice panel");
            if (panel) {
                panel->keyboardEvent(game->getGui(), SDL_KEYDOWN, SDLK_RETURN);
                expect_true(pumpHandlerUntil([&] { return !game->getGui()->findChild("CGameCampaignBrowserPanel"); }),
                            "real keyboard acknowledgement must detach the browser");
            }
        } else {
            loop->runReady();
            expect_true(!map->tryBeginSaveSnapshot(), "failed or stale owned cleanup must stay quarantined");
        }
        loop->runReady();
        expect_true(!game->getGui()->findChild("CGameFightPanel") && probe->browsers == (presented ? 1 : 0),
                    "queue draining must not reopen the ended fight or duplicate its browser");
        context->shutdown();
    }
}

void testPublicDefeatPreservesItsIndependentPostedPresentation() {
    NativeDefeatChoiceFixture uiFixture;
    auto game = makeWindowlessFightGame();
    auto map = game->getMap();
    auto context = game->getContext();
    map->setBoolProperty("plugin_cityFixedLoot", true);
    auto probe = std::make_shared<DefeatPresentationOrderProbe>();
    installDefeatBrowserObserver(game, probe);
    auto player = add_test_player(game);
    auto winner = add_test_creature(game, "unitPublicPresentationWinner", 1, 0);
    auto controller = std::make_shared<PresentationSelfDefeatController>(probe, 0);
    player->setFightController(controller);
    controller->start(player, winner);
    expect_true(game->getGui()->findChild("CGameFightPanel") != nullptr,
                "the public-path control must actually have an externally owned native fight panel");
    player->setHp(0);
    auto recovery = context->spawnTask(CFightHandler::defeatedCreatureAsync(winner, player));
    expect_true(pumpHandlerUntil([&] { return recovery.finished() && probe->browsers == 1; }),
                "public defeat must still post its presentation without a combat participant guard");
    if (recovery.finished()) {
        recovery.get();
    }
    expect_true(probe->ends == 0 && probe->browserSawFightPanel,
                "public defeat must not silently end an independently owned controller");
    auto panel =
        std::dynamic_pointer_cast<CGameCampaignBrowserPanel>(game->getGui()->findChild("CGameCampaignBrowserPanel"));
    if (panel) {
        panel->keyboardEvent(game->getGui(), SDL_KEYDOWN, SDLK_RETURN);
    }
    controller->end(player, winner);
    vstd::event_loop<>::instance()->runReady();
    expect_true(probe->browsers == 1 && probe->ends == 1 && !game->getGui()->findChild("CGameFightPanel"),
                "independent public caller cleanup must remain exactly once");
    context->shutdown();
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

    for (bool afterSuspension : {false, true}) {
        auto loop = vstd::event_loop<>::instance();
        auto game = load_empty_game();
        auto attacker = add_test_creature(game, "unitCancelledAttacker");
        auto defender = add_test_creature(game, "unitCancelledDefender", 1, 0);
        const auto attacker_controller =
            std::dynamic_pointer_cast<NoProgressFightController>(attacker->getFightController());
        const auto defender_controller =
            std::dynamic_pointer_cast<NoProgressFightController>(defender->getFightController());

        SDL_Event quit_event{};
        quit_event.type = SDL_QUIT;
        auto pushQuit = [quit_event]() mutable {
            expect_true(SDL_PushEvent(&quit_event) == 1, "SDL_QUIT event should be queued for cancellation coverage");
        };
        if (afterSuspension) {
            loop->invoke(pushQuit);
        } else {
            pushQuit();
        }

        const auto result = CFightHandler::fightManyResult(attacker, {defender});
        SDL_FlushEvent(SDL_QUIT);

        expect_true(result.outcome == CFightOutcome::Cancelled, "queued SDL_QUIT should report cancelled combat");
        expect_true(afterSuspension ? result.rounds <= 1 : result.rounds == 0,
                    "quit cancellation must retain the original pre-turn and next-round bounds");
        expect_true(!afterSuspension || loop->quitRequested(),
                    "the posted quit fixture must exercise an event consumed by the outer loop");
        expect_true(result.survivor == attacker && result.opponent == defender,
                    "cancelled combat should keep participant metadata");
        expect_true(!result.resolved() && !result.attackerSucceeded(),
                    "cancelled combat should stay distinct from resolved bool outcomes");
        expect_controller_lifecycle(attacker_controller, 1, 1, "attacker cleanup should run when combat is cancelled");
        expect_controller_lifecycle(defender_controller, 1, 1, "opponent cleanup should run when combat is cancelled");
        expect_true(game->getMap()->getStringProperty("combatStatus").find("cancelled") != std::string::npos,
                    "cancelled combat should publish the cancelled status text");
        if (afterSuspension) {
            auto nextGame = load_empty_game();
            auto nextAttacker = add_test_creature(nextGame, "unitNextSessionAttacker");
            auto nextDefender = add_test_creature(nextGame, "unitNextSessionDefender", 1, 0);
            expect_true(!loop->quitRequested(), "starting the next session must clear its prior loop quit state");
            const auto nextResult = CFightHandler::fightManyResult(nextAttacker, {nextDefender});
            expect_true(nextResult.outcome == CFightOutcome::Stalled && nextResult.rounds == 20,
                        "the surviving next session must execute its full ordinary no-progress combat budget");
        }
    }
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
    attachFightPanelGuiFixture(game);
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
    attachFightPanelGuiFixture(game);
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
    attachFightPanelGuiFixture(game);
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
        auto gui = game ? game->getGui() : nullptr;
        std::size_t fight_panel_count = 0;
        std::shared_ptr<CGameFightPanel> attached_panel;
        if (gui) {
            for (const auto &child : gui->getChildren()) {
                if (auto candidate = vstd::cast<CGameFightPanel>(child)) {
                    ++fight_panel_count;
                    attached_panel = candidate;
                }
            }
        }
        auto panel = gui ? vstd::cast<CGameFightPanel>(gui->findChild("CGameFightPanel")) : nullptr;
        expect_true(fight_panel_count == 1, "queued cancellation should find exactly one attached fight panel");
        expect_true(panel && panel == attached_panel && gui->findChild(panel) == panel,
                    "queued cancellation should target the same fight panel found by the GUI");
        if (panel) {
            panel->cancel();
            *panel_was_cancelled = panel->isCancelled();
        }
        std::cout << "[handler-test] cancellation callback ran=" << *cancellation_callback_ran
                  << " panelFound=" << (panel != nullptr) << " panelCount=" << fight_panel_count
                  << " isCancelled=" << *panel_was_cancelled << std::endl;
    });

    std::cout << "[handler-test] BEFORE fightManyResult for queued player cancellation" << std::endl;
    const auto result = CFightHandler::fightManyResult(player, {defender});
    std::cout << "[handler-test] AFTER fightManyResult for queued player cancellation outcome="
              << static_cast<int>(result.outcome) << " rounds=" << result.rounds << std::endl;

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

class AllocationOrderTickEffect : public CEffect {
  public:
    int ticks = 0;

    void prepare(bool restoresHealth, const std::shared_ptr<CCreature> &victim,
                 const std::shared_ptr<CCreature> &caster) {
        healTick = restoresHealth;
        tickDamage = 3;
        ticks = 0;
        setTypeId(healTick ? "unitAllocationHealTick" : "unitAllocationDamageTick");
        setName(getTypeId());
        if (healTick) {
            addTag(CTag::Buff);
        } else {
            removeTag(CTag::Buff);
        }
        setGame(victim->getGame());
        setDuration(1);
        setVictim(victim);
        setCaster(caster);
    }

    void onEffect() override {
        ++ticks;
        if (healTick) {
            getVictim()->heal(2);
        } else {
            // A fixed native tick isolates ordering from attack, block and critical RNG.
            getVictim()->setHp(getVictim()->getHp() - tickDamage);
        }
    }

    void setTickDamage(int amount) { tickDamage = amount; }

  private:
    bool healTick = false;
    int tickDamage = 3;
};

using AllocationOrderEffectPair =
    std::pair<std::shared_ptr<AllocationOrderTickEffect>, std::shared_ptr<AllocationOrderTickEffect>>;

AllocationOrderEffectPair makePointerRankedEffectPair() {
    auto first = std::make_shared<AllocationOrderTickEffect>();
    auto second = std::make_shared<AllocationOrderTickEffect>();
    const std::less<std::shared_ptr<CEffect>> pointerOrder;
    if (pointerOrder(second, first)) {
        std::swap(first, second);
    }
    expect_true(pointerOrder(first, second), "the two probe effects must have distinct pointer ranks");
    return {first, second};
}

AllocationOrderEffectPair attachAllocationOrderEffects(const AllocationOrderEffectPair &pointerRanked,
                                                       bool healAtLowerPointer,
                                                       const std::shared_ptr<CCreature> &victim,
                                                       const std::shared_ptr<CCreature> &damageCaster) {
    auto heal = healAtLowerPointer ? pointerRanked.first : pointerRanked.second;
    auto damage = healAtLowerPointer ? pointerRanked.second : pointerRanked.first;
    heal->prepare(true, victim, victim);
    damage->prepare(false, victim, damageCaster);
    // Identical semantic insertion order in both cases; only address-to-role assignment changes.
    victim->addEffect(heal);
    victim->addEffect(damage);
    expect_true(victim->getEffects().size() == 2, "both distinct configured probe effects must be attached");
    return {heal, damage};
}

void releaseAllocationOrderEndpoints(const AllocationOrderEffectPair &effects) {
    for (const auto &effect : {effects.first, effects.second}) {
        effect->setCaster(nullptr);
        effect->setVictim(nullptr);
    }
}

struct AllocationOrderTickSample {
    int hp;
    int healTicks;
    int damageTicks;
    int healTimeLeft;
    int damageTimeLeft;

    bool operator==(const AllocationOrderTickSample &) const = default;
};

AllocationOrderTickSample allocationOrderTickSample(const std::shared_ptr<CCreature> &victim,
                                                    const AllocationOrderEffectPair &semanticEffects) {
    return {victim->getHp(), semanticEffects.first->ticks, semanticEffects.second->ticks,
            semanticEffects.first->getTimeLeft(), semanticEffects.second->getTimeLeft()};
}

void testEffectTickCappingAndExpiryIgnoreAllocationOrder() {
    auto game = load_empty_game();
    const auto pointerRanked = makePointerRankedEffectPair();
    std::optional<AllocationOrderTickSample> reference;
    for (bool healAtLowerPointer : {true, false}) {
        auto victim = add_test_creature(game, "unitAllocationCappingVictim");
        const int hpMax = victim->getHpMax();
        victim->setHp(hpMax);
        const auto semanticEffects = attachAllocationOrderEffects(pointerRanked, healAtLowerPointer, victim, victim);

        CFightHandler::applyEffects(victim);
        const auto sample = allocationOrderTickSample(victim, semanticEffects);
        expect_true(sample.hp == hpMax - 1,
                    "at full health the damage tick must create room before the Buff recovery tick");
        expect_true(sample.healTicks == 1 && sample.damageTicks == 1 && sample.healTimeLeft == 0 &&
                        sample.damageTimeLeft == 0,
                    "both one-turn effects must tick exactly once and reach zero duration");
        expect_true(victim->getEffects().size() == 2,
                    "a just-ticked zero-duration effect remains attached until the next expiry pass");

        CFightHandler::applyEffects(victim);
        expect_true(victim->getEffects().empty() && allocationOrderTickSample(victim, semanticEffects) == sample,
                    "the next expiry pass must remove both effects without repeating a tick");

        if (reference) {
            expect_true(sample == *reference, "healing saturation must not depend on effect pointer layout");
        } else {
            reference = sample;
        }
        game->getMap()->removeObject(victim);
        releaseAllocationOrderEndpoints(pointerRanked);
    }

    auto victim = add_test_creature(game, "unitFrozenHealthTierVictim");
    const int hpMax = victim->getHpMax();
    expect_true(hpMax > 2, "the tier crossover probe needs positive room above the lethal boundary");
    victim->setHp(hpMax);
    auto firstDamage = std::make_shared<AllocationOrderTickEffect>();
    auto lastDamage = std::make_shared<AllocationOrderTickEffect>();
    auto recovery = std::make_shared<AllocationOrderTickEffect>();
    firstDamage->prepare(false, victim, victim);
    firstDamage->setTypeId("unitAllocationADamageTick");
    firstDamage->setTickDamage(hpMax - 2);
    lastDamage->prepare(false, victim, victim);
    lastDamage->setTypeId("unitAllocationBDamageTick");
    recovery->prepare(true, victim, victim);
    victim->addEffect(recovery);
    victim->addEffect(lastDamage);
    victim->addEffect(firstDamage);
    CFightHandler::applyEffects(victim);
    expect_true(victim->getHp() == -1 && firstDamage->ticks == 1 && lastDamage->ticks == 1 && recovery->ticks == 0 &&
                    firstDamage->getTimeLeft() == 0 && lastDamage->getTimeLeft() == 0 && recovery->getTimeLeft() == 1,
                "becoming hurt during a full-health phase must not reorder recovery ahead of the next lethal tick");
    game->getMap()->removeObject(victim);
    for (const auto &effect : {firstDamage, lastDamage, recovery}) {
        effect->setCaster(nullptr);
        effect->setVictim(nullptr);
    }
}

class AllocationOrderCancellationProbe : public CancellingFightController {
  public:
    int controls = 0;

    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        ++controls;
        return false;
    }
};

struct AllocationOrderFightSample {
    AllocationOrderTickSample ticks;
    CFightOutcome outcome;
    int rounds;
    int controllerCalls;
    int damageCasterLoot;
    int selectedOpponentLoot;
    bool victimRegistered;

    bool operator==(const AllocationOrderFightSample &) const = default;
};

void testEffectTickLethalityTimingAndCasterIgnoreAllocationOrder() {
    auto game = load_empty_game();
    auto map = game->getMap();
    const auto pointerRanked = makePointerRankedEffectPair();

    // Buff-first recovery still permits lethal damage at HP 1, with the actual caster credited.
    // At HP 2 it leaves the victim alive for its action, independent of pointer layout.
    for (int initialHp : {1, 2}) {
        std::optional<AllocationOrderFightSample> reference;
        for (bool healAtLowerPointer : {true, false}) {
            auto victim = add_test_creature(game, "unitAllocationFightVictim");
            auto selected = add_test_creature(game, "unitAAllocationSelectedOpponent", 1, 0);
            auto damageCaster = add_test_creature(game, "unitZAllocationActualCaster", 1, 0);
            victim->getBaseStats()->setAgility(20);
            victim->setHp(initialHp);
            auto controller = std::make_shared<AllocationOrderCancellationProbe>();
            victim->setFightController(controller);
            add_unit_loot(game, victim, "unitAllocationCasterLoot");
            const auto semanticEffects =
                attachAllocationOrderEffects(pointerRanked, healAtLowerPointer, victim, damageCaster);

            const auto result = CFightHandler::fightManyResult(victim, {selected, damageCaster});
            const AllocationOrderFightSample sample{allocationOrderTickSample(victim, semanticEffects),
                                                    result.outcome,
                                                    result.rounds,
                                                    controller->controls,
                                                    damageCaster->countItems("unitAllocationCasterLoot"),
                                                    selected->countItems("unitAllocationCasterLoot"),
                                                    map->getObjectByName(victim->getName()) == victim};
            expect_true(sample.rounds == 1 && sample.ticks.damageTicks == 1 && sample.ticks.damageTimeLeft == 0,
                        "the controlled first actor turn must execute exactly one damage tick");
            expect_true(sample.selectedOpponentLoot == 0,
                        "the selected opponent must never receive another caster's lethal-effect loot");
            expect_true(victim->isAlive() == (initialHp == 2) && sample.ticks.healTicks == 1 &&
                            sample.ticks.healTimeLeft == 0,
                        "the Buff recovery must tick before damage while retaining the real lethal boundary");

            if (victim->isAlive()) {
                expect_true(initialHp == 2 && sample.ticks.hp == 1 && sample.outcome == CFightOutcome::Cancelled &&
                                sample.controllerCalls == 1 && sample.ticks.healTicks == 1 &&
                                sample.ticks.healTimeLeft == 0 && sample.damageCasterLoot == 0 &&
                                sample.victimRegistered && result.survivor == victim && result.opponent == selected,
                            "a surviving effect phase must reach the cancelling action without granting defeat loot");
            } else {
                expect_true(sample.outcome == CFightOutcome::AttackerDefeat && sample.controllerCalls == 0 &&
                                sample.damageCasterLoot == 1 && !sample.victimRegistered &&
                                result.survivor == damageCaster && result.opponent == victim,
                            "a lethal tick must skip the action, remove the victim and credit its actual caster");
                expect_true((sample.ticks.healTicks == 0 && sample.ticks.healTimeLeft == 1) ||
                                (sample.ticks.healTicks == 1 && sample.ticks.healTimeLeft == 0),
                            "healing duration may decrement only if that effect actually executes before death");
            }

            if (reference) {
                expect_true(sample == *reference,
                            "lethality, action eligibility and effect timing must not depend on pointer layout");
            } else {
                reference = sample;
            }
            if (map->getObjectByName(victim->getName()) == victim) {
                map->removeObject(victim);
            }
            map->removeObject(selected);
            map->removeObject(damageCaster);
            releaseAllocationOrderEndpoints(pointerRanked);
        }
    }
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

class ItemCommitHealingProbe : public CItem {
  public:
    std::function<void()> afterHeal;
    std::function<void()> readPolicy;
    int uses = 0;
    int policyReads = 0;
    bool disposable = true;

    bool isDisposable() override {
        ++policyReads;
        if (readPolicy) {
            readPolicy();
        }
        return disposable;
    }

    void onUse(std::shared_ptr<CGameEvent> event) override {
        ++uses;
        auto caused = vstd::cast<CGameEventCaused>(event);
        vstd::cast<CCreature>(caused->getCause())->heal(5);
        if (afterHeal) {
            afterHeal();
        }
    }
};

void testDisposableItemCommitConsumesBeforeReceiptsAndCancellation() {
    auto loop = vstd::event_loop<>::instance();
    for (int mode : {0, 1, 2, 3, 4, 5}) {
        auto game = makeWindowlessFightGame();
        auto player = add_test_player(game);
        player->setHp(1);
        auto item = std::make_shared<ItemCommitHealingProbe>();
        item->setGame(game);
        item->setName("unitCommittedHealingItem");
        item->setTypeId("unitCommittedHealingItem");
        item->addTag(CTag::Heal);
        item->setNumericProperty("power", 5);
        player->addItem(item);
        CPlaytestTrace::configure(true, "", 100, true);
        vstd::task_handle<void> use;
        if (mode == 0) {
            item->afterHeal = [&use] { use.requestStop(); };
        } else if (mode == 1) {
            item->afterHeal = [context = game->getContext()] { context->shutdown(); };
        } else if (mode == 4) {
            item->readPolicy = [context = game->getContext()] { context->shutdown(); };
        } else if (mode == 5) {
            item->readPolicy = [&use] { use.requestStop(); };
        }
        auto receipt = std::make_shared<AsyncTriggerProbe>();
        if (mode == 2) {
            auto trigger = std::make_shared<CCustomTrigger>(
                item->getName(), "onUse", [receipt](auto, auto) { return awaitTriggerProbe(receipt, "receipt"); });
            trigger->setName("unitCommittedItemReceipt");
            game->getMap()->getEventHandler()->registerTrigger(trigger);
        }
        use = game->getContext()->spawnTask(player->useItemAsync(item));
        if (mode == 3) {
            use.requestStop();
        } else if (mode == 2) {
            expect_true(pumpHandlerUntil([&] { return !receipt->entered.empty() || use.finished(); }) &&
                            !use.finished() && player->getHp() == 6 && !player->hasInInventory(item),
                        "a suspended item receipt must expose healed HP and an already-consumed inventory item");
            bool tracedBeforeReceipt = false;
            for (const auto &line : CPlaytestTrace::records()) {
                const auto record = json::parse(line);
                if (record.value("event", std::string()) == "item_used") {
                    tracedBeforeReceipt = record.at("hpBefore").get<int>() == 1 &&
                                          record.at("hpAfter").get<int>() == 6 && !record.at("ownedAfter").get<bool>();
                }
            }
            expect_true(tracedBeforeReceipt,
                        "item-use evidence must settle with consumption before a later receipt can suspend or save");
            use.requestStop();
        }
        expect_true(pumpHandlerUntil([&] { return use.finished(); }),
                    "cancelled disposable use must release every owned execution frame");
        bool cancelled = false;
        if (use.finished()) {
            try {
                use.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        const bool committed = mode < 3;
        expect_true(cancelled && item->uses == (committed ? 1 : 0) && player->getHp() == (committed ? 6 : 1) &&
                        player->hasInInventory(item) != committed && item->policyReads == (mode == 3 ? 0 : 1),
                    "committed healing must consume once, while cancellation before onUse must retain the item");
        int usedRecords = 0;
        for (const auto &line : CPlaytestTrace::drain()) {
            const auto record = json::parse(line);
            if (record.value("event", std::string()) == "item_used") {
                ++usedRecords;
                expect_true(
                    record.at("disposable").get<bool>() && record.at("hpBefore").get<int>() == 1 &&
                        record.at("hpAfter").get<int>() == 6 && !record.at("ownedAfter").get<bool>() &&
                        record.at("onlyUsedItemRemoved").get<bool>() && record.at("equipmentUnchanged").get<bool>(),
                    "committed/cancelled/shutdown item traces must use cached policy and actual consumed state");
            }
        }
        expect_true(usedRecords == (committed ? 1 : 0),
                    "item traces must record an actual commit once and never record a cancelled pre-use operation");
        CPlaytestTrace::configure(false);
        if (committed && game->getContext()->isActive()) {
            auto repeated = game->getContext()->spawnTask(player->useItemAsync(item));
            bool rejected = false;
            if (repeated.finished()) {
                try {
                    repeated.get();
                } catch (const std::invalid_argument &error) {
                    rejected = std::string(error.what()) == "Tried to use item not in inventory!";
                }
            }
            expect_true(rejected && player->getHp() == 6 && item->uses == 1,
                        "a cancelled committed potion must not be usable for a second healing effect");
        }
        game->getContext()->shutdown();
    }
    {
        auto game = makeWindowlessFightGame();
        auto player = add_test_player(game);
        auto other = add_test_creature(game, "unitForeignItemOwner", 1, 0);
        player->setHp(1);
        auto owned = std::make_shared<ItemCommitHealingProbe>();
        owned->setGame(game);
        owned->setName("unitValidItemAfterRejection");
        player->addItem(owned);
        auto foreign = std::make_shared<ItemCommitHealingProbe>();
        foreign->setGame(game);
        foreign->setName("unitForeignItemAfterRejection");
        other->addItem(foreign);
        const auto inventory = player->getItems();
        const auto otherInventory = other->getItems();
        for (const auto &invalid : std::vector<std::shared_ptr<CItem>>{nullptr, foreign}) {
            for (bool synchronous : {false, true}) {
                bool rejected = false;
                try {
                    if (synchronous) {
                        player->useItem(invalid);
                    } else {
                        auto use = game->getContext()->spawnTask(player->useItemAsync(invalid));
                        expect_true(use.finished(), "invalid item arguments must settle without queuing gameplay work");
                        if (use.finished()) {
                            use.get();
                        }
                    }
                } catch (const std::invalid_argument &error) {
                    rejected = std::string(error.what()) == "Tried to use item not in inventory!";
                }
                expect_true(rejected && player->getHp() == 1 && player->getItems() == inventory &&
                                other->getItems() == otherInventory && owned->uses == 0 && owned->policyReads == 0 &&
                                foreign->uses == 0 && foreign->policyReads == 0 && game->getContext()->isActive(),
                            "null and foreign items must reject recoverably at both boundaries without gameplay work");
            }
        }
        auto use = game->getContext()->spawnTask(player->useItemAsync(owned));
        expect_true(pumpHandlerUntil([&] { return use.finished(); }),
                    "a valid item must remain usable after rejected item arguments");
        if (use.finished()) {
            use.get();
        }
        expect_true(player->getHp() == 6 && !player->hasInInventory(owned) && owned->uses == 1 &&
                        owned->policyReads == 1 && other->getItems() == otherInventory && foreign->uses == 0 &&
                        foreign->policyReads == 0,
                    "argument rejection must preserve normal subsequent consumption and the foreign inventory");
        game->getContext()->shutdown();
    }
    auto game = makeWindowlessFightGame();
    auto player = add_test_player(game);
    player->setHp(1);
    auto protectedItem = std::make_shared<ItemCommitHealingProbe>();
    protectedItem->setGame(game);
    protectedItem->setName("unitDetachedQuestItem");
    protectedItem->addTag(CTag::Quest);
    player->addItem(protectedItem);
    game->getMap()->detachPlayer();
    protectedItem->afterHeal = [context = game->getContext()] { context->shutdown(); };
    auto protectedUse = game->getContext()->spawnTask(player->useItemAsync(protectedItem));
    expect_true(pumpHandlerUntil([&] { return protectedUse.finished(); }),
                "detached-player quest-item shutdown must finish its owned use");
    bool cancelled = false;
    if (protectedUse.finished()) {
        try {
            protectedUse.get();
        } catch (const vstd::task_cancelled &) {
            cancelled = true;
        }
    }
    expect_true(cancelled && player->getHp() == 6 && player->hasInInventory(protectedItem) &&
                    protectedItem->policyReads == 1,
                "inactive cleanup must preserve legacy quest-item protection for detached CPlayer owners");
    game->getContext()->shutdown();
    loop->runReady();
}

void testScriptCallbackFlowUsesInitializedUiModule() {
    auto game = makeWindowlessFightGame();
    int callbacks = 0;
    auto flow =
        game->getScriptHandler()->createCallbackFlow(pybind11::cpp_function([&callbacks] { ++callbacks; }), game);
    expect_true(callbacks == 0, "creating an owned callback flow must preserve its lazy execution");
    expect_true(!flow->next() && callbacks == 1,
                "the trusted UI module must advance and complete the native-owned callback");
    expect_true(!flow->next() && callbacks == 1, "completed callback flows must not invoke their body twice");
    flow.reset();
    game->getContext()->shutdown();
}

class ItemPositionCommitProbe : public CCreature {
  public:
    bool beforeReleased = false;
    bool afterEntered = false;
    bool afterReleased = false;

    vstd::task<void> beforeMoveAsync() override {
        return [](std::shared_ptr<ItemPositionCommitProbe> self) -> vstd::task<void> {
            co_await vstd::until(vstd::event_loop<>::instance(), [self] { return self->beforeReleased; });
        }(this->ptr<ItemPositionCommitProbe>());
    }

    vstd::task<void> afterMoveAsync() override {
        return [](std::shared_ptr<ItemPositionCommitProbe> self) -> vstd::task<void> {
            self->afterEntered = true;
            co_await vstd::until(vstd::event_loop<>::instance(), [self] { return self->afterReleased; });
        }(this->ptr<ItemPositionCommitProbe>());
    }
};

void testItemPositionCommitOwnsConsumptionBeforeArrivalCancellation() {
    auto loop = vstd::event_loop<>::instance();
    const auto conditions = loop->getConditionalTaskCount();
    for (bool afterPosition : {false, true}) {
        for (bool shutdown : {false, true}) {
            auto game = makeWindowlessFightGame();
            auto actor = std::make_shared<ItemPositionCommitProbe>();
            actor->setGame(game);
            actor->setName("unitItemPositionActor");
            initialize_test_creature_stats(actor);
            game->getMap()->addObject(actor);
            auto tile = std::make_shared<CTile>();
            tile->setCanStep(true);
            game->getMap()->addTile(tile, 1, 0, 0);
            auto item = add_unit_loot(game, actor, "unitPositionDisposable");
            int commits = 0;
            auto commit =
                std::make_shared<vstd::move_only_function<void()>>([actor, item, &commits, settled = false]() mutable {
                    if (!std::exchange(settled, true)) {
                        ++commits;
                        actor->removeItem(item);
                    }
                });
            pybind11::dict scope;
            pybind11::exec("class ItemFlowProbe:\n    def onUseFlow(self):\n        yield from ()\n"
                           "callbacks = ItemFlowProbe()\n",
                           scope);
            auto callbacks = scope["callbacks"];
            CPythonOverrides::retain(item, callbacks);
            auto flow = CScriptHandler::createObjectFlow(item, "onUseFlow", {}, game, {}, commit);
            expect_true(flow != nullptr, "the position commit fixture must create an owned script flow");
            bool wrongQuestCommitRejected = false;
            if (flow) {
                try {
                    flow->markCommitted();
                } catch (const std::invalid_argument &) {
                    wrongQuestCommitRejected = true;
                }
            }
            expect_true(wrongQuestCommitRejected && commits == 0 && actor->hasInInventory(item),
                        "a quest marker must not consume an item-use capability");
            auto positionCommit = flow ? flow->commitCallback() : vstd::move_only_function<void()>{[] {}};
            flow.reset();
            CPythonOverrides::release(item.get());
            commit.reset();
            auto move = game->getContext()->spawnTask(actor->moveToAsync(Coords(1, 0, 0), std::move(positionCommit)));
            if (afterPosition) {
                actor->beforeReleased = true;
                expect_true(pumpHandlerUntil([&] { return actor->afterEntered || move.finished(); }) &&
                                !move.finished() && actor->getCoords() == Coords(1, 0, 0) && commits == 1 &&
                                !actor->hasInInventory(item),
                            "the owned position commit must consume before any suspended arrival hook");
            } else {
                expect_true(!move.finished() && commits == 0 && actor->getCoords() == Coords(0, 0, 0) &&
                                actor->hasInInventory(item),
                            "a suspended preparation must preserve both position and disposable item");
            }
            if (shutdown) {
                game->getContext()->shutdown();
            } else {
                move.requestStop();
            }
            expect_true(pumpHandlerUntil([&] { return move.finished(); }),
                        "position cancellation must finish and release its owned commit capability");
            bool cancelled = false;
            if (move.finished()) {
                try {
                    move.get();
                } catch (const vstd::task_cancelled &) {
                    cancelled = true;
                }
            }
            expect_true(cancelled && commits == (afterPosition ? 1 : 0) &&
                            actor->hasInInventory(item) != afterPosition &&
                            actor->getCoords() == (afterPosition ? Coords(1, 0, 0) : Coords(0, 0, 0)),
                        "cancellation must retain preposition items and never restore a committed item or move twice");
            game->getContext()->shutdown();
        }
    }
    for (int mode : {0, 1, 2}) {
        auto game = makeWindowlessFightGame();
        auto actor = std::make_shared<ItemPositionCommitProbe>();
        actor->setGame(game);
        actor->setName("unitNormalPositionActor");
        initialize_test_creature_stats(actor);
        game->getMap()->addObject(actor);
        if (mode == 1) {
            auto tile = std::make_shared<CTile>();
            tile->setCanStep(true);
            game->getMap()->addTile(tile, 1, 0, 0);
        }
        auto item = add_unit_loot(game, actor, "unitNormalPositionItem");
        int commits = 0;
        auto commit =
            std::make_shared<vstd::move_only_function<void()>>([actor, item, &commits, settled = false]() mutable {
                if (!std::exchange(settled, true)) {
                    ++commits;
                    actor->removeItem(item);
                }
            });
        pybind11::dict scope;
        pybind11::exec("class NormalItemFlowProbe:\n    def onUseFlow(self):\n        yield from ()\n"
                       "callbacks = NormalItemFlowProbe()\n",
                       scope);
        auto callbacks = scope["callbacks"];
        CPythonOverrides::retain(item, callbacks);
        auto flow = CScriptHandler::createObjectFlow(item, "onUseFlow", {}, game, {}, commit);
        expect_true(flow != nullptr, "normal-return movement must create its explicit commit flow");
        auto positionCommit = flow ? flow->commitCallback() : vstd::move_only_function<void()>{[] {}};
        if (mode == 2) {
            actor->beforeReleased = true;
            actor->afterReleased = true;
        }
        auto move = game->getContext()->spawnTask(
            actor->moveToAsync(mode == 2 ? Coords(0, 0, 0) : Coords(1, 0, 0), std::move(positionCommit)));
        if (mode == 1) {
            game->getContext()->advanceTransitionGeneration();
            actor->beforeReleased = true;
        }
        expect_true(pumpHandlerUntil([&] { return move.finished(); }),
                    "blocked, stale, and same-coordinate movement must settle without waiting forever");
        if (move.finished()) {
            move.get();
        }
        if (flow) {
            expect_true(!flow->next(), "the flow must return normally after its position operation");
        }
        expect_true(commits == (mode == 2 ? 1 : 0) && actor->hasInInventory(item) != (mode == 2),
                    "normal-return blocked/stale moves must retain items; same-coordinate success commits once");
        flow.reset();
        CPythonOverrides::release(item.get());
        game->getContext()->shutdown();
    }
    {
        auto game = makeWindowlessFightGame();
        auto actor = add_test_creature(game, "unitOrdinaryItemFlowActor");
        auto item = add_unit_loot(game, actor, "unitOrdinaryItemFlow");
        int commits = 0;
        auto commit =
            std::make_shared<vstd::move_only_function<void()>>([actor, item, &commits, settled = false]() mutable {
                if (!std::exchange(settled, true)) {
                    ++commits;
                    actor->removeItem(item);
                }
            });
        pybind11::dict scope;
        pybind11::exec("class OrdinaryItemFlowProbe:\n    def onUseFlow(self):\n        yield from ()\n"
                       "callbacks = OrdinaryItemFlowProbe()\n",
                       scope);
        auto callbacks = scope["callbacks"];
        CPythonOverrides::retain(item, callbacks);
        auto flow = CScriptHandler::createObjectFlow(item, "onUseFlow", {}, game, {}, commit);
        expect_true(flow && !flow->next() && commits == 1 && !actor->hasInInventory(item),
                    "ordinary successful onUseFlow must consume inline before any parent continuation");
        if (flow) {
            expect_true(!flow->next(), "reading completed flow state again must remain complete");
            flow->markItemCommitted();
        }
        expect_true(commits == 1, "repeat completion and explicit settlement must not consume an item twice");
        flow.reset();
        CPythonOverrides::release(item.get());
        game->getContext()->shutdown();
    }
    auto game = makeWindowlessFightGame();
    auto actor = add_test_creature(game, "unitFailedPositionCommit");
    auto tile = std::make_shared<CTile>();
    tile->setCanStep(true);
    game->getMap()->addTile(tile, 1, 0, 0);
    auto failed = game->getContext()->spawnTask(
        actor->moveToAsync(Coords(1, 0, 0), [] { throw std::runtime_error("position commit notification failure"); }));
    expect_true(pumpHandlerUntil([&] { return failed.finished(); }),
                "a failed position callback must settle its move without entering later hooks");
    bool rejected = false;
    if (failed.finished()) {
        try {
            failed.get();
        } catch (const std::runtime_error &) {
            rejected = true;
        }
    }
    expect_true(rejected && actor->getCoords() == Coords(1, 0, 0) && !actor->getPendingMoveOrigin() &&
                    game->getMap()->getObjectsAtCoords(Coords(1, 0, 0)).contains(actor) &&
                    !game->getMap()->getObjectsAtCoords(Coords(0, 0, 0)).contains(actor),
                "position commit failure must preserve the spatial index and clear movement origin state");
    game->getContext()->shutdown();
    expect_true(loop->getConditionalTaskCount() == conditions,
                "item position cancellation must remove all preparation and arrival waits");
}

void testIndividualQuestCancellationHonorsExplicitRewardCommit() {
    auto loop = vstd::event_loop<>::instance();
    auto game = makeWindowlessFightGame();
    game->getObjectHandler()->registerType("CGameTextPanel", [] { return std::make_shared<CGameTextPanel>(); });
    game->getObjectHandler()->registerConfig("textPanel", std::make_shared<json>(json{{"class", "CGameTextPanel"}}));
    auto player = add_test_player(game);
    auto quest = std::make_shared<QuestLifecycleProbe>();
    quest->setGame(game);
    quest->setTypeId("unitExplicitCommitQuest");
    player->setQuests({quest});
    int rewards = 0;
    pybind11::dict scope;
    scope["grant"] = pybind11::cpp_function([&rewards] { ++rewards; });
    pybind11::exec(R"(
class CompletionFlowProbe:
    committed = False
    closed = 0
    def onCompleteFlow(self):
        try:
            if self.committed:
                grant()
                yield {"operation": "gui.questCommitted", "args": [], "kwargs": {}}
            yield {"operation": "gui.showMessage", "args": ["Quest receipt"], "kwargs": {}}
        finally:
            self.closed += 1
callbacks = CompletionFlowProbe()
)",
                   scope);
    auto callbacks = scope["callbacks"];
    CPythonOverrides::retain(quest, callbacks);
    struct OverrideOwner {
        std::shared_ptr<CQuest> quest;
        ~OverrideOwner() { CPythonOverrides::release(quest.get()); }
    } releaseOverride{quest};
    const auto conditions = loop->getConditionalTaskCount();
    for (bool committed : {false, true}) {
        callbacks.attr("committed") = committed;
        auto waiting = game->getContext()->spawnTask(player->checkQuestsAsync());
        expect_true(pumpHandlerUntil([&] { return !game->getGui()->getChildren().empty() || waiting.finished(); }) &&
                        !waiting.finished() && !game->getGui()->getChildren().empty(),
                    "quest completion must suspend at its receipt before individual cancellation");
        waiting.requestStop();
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while (!waiting.finished() && std::chrono::steady_clock::now() < deadline) {
            loop->runReady();
            game_async::waitForProgress();
        }
        bool cancelled = false;
        if (waiting.finished()) {
            try {
                waiting.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        expect_true(cancelled && game->getContext()->isActive() && game->getGui()->getChildren().empty(),
                    "individual quest cancellation must close its receipt while retaining the active context");
        expect_true(player->getCompletedQuests().contains(quest) == committed &&
                        player->getQuests().contains(quest) != committed && rewards == (committed ? 1 : 0),
                    "precommit cancellation must retain the quest, while committed rewards settle membership once");
        expect_true(quest->captures == (committed ? std::vector<bool>{true} : std::vector<bool>{}),
                    "only an explicitly committed cancellation may capture the completed journal");
    }
    auto unrelatedCommit = std::make_shared<bool>(false);
    auto isolated = CScriptHandler::createObjectFlow(quest, "onCompleteFlow", {}, game, unrelatedCommit);
    int wrongItemCommitRejections = 0;
    if (isolated) {
        try {
            isolated->markItemCommitted();
        } catch (const std::invalid_argument &) {
            ++wrongItemCommitRejections;
        }
        try {
            (void)isolated->commitCallback();
        } catch (const std::invalid_argument &) {
            ++wrongItemCommitRejections;
        }
    }
    expect_true(wrongItemCommitRejections == 2 && !*unrelatedCommit,
                "neither an item marker nor item movement capability may commit a quest reward");
    isolated.reset();
    player->checkQuests();
    expect_true(rewards == 1 && quest->captures == std::vector<bool>{true} && callbacks.attr("closed").cast<int>() == 2,
                "repeated completion checks must neither duplicate committed rewards nor retain cancelled generators");
    expect_true(loop->getConditionalTaskCount() == conditions,
                "cancelled quest receipts must release all conditional waits");
    game->getContext()->shutdown();
}

void test_player_quest_completion_ignores_reentry_and_captures_final_callback_state() {
    auto player = std::make_shared<CPlayer>();
    auto quest = std::make_shared<QuestLifecycleProbe>();
    quest->setTypeId("reentrantQuest");
    player->setQuests({quest});
    std::string journal_state = "active";
    quest->complete_callback = [&]() {
        expect_true(player->getQuests().contains(quest) && player->getCompletedQuests().empty(),
                    "completion callbacks should retain the existing active-quest timing");
        player->checkQuests();
        journal_state = "completed";
    };
    quest->capture_callback = [&]() {
        expect_true(journal_state == "completed" && player->getCompletedQuests().empty(),
                    "completion capture should observe callback changes before completed insertion");
    };

    CPlaytestTrace::configure(true, "", 100);
    player->checkQuests();
    player->checkQuests();
    int completion_records = 0;
    for (const auto &line : CPlaytestTrace::drain()) {
        const auto record = json::parse(line);
        if (record.value("event", std::string()) == "quest_completed") {
            completion_records++;
        }
    }
    CPlaytestTrace::configure(false, "", 100);

    expect_true(quest->check_count == 1 && quest->complete_count == 1 && completion_records == 1,
                "nested and repeated completion checks should run and trace one completion");
    expect_true(quest->captures == std::vector<bool>{true}, "completed quest journals should capture exactly once");
    expect_true(player->getQuests().empty() && player->getCompletedQuests().contains(quest),
                "reentrant completion should move the quest into the completed journal");
}

void test_player_quest_completion_accepts_cleared_active_set() {
    auto player = std::make_shared<CPlayer>();
    auto quest = std::make_shared<QuestLifecycleProbe>();
    player->setQuests({quest});
    quest->complete_callback = [&]() { player->setQuests({}); };

    player->checkQuests();
    player->checkQuests();

    expect_true(quest->complete_count == 1 && quest->captures == std::vector<bool>{true},
                "a callback clearing active quests should complete and capture safely once");
    expect_true(player->getQuests().empty() && player->getCompletedQuests().contains(quest),
                "clearing active quests during completion should preserve the current completed quest");
}

void test_player_quest_completion_skips_removed_snapshot_entries() {
    auto player = std::make_shared<CPlayer>();
    auto first = std::make_shared<QuestLifecycleProbe>();
    auto second = std::make_shared<QuestLifecycleProbe>();
    auto replacement = std::make_shared<QuestLifecycleProbe>();
    player->setQuests({first, second});
    if (*player->getQuests().begin() != first) {
        std::swap(first, second);
    }
    first->complete_callback = [&]() { player->setQuests({replacement}); };

    player->checkQuests();

    expect_true(first->complete_count == 1 && second->check_count == 0 && second->complete_count == 0,
                "quests removed by an earlier callback should be skipped in the original snapshot");
    expect_true(replacement->check_count == 0 && player->getQuests() == std::set<std::shared_ptr<CQuest>>{replacement},
                "replacement quests should wait for the next completion pass");
    player->checkQuests();
    expect_true(replacement->complete_count == 1 && player->getCompletedQuests().size() == 2,
                "the next pass should complete the replacement without restoring removed quests");

    auto removed_during_check = std::make_shared<QuestLifecycleProbe>();
    removed_during_check->check_callback = [&]() { player->setQuests({}); };
    player->setQuests({removed_during_check});
    player->checkQuests();
    expect_true(removed_during_check->complete_count == 0 && removed_during_check->captures.empty(),
                "a quest removed by its completion predicate should not receive completion callbacks");
}

void test_player_quest_completion_defers_new_quests_until_next_pass() {
    auto player = std::make_shared<CPlayer>();
    auto quest = std::make_shared<QuestLifecycleProbe>();
    auto next_quest = std::make_shared<QuestLifecycleProbe>();
    player->setQuests({quest});
    quest->complete_callback = [&]() {
        auto active = player->getQuests();
        active.insert(next_quest);
        player->setQuests(active);
        player->checkQuests();
    };

    player->checkQuests();
    expect_true(quest->complete_count == 1 && next_quest->check_count == 0,
                "quests added by a completion callback should wait even when the callback reenters checks");
    expect_true(player->getQuests() == std::set<std::shared_ptr<CQuest>>{next_quest},
                "new quest membership should survive completion of the original quest");
    player->checkQuests();
    player->checkQuests();
    expect_true(quest->complete_count == 1 && next_quest->complete_count == 1 && player->getQuests().empty(),
                "each original and newly added quest should complete exactly once across later passes");
}

void test_player_quest_completion_restores_guard_after_native_exceptions() {
    for (bool throw_in_predicate : {true, false}) {
        auto player = std::make_shared<CPlayer>();
        auto quest = std::make_shared<QuestLifecycleProbe>();
        player->setQuests({quest});
        bool first_attempt = true;
        auto fail_once = [&]() {
            if (std::exchange(first_attempt, false)) {
                throw std::runtime_error("quest lifecycle failure");
            }
        };
        if (throw_in_predicate) {
            quest->check_callback = fail_once;
        } else {
            quest->complete_callback = fail_once;
        }
        bool threw = false;
        try {
            player->checkQuests();
        } catch (const std::runtime_error &) {
            threw = true;
        }
        expect_true(threw && player->getQuests().contains(quest) && player->getCompletedQuests().empty(),
                    "failed native callbacks should retain the existing incomplete membership");

        player->checkQuests();
        player->checkQuests();
        expect_true(player->getQuests().empty() && player->getCompletedQuests().contains(quest),
                    "the RAII guard should permit retry after predicate and completion exceptions");
        expect_true(quest->complete_count == (throw_in_predicate ? 1 : 2) && quest->captures == std::vector<bool>{true},
                    "only the successful completion attempt should capture the completed journal");
    }
}

void test_player_capture_quest_journal_passes_membership_without_completing() {
    auto player = std::make_shared<CPlayer>();
    auto active = std::make_shared<QuestLifecycleProbe>();
    auto completed = std::make_shared<QuestLifecycleProbe>();
    player->setQuests({active});
    player->setCompletedQuests({completed});

    player->captureQuestJournal();

    expect_true(active->captures == std::vector<bool>{false} && completed->captures == std::vector<bool>{true},
                "journal capture should pass active and completed set membership to each quest");
    expect_true(active->check_count == 0 && completed->check_count == 0 && active->complete_count == 0 &&
                    completed->complete_count == 0,
                "saving or leaving a map should capture journals without driving completion predicates or rewards");
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
        victor->getBaseStats()->setStamina(11);
        victor->getBaseStats()->setStrength(13);
        victor->setLevel(3);
        victor->setHp(23);
        victor->setMana(13);
        auto defeated = add_test_creature(game, "unitTraceOutcomeDefeated", 1, 0);
        defeated->getBaseStats()->setStamina(9);
        defeated->getBaseStats()->setStrength(8);
        defeated->setLevel(2);
        defeated->setHp(6);
        defeated->setMana(4);
        auto second = add_test_creature(game, "unitTraceOutcomeSecond", 0, 1);
        second->getBaseStats()->setStamina(12);
        second->getBaseStats()->setStrength(14);
        second->setLevel(4);
        second->setHp(9);
        second->setMana(8);
        add_unit_loot(game, defeated, "unitTraceOutcomeLoot");

        const auto result = CFightHandler::fightManyResult(victor, {second, nullptr, defeated, second});
        const auto records = CPlaytestTrace::drain();

        bool found_started = false;
        bool found_finished = false;
        for (const auto &record : records) {
            const auto parsed = json::parse(record);
            if (parsed.value("event", std::string()) == "combat_started") {
                expect_true(!found_started, "one encounter should emit exactly one combat_started trace");
                found_started = true;
                const auto &attacker_state = parsed.at("attackerState");
                const auto &opponent_states = parsed.at("opponentStates");
                expect_true(attacker_state.size() == 7 && opponent_states.at(0).size() == 7 &&
                                opponent_states.at(1).size() == 7,
                            "combat-start snapshots should remain limited to identity, coordinates and resources");
                expect_true(attacker_state.at("object").dump() == parsed.at("attacker").dump() &&
                                parsed.at("attacker").value("name", std::string()) == victor->getName(),
                            "combat snapshots should preserve the existing attacker identity reference");
                expect_true(
                    attacker_state.at("coords").dump() == json{{"x", 0}, {"y", 0}, {"z", 0}}.dump() &&
                        attacker_state.at("hp").get<int>() == 23 && attacker_state.at("hpMax").get<int>() == 77 &&
                        attacker_state.at("mana").get<int>() == 13 && attacker_state.at("manaMax").get<int>() == 91 &&
                        attacker_state.at("level").get<int>() == 3,
                    "combat_started should capture actual damaged attacker resources before the first round");
                expect_true(opponent_states.size() == 2 && parsed.at("opponents").size() == 2,
                            "combat snapshots should include each sanitized opponent exactly once");
                expect_true(opponent_states.at(0).at("object").dump() == parsed.at("opponents").at(0).dump() &&
                                opponent_states.at(1).at("object").dump() == parsed.at("opponents").at(1).dump() &&
                                opponent_states.at(0).at("object").value("name", std::string()) ==
                                    defeated->getName() &&
                                opponent_states.at(1).at("object").value("name", std::string()) == second->getName(),
                            "combat snapshots should retain existing sanitized opponent references and order");
                expect_true(opponent_states.at(0).at("coords").dump() == json{{"x", 1}, {"y", 0}, {"z", 0}}.dump() &&
                                opponent_states.at(0).at("hp").get<int>() == 6 &&
                                opponent_states.at(0).at("hpMax").get<int>() == 63 &&
                                opponent_states.at(0).at("mana").get<int>() == 4 &&
                                opponent_states.at(0).at("manaMax").get<int>() == 56 &&
                                opponent_states.at(0).at("level").get<int>() == 2 &&
                                opponent_states.at(1).at("coords").dump() ==
                                    json{{"x", 0}, {"y", 1}, {"z", 0}}.dump() &&
                                opponent_states.at(1).at("hp").get<int>() == 9 &&
                                opponent_states.at(1).at("hpMax").get<int>() == 84 &&
                                opponent_states.at(1).at("mana").get<int>() == 8 &&
                                opponent_states.at(1).at("manaMax").get<int>() == 98 &&
                                opponent_states.at(1).at("level").get<int>() == 4,
                            "combat_started should retain pre-defeat resources for every actual opponent");
            }
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
        expect_true(found_started, "combat should emit a combat_started trace while tracing is enabled");
        expect_true(found_finished, "combat should emit a combat_finished trace while tracing is enabled");
        expect_true(result.outcome == CFightOutcome::AttackerVictory && !defeated->isAlive() && !second->isAlive(),
                    "resource snapshots must describe the start of an actual resolved multi-opponent fight");

        CPlaytestTrace::configure(false);
        auto untraced = add_test_creature(game, "unitTraceDisabledDefeated", 1, 1);
        const auto hp_before = victor->getHp();
        const auto mana_before = victor->getMana();
        const auto untraced_result = CFightHandler::fightManyResult(victor, {untraced});
        expect_true(CPlaytestTrace::records().empty(),
                    "disabled fight tracing should emit neither combat events nor resource snapshots");
        expect_true(untraced_result.outcome == result.outcome && !untraced->isAlive() && victor->getHp() == hp_before &&
                        victor->getMana() == mana_before,
                    "disabling snapshots should preserve the normal fight outcome and surviving resources");
    } catch (...) {
        CPlaytestTrace::configure(false);
        throw;
    }
    CPlaytestTrace::configure(false);
}

void testAsyncCombatTraceCapturesResourcesBeforeControllerSuspension() {
    auto game = load_empty_game();
    auto attacker = add_test_creature(game, "unitAsyncTraceAttacker");
    auto opponent = add_test_creature(game, "unitAsyncTraceDefender", 1, 0);
    attacker->getBaseStats()->setAgility(99);
    attacker->getBaseStats()->setStamina(3);
    attacker->setHp(7);
    attacker->setMana(4);
    opponent->setHp(6);
    const auto hpMax = attacker->getHpMax();
    const auto manaMax = attacker->getManaMax();
    auto probe = std::make_shared<AsyncTriggerProbe>();
    auto controller = std::make_shared<SuspendedTraceFightController>();
    controller->probe = probe;
    attacker->setFightController(controller);
    CPlaytestTrace::configure(true, "", 100, true);
    bool queued = false;
    vstd::event_loop<>::instance()->invoke([&queued] { queued = true; });
    auto fight = game->getContext()->spawnTask(CFightHandler::fightManyResultAsync(attacker, {opponent}));
    expect_true(!queued, "capturing combat-start resources must not pump unrelated work before controller await");
    expect_true(pumpHandlerUntil([&] { return !probe->entered.empty() || fight.finished(); }) && !fight.finished(),
                "the combat trace regression must suspend in its actual asynchronous controller");
    attacker->setHp(1);
    attacker->setMana(1);
    attacker->relocateWithoutMoveHooks(Coords(2, 0, 0));
    fight.requestStop();
    expect_true(pumpHandlerUntil([&] { return fight.finished(); }), "cancelled traced combat must release its frames");
    bool cancelled = false;
    if (fight.finished()) {
        try {
            (void)fight.get();
        } catch (const vstd::task_cancelled &) {
            cancelled = true;
        }
    }
    int starts = 0;
    for (const auto &line : CPlaytestTrace::drain()) {
        const auto record = json::parse(line);
        if (record.value("event", std::string()) == "combat_started") {
            ++starts;
            const auto &state = record.at("attackerState");
            expect_true(
                state.at("hp").get<int>() == 7 && state.at("mana").get<int>() == 4 &&
                    state.at("hpMax").get<int>() == hpMax && state.at("manaMax").get<int>() == manaMax &&
                    state.at("coords").dump() == CPlaytestTrace::coords(ZERO).dump() &&
                    record.at("opponentStates").at(0).at("hp").get<int>() == 6,
                "combat-start snapshots must retain original resources and coordinates across suspension/cancel");
        }
    }
    expect_true(cancelled && starts == 1 && controller->start_count == 1 && controller->end_count == 1,
                "cancelling a traced controller must retain one start record and clean its controller exactly once");
    CPlaytestTrace::configure(false);
    game->getContext()->shutdown();
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

void test_creature_scale_preserves_level_plus_sw_invariant() {
    // EPIC_03/STORY_01/SUBSTORY_03 regression guard: getScale() must stay equal to
    // getLevel() + getSw() so encounter power math survives the archetype migration.
    auto creature = std::make_shared<CCreature>();

    creature->setLevel(0);
    creature->setSw(0);
    expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                "getScale() should equal level + sw for a zeroed creature");

    creature->setLevel(3);
    creature->setSw(2);
    expect_true(creature->getScale() == 5, "getScale() should report level + sw for explicit values");
    expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                "getScale() should track concrete level and sw after both are set");

    creature->setSw(7);
    expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                "mutating sw alone should still leave getScale() == level + sw");

    creature->setLevel(10);
    expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                "mutating level alone should still leave getScale() == level + sw");

    creature->setSw(-4);
    expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                "getScale() should preserve the sum even when sw is negative");
}

std::shared_ptr<json> make_unit_creature_config(int sw) {
    auto config = CJsonUtil::from_string("{\"class\":\"CCreature\",\"properties\":{\"sw\":" + std::to_string(sw) +
                                             ",\"fightController\":{\"class\":\"CMonsterFightController\"},"
                                             "\"baseStats\":{\"class\":\"CStats\",\"properties\":{\"stamina\":10,"
                                             "\"strength\":5,\"mainStat\":\"strength\"}},"
                                             "\"levelStats\":{\"class\":\"CStats\",\"properties\":{\"stamina\":2}}}}",
                                         "unitCreatureSwConfig");
    expect_true(config != nullptr, "unit creature sw config json should parse for the RNG encounter regression test");
    return config;
}

void primeEncounterFixtureLevels(const std::shared_ptr<CGame> &game, int budget, int samples,
                                 const std::string &fixture) {
    nativeTestProfile().run("primeEncounterFixtureLevels", [&] {
        // These samples assert candidate membership, not XP progression. Prime copied configs after
        // checking their authored prototypes so every sample avoids replaying unrelated level unlocks.
        // The fresh-template XP regression and raw baseline remain separate and unmodified.
        auto handler = game->getObjectHandler();
        std::size_t primed = 0;
        for (const auto &type : handler->getAllSubTypes("CCreature")) {
            auto resolvedClass = handler->getType(handler->getClass(type));
            if (resolvedClass && resolvedClass->meta()->inherits("CPlayer")) {
                continue;
            }
            auto config = CJsonUtil::clone(handler->getConfig(type));
            (*config)["properties"]["exp"] = 0;
            (*config)["properties"]["level"] = budget;
            handler->registerConfig(type, config);
            ++primed;
        }
        std::cout << "[encounter-fixture] " << fixture << " templates=" << primed << " level=" << budget
                  << " samples=" << samples << " maxSamplingLevelUps=0\n";
    });
}

void test_rng_handler_scales_fresh_creatures_before_map_insertion() {
    auto game = load_empty_game();
    auto handler = game->getObjectHandler();
    for (const auto &type : handler->getAllSubTypes("CCreature")) {
        handler->unregisterConfig(type);
    }
    handler->registerConfig("unitScaledEncounter", make_unit_creature_config(1));
    auto prototype = game->createObject<CCreature>("unitScaledEncounter");
    expect_true(prototype && prototype->getHp() == 0 && prototype->getLevel() == 0,
                "the scaling regression must exercise an uninitialized creature template");

    CRngHandler rng(game);
    const auto previousRng = vstd::rng();
    vstd::rng().seed(7);
    const auto encounterRng = vstd::rng();
    std::multiset<int> expectedLevels;
    int expectedExperience = 0;
    for (int component : vstd::random_components(40, std::views::iota(1, 41))) {
        const int level = std::max(1, component - 1);
        expectedLevels.insert(level);
        expectedExperience += prototype->getExpForLevel(level);
    }
    expect_true(!expectedLevels.empty() && *expectedLevels.rbegin() > 1,
                "the fixed encounter seed must include a component that needs level scaling");
    vstd::rng() = encounterRng;
    std::multiset<int> actualLevels;
    int actualExperience = 0;
    for (const auto &creature : rng.getRandomEncounter(40)) {
        actualLevels.insert(creature->getLevel());
        actualExperience += creature->getExp();
        expect_true(creature->isAlive() && creature->getHp() == creature->getHpMax(),
                    "generated encounters must start alive at their scaled maximum hit points");
        const auto level = creature->getLevel();
        game->getMap()->addObject(creature);
        expect_true(creature->getLevel() == level,
                    "adding an initialized encounter to the map must preserve its scaled level");
    }
    vstd::rng() = previousRng;
    expect_true(actualLevels == expectedLevels, "encounter levels must match the allocated component powers");
    expect_true(actualExperience == expectedExperience, "encounter scaling must retain the allocated experience");
}

void test_rng_handler_excludes_noncombatants_from_encounters() {
    auto game = load_empty_game();
    auto handler = game->getObjectHandler();
    for (const auto &type : handler->getAllSubTypes("CCreature")) {
        handler->unregisterConfig(type);
    }
    const std::vector<std::shared_ptr<json>> noncombatants = {
        CJsonUtil::from_string("{\"class\":\"CCreature\"}", "neutralEncounter"),
        CJsonUtil::from_string("{\"class\":\"CCreature\",\"properties\":{\"sw\":1}}", "uncontrolledEncounter"),
        make_unit_creature_config(0),
        make_unit_creature_config(1),
    };
    (*noncombatants.back())["properties"]["npc"] = true;
    for (const auto &config : noncombatants) {
        handler->registerConfig("unitNoncombatant", config);
        CRngHandler rng(game);
        expect_true(rng.getRandomEncounter(1).empty(),
                    "neutral, uncontrolled, zero-power and NPC templates must not become hostile encounters");
    }
    handler->unregisterConfig("unitNoncombatant");
    handler->registerConfig("unitCombatant", make_unit_creature_config(1));
    CRngHandler rng(game);
    const auto encounter = rng.getRandomEncounter(1);
    expect_true(encounter.size() == 1 && (*encounter.begin())->getTypeId() == "unitCombatant",
                "a controlled positive-power monster must remain eligible for encounters");
}

void test_rng_handler_builds_encounters_from_concrete_creature_sw() {
    auto game = load_empty_game();
    auto objectHandler = game->getObjectHandler();

    // Register two creature archetypes carrying explicit, well-separated sw values. The empty game
    // already registers other CCreature subtypes, so these are added to (not isolated from) the
    // registry CRngHandler scans.
    struct Archetype {
        std::string type;
        int sw;
    };
    const std::vector<Archetype> archetypes = {
        {"unitRngSwLow", 1},
        {"unitRngSwHigh", 4},
    };

    for (const auto &archetype : archetypes) {
        objectHandler->registerConfig(archetype.type, make_unit_creature_config(archetype.sw));
        auto prototype = game->createObject<CCreature>(archetype.type);
        expect_true(prototype != nullptr, "registered unit creature archetype should construct");
        if (prototype) {
            expect_true(prototype->getSw() == archetype.sw,
                        "concrete creature should report the sw configured for its archetype");
        }
    }

    // Reconstruct the ground-truth power-table keys exactly the way CRngHandler's constructor does
    // (src/handler/CRngHandler.cpp:63-68): one key per registered CCreature subtype, taken from the
    // concrete creature's getSw(). Any encounter sw must be one of these real concrete keys.
    std::set<int> registeredCreatureSw;
    for (const std::string &type : objectHandler->getAllSubTypes("CCreature")) {
        auto prototype = game->createObject<CCreature>(type);
        if (prototype) {
            registeredCreatureSw.insert(prototype->getSw());
        }
    }

    // Deterministic ingestion proof: our two archetypes' concrete sw values are reachable keys.
    expect_true(registeredCreatureSw.contains(1),
                "CRngHandler power table should ingest the concrete sw of the low archetype");
    expect_true(registeredCreatureSw.contains(4),
                "CRngHandler power table should ingest the concrete sw of the high archetype");

    // Building the handler against the live game ingests every registered subtype's concrete getSw()
    // into the creature power table used to assemble encounters.
    primeEncounterFixtureLevels(game, 40, 64, "concrete-sw");
    CRngHandler rng_handler(game);

    for (int attempt = 0; attempt < 64; attempt++) {
        auto encounter = rng_handler.getRandomEncounter(40);
        for (const auto &creature : encounter) {
            expect_true(creature != nullptr, "encounter creatures should be non-null");
            if (!creature) {
                continue;
            }
            expect_true(creature->getLevel() == 40, "concrete-sw sampling must not replay fixture level-ups");
            // Encounter power compatibility: the post-scaling sum stays getScale() == level + sw.
            expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                        "scaled encounter creatures should keep getScale() == level + sw");
            // CRngHandler selects the creature from creaturePowerTable.equal_range(sw) where sw is a
            // table key (src/handler/CRngHandler.cpp:124-131); addExp scaling never mutates sw, so an
            // encounter creature's getSw() must be one of the registered concrete subtype keys.
            expect_true(registeredCreatureSw.contains(creature->getSw()),
                        "encounter creatures should retain a concrete registered-subtype sw used as the power key");
        }
    }

    for (const auto &archetype : archetypes) {
        objectHandler->unregisterConfig(archetype.type);
    }
}

// [EPIC_05][STORY_07][SUBSTORY_01] Random encounter candidates must contain only
// concrete spawnable creatures: race/class *archetype definitions* must never enter
// the CRngHandler creature power table. CCreatureRace/CCreatureClass are registered as
// CGameObject-derived definitions (src/plugin/NativePlugin.cpp:162-165), so
// getAllSubTypes("CCreature") -- which only returns a type whose resolved class
// meta()->inherits("CCreature") (src/handler/CObjectHandler.cpp:114-117) -- must exclude
// them. The CRngHandler constructor seeds creaturePowerTable solely from that
// enumeration (src/handler/CRngHandler.cpp:63-69), so a definition absent from the
// enumeration provably cannot become an encounter candidate. This regression registers
// definition configs alongside a real concrete creature and pins both: the definitions
// are excluded from the enumeration, while the concrete creature is included and the
// handler still assembles encounters made only of concrete creatures.
void test_rng_handler_excludes_archetype_definitions_from_encounters() {
    auto game = load_empty_game();
    auto objectHandler = game->getObjectHandler();

    // Configured archetype-definition entries: their declared class is the
    // CGameObject-derived definition type, NOT CCreature.
    const std::string raceDefId = "unitArchetypeRaceDefinition";
    const std::string classDefId = "unitArchetypeClassDefinition";
    const std::string concreteCreatureId = "unitArchetypeConcreteCreature";

    objectHandler->registerConfig(raceDefId, CJsonUtil::from_string("{\"class\":\"CCreatureRace\"}", raceDefId));
    objectHandler->registerConfig(classDefId, CJsonUtil::from_string("{\"class\":\"CCreatureClass\"}", classDefId));
    // A genuine concrete creature so the enumeration / power table is provably non-empty
    // and we can show definitions are excluded while real creatures are included.
    objectHandler->registerConfig(concreteCreatureId, make_unit_creature_config(2));

    // Sanity: the definition configs resolve to their CGameObject-derived definition
    // classes, which do NOT inherit CCreature -- the exact gate getAllSubTypes applies.
    expect_true(objectHandler->getClass(raceDefId) == "CCreatureRace",
                "race definition config should resolve to the CCreatureRace definition class");
    expect_true(objectHandler->getClass(classDefId) == "CCreatureClass",
                "class definition config should resolve to the CCreatureClass definition class");
    if (auto raceProto = objectHandler->getType("CCreatureRace")) {
        expect_true(!raceProto->meta()->inherits("CCreature"),
                    "CCreatureRace definition must not inherit CCreature so it stays out of encounters");
    }
    if (auto classProto = objectHandler->getType("CCreatureClass")) {
        expect_true(!classProto->meta()->inherits("CCreature"),
                    "CCreatureClass definition must not inherit CCreature so it stays out of encounters");
    }

    // The encounter enumeration (and therefore creaturePowerTable, which is seeded only
    // from it) must exclude the definitions and include the concrete creature.
    const std::vector<std::string> creatureSubTypes = objectHandler->getAllSubTypes("CCreature");
    std::set<std::string> creatureSubTypeSet(creatureSubTypes.begin(), creatureSubTypes.end());

    expect_true(!creatureSubTypeSet.contains(raceDefId),
                "getAllSubTypes(\"CCreature\") must exclude race archetype-definition entries");
    expect_true(!creatureSubTypeSet.contains(classDefId),
                "getAllSubTypes(\"CCreature\") must exclude class archetype-definition entries");
    expect_true(creatureSubTypeSet.contains(concreteCreatureId),
                "getAllSubTypes(\"CCreature\") must include the concrete spawnable creature");

    // Every enumerated candidate must construct as a real CCreature -- definitions cannot.
    for (const std::string &type : creatureSubTypes) {
        auto candidate = game->createObject<CCreature>(type);
        expect_true(candidate != nullptr, "every encounter candidate must construct as a concrete CCreature");
        if (candidate) {
            expect_true(candidate->meta()->inherits("CCreature"),
                        "every encounter candidate must inherit CCreature (no archetype definitions)");
        }
    }

    // Build the live handler: it seeds creaturePowerTable from the enumeration above, so
    // no definition can have entered it. Assembled encounters must be only real creatures.
    primeEncounterFixtureLevels(game, 40, 64, "archetype-exclusion");
    CRngHandler rng_handler(game);
    bool producedEncounter = false;
    for (int attempt = 0; attempt < 64; attempt++) {
        auto encounter = rng_handler.getRandomEncounter(40);
        for (const auto &creature : encounter) {
            expect_true(creature != nullptr, "encounter creatures should be non-null");
            if (!creature) {
                continue;
            }
            expect_true(creature->getLevel() == 40, "archetype-exclusion sampling must not replay fixture level-ups");
            producedEncounter = true;
            expect_true(creature->meta()->inherits("CCreature"),
                        "every assembled encounter creature must be a concrete CCreature");
            expect_true(creature->getType() != "CCreatureRace" && creature->getType() != "CCreatureClass",
                        "archetype definition types must never be assembled into an encounter");
        }
    }
    expect_true(producedEncounter,
                "the handler should assemble a non-empty encounter from the concrete creature population");

    objectHandler->unregisterConfig(raceDefId);
    objectHandler->unregisterConfig(classDefId);
    objectHandler->unregisterConfig(concreteCreatureId);
}

void test_rng_handler_captures_encounter_power_and_scale_baseline() {
    // EPIC_01/STORY_02/SUBSTORY_04 pre-migration baseline.
    //
    // The random-encounter machinery enumerates creature templates with
    // CObjectHandler::getAllSubTypes("CCreature") and keys its power table on the
    // concrete creature's getSw() (src/handler/CRngHandler.cpp:63-69, :124-131).
    // A later archetype migration must NOT let race/class *definition* types (which
    // do not exist yet) leak into that enumeration, and it must keep a defined sw on
    // every concrete monster template. This test records sw/level/getScale() and the
    // power-table participation for every concrete template as a reviewable artifact
    // and asserts only structural invariants the source guarantees today.
    auto game = load_empty_game();
    auto objectHandler = game->getObjectHandler();

    // Reconstruct the exact enumeration the RNG handler scans
    // (src/handler/CRngHandler.cpp:63). getAllSubTypes only returns a type when its
    // resolved config "class" constructs and meta()->inherits("CCreature") holds
    // (src/handler/CObjectHandler.cpp:104-119), which is the precise gate a migration
    // must not loosen for definition-only race/class types.
    const std::vector<std::string> creatureSubTypes = objectHandler->getAllSubTypes("CCreature");
    expect_true(!creatureSubTypes.empty(),
                "the normally-configured game should register at least one concrete CCreature template");

    struct CreatureBaseline {
        std::string type;
        int sw = 0;
        int level = 0;
        int scale = 0;
        bool inPowerTable = false;
    };

    // Deterministic ordering: getAllSubTypes already returns a sorted, de-duplicated
    // list (src/handler/CObjectHandler.cpp:61-63), so iterate it directly so the
    // emitted baseline table is stable across runs.
    std::vector<CreatureBaseline> baseline;
    for (const std::string &type : creatureSubTypes) {
        auto creature = game->createObject<CCreature>(type);
        // getAllSubTypes only yields constructible CCreature-inheriting templates, so
        // every concrete monster template must materialize.
        expect_true(creature != nullptr, "every concrete CCreature template should construct from the registry");
        if (!creature) {
            continue;
        }

        // Reject race/class-definition leakage structurally: anything the encounter
        // enumeration returns must still be a real creature, mirroring the
        // getAllSubTypes inherits gate (src/handler/CObjectHandler.cpp:115).
        expect_true(creature->meta()->inherits("CCreature"),
                    "encounter templates must inherit CCreature so race/class definitions cannot leak in");

        CreatureBaseline entry;
        entry.type = type;
        entry.sw = creature->getSw();
        entry.level = creature->getLevel();
        entry.scale = creature->getScale();
        entry.inPowerTable = !creature->meta()->inherits("CPlayer") && !creature->isNpc() &&
                             creature->getFightController() && entry.sw > 0;

        // Every concrete monster must preserve a defined sw/level pair, and getScale()
        // stays level + sw (src/object/CCreature.cpp:366), which the encounter power
        // math relies on across the migration.
        expect_true(entry.scale == entry.level + entry.sw,
                    "concrete template getScale() should equal getLevel() + getSw()");

        baseline.push_back(entry);
    }

    // Keep the baseline's encounter membership consistent with the eligible monster registry.
    std::unordered_multimap<int, std::string> creaturePowerTable;
    for (const auto &entry : baseline) {
        if (entry.inPowerTable) {
            creaturePowerTable.insert(std::make_pair(entry.sw, entry.type));
        }
    }
    expect_true(!creaturePowerTable.empty(),
                "the creature power table should be produced non-empty from concrete templates");
    expect_true(creaturePowerTable.size() ==
                    static_cast<std::size_t>(std::count_if(baseline.begin(), baseline.end(),
                                                           [](const auto &entry) { return entry.inPowerTable; })),
                "only eligible monster templates should contribute power-table entries");

    // Emit the deterministic, ordered baseline artifact for review.
    std::cout << "[SS04] encounter power/scale baseline (type sw level scale inPowerTable)\n";
    for (const auto &entry : baseline) {
        std::cout << "[SS04] " << entry.type << " sw=" << entry.sw << " level=" << entry.level
                  << " scale=" << entry.scale << " inPowerTable=" << (entry.inPowerTable ? "true" : "false") << "\n";
    }
    std::cout.flush();

    // Building the live handler must ingest the same enumeration without crashing and
    // must produce a usable, non-empty encounter source.
    CRngHandler rng_handler(game);
    std::set<int> baselineSw;
    for (const auto &entry : baseline) {
        if (entry.inPowerTable) {
            baselineSw.insert(entry.sw);
        }
    }
    bool producedEncounter = false;
    for (int attempt = 0; attempt < 64 && !producedEncounter; attempt++) {
        auto encounter = rng_handler.getRandomEncounter(40);
        for (const auto &creature : encounter) {
            if (!creature) {
                continue;
            }
            producedEncounter = true;
            // addExp scaling never mutates sw (src/handler/CRngHandler.cpp:135), so an
            // encounter creature's getSw() must remain a recorded baseline power key.
            expect_true(baselineSw.contains(creature->getSw()),
                        "encounter creatures should retain a concrete baseline-template sw used as the power key");
        }
    }
    expect_true(producedEncounter,
                "the baseline power table should be able to assemble a non-empty encounter without crashing");
}

// [EPIC_05][STORY_07][SUBSTORY_03] Compare deterministic encounter outputs.
//
// Acceptance: "Encounter generation remains equivalent under stable candidate/power
// constraints." The encounter RNG (vstd::rand -> a single time-seeded static
// std::mt19937_64) exposes NO seeding hook, so an exact sampled SEQUENCE cannot be
// pinned. Instead this guard pins the two things that ARE invariant of sampling order:
// the candidate SET (which sw power-buckets an encounter creature may be drawn from)
// and the power-budget constraint (the `it <= pow` filter in
// src/handler/CRngHandler.cpp:118 / :124). These follow directly from the source and
// must survive any future encounter-table refactor that keeps the same candidates and
// power semantics.
//
// Source contract being pinned:
//   * The constructor seeds creaturePowerTable with one entry per registered CCreature
//     subtype, keyed on the concrete creature's getSw() (CRngHandler.cpp:63-69).
//   * calculateRandomEncounter decomposes value via random_components and, for each
//     component `pow`, only considers power-table keys with `sw <= pow`, where
//     `pow <= value` (CRngHandler.cpp:116-124). So every assembled creature's sw key
//     is <= clamp(value, 0, 1000).
//   * Selection scales the creature with addExp(getExpForLevel(pow - sw)); addExp only
//     mutates exp/level, never sw (src/object/CCreature.cpp:80-88), so the assembled
//     creature's getSw() stays exactly the table key it was drawn from, and
//     getScale() stays getLevel() + getSw() (CCreature.cpp:369).
void test_rng_handler_encounter_candidates_stay_in_stable_power_buckets() {
    auto game = load_empty_game();
    auto objectHandler = game->getObjectHandler();

    // Two well-separated, deterministic power buckets added to the live registry. They
    // are added to (not isolated from) whatever the configured game already registers.
    const int kLowSw = 1;
    const int kHighSw = 9;
    const std::string lowId = "unitEncounterEquivLow";
    const std::string highId = "unitEncounterEquivHigh";
    objectHandler->registerConfig(lowId, make_unit_creature_config(kLowSw));
    objectHandler->registerConfig(highId, make_unit_creature_config(kHighSw));

    // Reconstruct the ground-truth creature power table EXACTLY as the constructor does
    // (CRngHandler.cpp:63-78): one sw bucket per registered concrete subtype, EXCLUDING
    // CPlayer-derived player templates. [EPIC_05][STORY_07][SUBSTORY_02] made the constructor skip
    // any candidate whose resolved class meta()->inherits("CPlayer") (res/config/monsters.json
    // registers real CPlayer templates such as Warrior/Sorcerer/Assasin), so the reconstructed
    // candidate set must apply the same exclusion to stay consistent with the live table.
    std::set<int> eligibleSwBuckets;
    for (const std::string &type : objectHandler->getAllSubTypes("CCreature")) {
        auto resolvedClass = objectHandler->getType(objectHandler->getClass(type));
        if (resolvedClass && resolvedClass->meta()->inherits("CPlayer")) {
            continue;
        }
        if (auto prototype = game->createObject<CCreature>(type)) {
            eligibleSwBuckets.insert(prototype->getSw());
        }
    }
    expect_true(eligibleSwBuckets.contains(kLowSw),
                "the low archetype's sw must register as an eligible encounter power bucket");
    expect_true(eligibleSwBuckets.contains(kHighSw),
                "the high archetype's sw must register as an eligible encounter power bucket");

    // (1) Candidate-set equivalence at a full power budget: across many samples every
    // assembled creature's sw must be a member of the eligible bucket set -- the
    // generator must never invent an sw key outside the registered candidate set, and
    // the post-scaling scale invariant must hold. Sampling order is irrelevant: this is a
    // set-membership comparison, not a sequence comparison.
    const int kFullBudget = 60;
    primeEncounterFixtureLevels(game, kFullBudget, 256, "full-power-buckets");
    auto rng_handler = nativeTestProfile().run("CRngHandler::CRngHandler", [&] { return CRngHandler(game); });
    bool producedFullEncounter = false;
    nativeTestProfile().run("encounter samples(full-budget)", [&] {
        for (int attempt = 0; attempt < 256; attempt++) {
            for (const auto &creature : rng_handler.getRandomEncounter(kFullBudget)) {
                if (!creature) {
                    continue;
                }
                expect_true(creature->getLevel() == kFullBudget,
                            "full-budget sampling must not replay fixture level-ups");
                producedFullEncounter = true;
                expect_true(eligibleSwBuckets.contains(creature->getSw()),
                            "every encounter creature's sw must be drawn from a registered eligible power bucket");
                expect_true(creature->getSw() <= kFullBudget,
                            "every encounter creature's sw must respect the requested power budget");
                expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                            "scaled encounter creatures must keep getScale() == level + sw");
            }
        }
    });
    expect_true(producedFullEncounter,
                "a full power budget should assemble at least one encounter from the eligible buckets");

    // (2) Power-constraint equivalence under a TIGHT budget: with a budget strictly below
    // the high bucket's sw, the `it <= pow` power filter provably excludes the high bucket
    // for every component (pow <= value < kHighSw). So the high archetype must NEVER appear
    // and every assembled creature's sw must be <= the tight budget. This is deterministic
    // regardless of which low bucket the RNG happens to sample.
    const int kTightBudget = kHighSw - 1; // 8: below the high bucket, so it is never eligible
    primeEncounterFixtureLevels(game, kTightBudget, 256, "tight-power-buckets");
    nativeTestProfile().run("encounter samples(tight-budget)", [&] {
        for (int attempt = 0; attempt < 256; attempt++) {
            for (const auto &creature : rng_handler.getRandomEncounter(kTightBudget)) {
                if (!creature) {
                    continue;
                }
                expect_true(creature->getLevel() == kTightBudget,
                            "tight-budget sampling must not replay fixture level-ups");
                expect_true(creature->getSw() <= kTightBudget,
                            "a tight power budget must exclude every bucket whose sw exceeds the budget");
                expect_true(creature->getSw() != kHighSw,
                            "the high power bucket must never be sampled when the budget is below its sw");
                expect_true(creature->getType() != highId,
                            "the high archetype must never be assembled under a sub-threshold power budget");
            }
        }
    });

    // (3) Empty-encounter equivalence: a clamped-to-zero (or non-positive) budget leaves
    // random_components with nothing to decompose, so no candidate is ever drawn. This
    // boundary is fully deterministic and order-independent.
    expect_true(rng_handler.getRandomEncounter(0).empty(),
                "a zero power budget must produce an empty encounter regardless of the candidate set");
    expect_true(rng_handler.getRandomEncounter(-25).empty(),
                "a non-positive power budget clamps to zero and must produce an empty encounter");

    objectHandler->unregisterConfig(lowId);
    objectHandler->unregisterConfig(highId);
}

// [EPIC_08][STORY_05][SUBSTORY_01] Associated-class metadata: future-gated encounter
// scale hook. CCreatureRace.associatedClasses models D&D-inspired associated classes
// (a class that reinforces the race's natural role), and CRngHandler's
// classifyClassAssociation/scaleEncounterPower hook lets the encounter power table
// DISTINGUISH associated from non-associated pairings. Balance is design-gated: the
// multipliers behind scaleEncounterPower are pinned to the neutral value 1, so the
// hook must be the identity for every classification and the encounter scale output
// must stay bit-identical to the pre-hook math for all existing content (empty
// metadata => zero effect). This test proves both halves of that acceptance.
void test_rng_handler_distinguishes_associated_classes_with_neutral_scale() {
    using ClassAssociation = CRngHandler::ClassAssociation;

    // --- Capability (metadata): a race configured with associatedClasses reports the
    // distinction for class ids and for class objects (configured-identity semantics).
    auto race = std::make_shared<CCreatureRace>();
    race->setAssociatedClasses({"mageClass"});

    expect_true(race->isAssociatedClass("mageClass"), "a race should report a listed class id as associated");
    expect_true(!race->isAssociatedClass("bruteClass"), "a race should report an unlisted class id as non-associated");
    expect_true(!race->isAssociatedClass(std::string()), "an empty class id should never be associated");

    auto mageClass = std::make_shared<CCreatureClass>();
    mageClass->setTypeId("mageClass");
    auto bruteClass = std::make_shared<CCreatureClass>();
    bruteClass->setTypeId("bruteClass");
    expect_true(race->isAssociatedClass(mageClass), "a class object should match by its configured typeId");
    expect_true(!race->isAssociatedClass(bruteClass), "an off-role class object should not match");
    auto namedOnlyClass = std::make_shared<CCreatureClass>();
    namedOnlyClass->setName("mageClass");
    expect_true(race->isAssociatedClass(namedOnlyClass),
                "a class with no typeId should fall back to its name, matching configured-identity semantics");
    expect_true(!race->isAssociatedClass(std::shared_ptr<CCreatureClass>()), "a null class is never associated");

    // --- Capability (hook input): the encounter hook derives the right distinction
    // from a creature's race/class pairing.
    expect_true(CRngHandler::classifyClassAssociation(nullptr) == ClassAssociation::NoArchetype,
                "a null creature carries no association to weigh");
    auto creature = std::make_shared<CCreature>();
    expect_true(CRngHandler::classifyClassAssociation(creature) == ClassAssociation::NoArchetype,
                "a legacy creature (no race, no class) carries no association to weigh");
    creature->setRace(race);
    expect_true(CRngHandler::classifyClassAssociation(creature) == ClassAssociation::NoArchetype,
                "a race-only creature has no race/class pairing to classify");
    creature->setCreatureClass(mageClass);
    expect_true(CRngHandler::classifyClassAssociation(creature) == ClassAssociation::Associated,
                "a class listed in the race's associatedClasses should classify as Associated");
    creature->setCreatureClass(bruteClass);
    expect_true(CRngHandler::classifyClassAssociation(creature) == ClassAssociation::NonAssociated,
                "a class missing from the race's associatedClasses should classify as NonAssociated");
    auto emptyMetadataRace = std::make_shared<CCreatureRace>();
    creature->setRace(emptyMetadataRace);
    creature->setCreatureClass(mageClass);
    expect_true(CRngHandler::classifyClassAssociation(creature) == ClassAssociation::NonAssociated,
                "a race with default-empty associatedClasses should treat every class as non-associated");

    // --- Neutrality (design-gated): the hook is the identity for EVERY classification
    // and power, so the constructor's power-table key provably equals the raw getSw()
    // no matter how a creature classifies (initial migration balance unchanged).
    for (int power : {0, 1, 2, 4, 9, 40, 1000}) {
        expect_true(CRngHandler::scaleEncounterPower(power, ClassAssociation::NoArchetype) == power,
                    "legacy creatures must keep their raw power as the encounter power key");
        expect_true(CRngHandler::scaleEncounterPower(power, ClassAssociation::Associated) == power,
                    "the associated-class multiplier must stay neutral until the balance design is approved");
        expect_true(CRngHandler::scaleEncounterPower(power, ClassAssociation::NonAssociated) == power,
                    "the non-associated-class multiplier must stay neutral until the balance design is approved");
    }

    // --- Neutrality (existing content): for every encounter candidate the configured
    // game registers, the hooked key the constructor computes equals the raw getSw(),
    // so the creature power table is identical to the pre-hook build. Reconstructs the
    // candidate set exactly as the constructor does (src/handler/CRngHandler.cpp),
    // including the CPlayer exclusion.
    auto game = load_empty_game();
    auto objectHandler = game->getObjectHandler();

    std::set<int> rawSwKeys;
    for (const std::string &type : objectHandler->getAllSubTypes("CCreature")) {
        auto resolvedClass = objectHandler->getType(objectHandler->getClass(type));
        if (resolvedClass && resolvedClass->meta()->inherits("CPlayer")) {
            continue;
        }
        auto prototype = game->createObject<CCreature>(type);
        if (!prototype) {
            continue;
        }
        const int hookedKey =
            CRngHandler::scaleEncounterPower(prototype->getSw(), CRngHandler::classifyClassAssociation(prototype));
        expect_true(hookedKey == prototype->getSw(),
                    "every existing encounter candidate's hooked power key must equal its raw getSw()");
        rawSwKeys.insert(prototype->getSw());
    }

    // The live handler (built with the hook in place) must still assemble encounters
    // exclusively from the raw concrete sw buckets, exactly as before the hook.
    primeEncounterFixtureLevels(game, 40, 64, "neutral-associated-class-hook");
    CRngHandler rng_handler(game);
    bool producedEncounter = false;
    for (int attempt = 0; attempt < 64; attempt++) {
        for (const auto &sampled : rng_handler.getRandomEncounter(40)) {
            if (!sampled) {
                continue;
            }
            expect_true(sampled->getLevel() == 40, "neutral-hook sampling must not replay fixture level-ups");
            producedEncounter = true;
            expect_true(rawSwKeys.contains(sampled->getSw()),
                        "encounter creatures must still be drawn from the raw concrete sw power buckets");
            expect_true(sampled->getScale() == sampled->getLevel() + sampled->getSw(),
                        "the neutral hook must preserve getScale() == level + sw for encounter creatures");
        }
    }
    expect_true(producedEncounter, "the hooked power table should still assemble non-empty encounters");
}

std::shared_ptr<json> make_unit_player_config(int sw) {
    auto config = CJsonUtil::from_string("{\"class\":\"CPlayer\",\"properties\":{\"sw\":" + std::to_string(sw) + "}}",
                                         "unitPlayerSwConfig");
    expect_true(config != nullptr, "unit player sw config json should parse for the RNG player-exclusion test");
    return config;
}

// [EPIC_05][STORY_07][SUBSTORY_02] Exclude player templates from random monster candidates.
//
// getAllSubTypes("CCreature") legitimately includes CPlayer templates because CPlayer inherits
// CCreature (src/object/CPlayer.h:24, registered via register_type<CPlayer, CCreature, ...> in
// src/plugin/NativePlugin.cpp). The CRngHandler constructor seeds creaturePowerTable from that
// enumeration (src/handler/CRngHandler.cpp:63-78), so without a filter a player template could be
// assembled into a random encounter. The fix skips any candidate whose resolved class
// meta()->inherits("CPlayer") -- the same inheritance test getAllSubTypes applies for its CCreature
// gate (src/handler/CObjectHandler.cpp:115) -- while leaving genuine monster candidates and their sw
// power buckets unchanged. This regression registers a CPlayer template alongside two concrete
// monster templates and asserts: (1) the player template is NEVER assembled across many samples,
// (2) the monster templates still appear, and (3) the monster sw power buckets are unchanged.
void test_rng_handler_excludes_player_templates_from_encounters() {
    auto game = load_empty_game();
    auto objectHandler = game->getObjectHandler();

    const std::string playerTemplateId = "unitPlayerTemplate";
    const int kMonsterLowSw = 2;
    const int kMonsterHighSw = 5;
    const std::string monsterLowId = "unitPlayerExclusionMonsterLow";
    const std::string monsterHighId = "unitPlayerExclusionMonsterHigh";

    objectHandler->registerConfig(playerTemplateId, make_unit_player_config(3));
    objectHandler->registerConfig(monsterLowId, make_unit_creature_config(kMonsterLowSw));
    objectHandler->registerConfig(monsterHighId, make_unit_creature_config(kMonsterHighSw));

    // Sanity: the player template config resolves to CPlayer and CPlayer inherits CCreature, so it
    // is genuinely part of getAllSubTypes("CCreature") -- the exact reason it must be filtered out of
    // the encounter candidate population rather than relying on it being absent.
    expect_true(objectHandler->getClass(playerTemplateId) == "CPlayer",
                "player template config should resolve to the CPlayer class");
    if (auto playerProto = objectHandler->getType("CPlayer")) {
        expect_true(playerProto->meta()->inherits("CCreature"),
                    "CPlayer must inherit CCreature so the player template legitimately enters getAllSubTypes");
        expect_true(playerProto->meta()->inherits("CPlayer"),
                    "the CPlayer prototype must report inheriting CPlayer for the exclusion gate");
    }

    const std::vector<std::string> creatureSubTypes = objectHandler->getAllSubTypes("CCreature");
    std::set<std::string> creatureSubTypeSet(creatureSubTypes.begin(), creatureSubTypes.end());
    expect_true(creatureSubTypeSet.contains(playerTemplateId),
                "getAllSubTypes(\"CCreature\") should still include the player template (CPlayer inherits CCreature)");
    expect_true(creatureSubTypeSet.contains(monsterLowId),
                "getAllSubTypes(\"CCreature\") should include the low monster template");
    expect_true(creatureSubTypeSet.contains(monsterHighId),
                "getAllSubTypes(\"CCreature\") should include the high monster template");

    // Ground-truth monster power buckets: the sw of every NON-player concrete candidate, built the
    // way the (fixed) constructor seeds creaturePowerTable -- i.e. excluding CPlayer-derived configs.
    // The two registered monsters must contribute their sw buckets, and no player-only bucket may
    // exist that is not also a monster bucket.
    std::set<int> monsterSwBuckets;
    for (const std::string &type : creatureSubTypes) {
        auto resolvedClass = objectHandler->getType(objectHandler->getClass(type));
        if (resolvedClass && resolvedClass->meta()->inherits("CPlayer")) {
            continue;
        }
        if (auto prototype = game->createObject<CCreature>(type)) {
            monsterSwBuckets.insert(prototype->getSw());
        }
    }
    expect_true(monsterSwBuckets.contains(kMonsterLowSw),
                "the low monster's sw must remain an eligible encounter power bucket");
    expect_true(monsterSwBuckets.contains(kMonsterHighSw),
                "the high monster's sw must remain an eligible encounter power bucket");

    // The exclusive high-sw bucket guarantees a deterministic "monsters are still selected" proof:
    // sw == kMonsterHighSw (5) is occupied ONLY by monsterHighId -- no real monsters.json template
    // reaches that bucket (their sw is 1 or 2). So any encounter creature whose sw is kMonsterHighSw
    // is provably the registered high monster, identified by its config key via getTypeId()
    // (set in CObjectHandler::_createObject -- the class name lives in getType(), the config id in
    // getTypeId(), src/handler/CObjectHandler.cpp:91).
    expect_true(monsterSwBuckets.count(kMonsterHighSw) > 0,
                "the exclusive high-sw bucket must belong solely to the registered high monster");
    bool highBucketIsExclusive = true;
    for (const std::string &type : creatureSubTypes) {
        if (type == monsterHighId) {
            continue;
        }
        auto resolvedClass = objectHandler->getType(objectHandler->getClass(type));
        if (resolvedClass && resolvedClass->meta()->inherits("CPlayer")) {
            continue;
        }
        if (auto prototype = game->createObject<CCreature>(type)) {
            if (prototype->getSw() == kMonsterHighSw) {
                highBucketIsExclusive = false;
            }
        }
    }
    expect_true(highBucketIsExclusive,
                "no other monster template may share the high monster's sw bucket for the determinism proof");

    primeEncounterFixtureLevels(game, 60, 256, "player-exclusion");
    auto rng_handler = nativeTestProfile().run("CRngHandler::CRngHandler", [&] { return CRngHandler(game); });

    bool sawRegisteredMonster = false;
    bool producedEncounter = false;
    nativeTestProfile().run("encounter samples(player-exclusion)", [&] {
        for (int attempt = 0; attempt < 256; attempt++) {
            for (const auto &creature : rng_handler.getRandomEncounter(60)) {
                if (!creature) {
                    continue;
                }
                expect_true(creature->getLevel() == 60, "player-exclusion sampling must not replay fixture level-ups");
                producedEncounter = true;

                // (1) A player template must NEVER be assembled into a random encounter. The
                // load-bearing guard is the meta-inheritance check: a filtered CPlayer template can
                // never construct as a CPlayer-derived instance. getType() carries the resolved class
                // name (src/core/CSerialization.cpp:391), so it must never be CPlayer either.
                expect_true(creature->getType() != "CPlayer",
                            "random encounters must never select a CPlayer-classed template");
                expect_true(!creature->meta()->inherits("CPlayer"),
                            "no assembled encounter creature may be a CPlayer-derived player template");

                // (3) Every assembled creature's sw must remain one of the unchanged monster power
                // buckets -- the player filter must not perturb monster sw selection.
                expect_true(monsterSwBuckets.contains(creature->getSw()),
                            "encounter creatures must keep an unchanged registered monster sw power bucket");
                expect_true(creature->getScale() == creature->getLevel() + creature->getSw(),
                            "scaled encounter creatures must keep getScale() == level + sw");

                // (2) Genuine monster candidates are still selected. Any creature drawn from the
                // exclusive high-sw bucket is provably the registered high monster; confirm its config
                // id via getTypeId() (getType() is the class name "CCreature", not the config key).
                if (creature->getSw() == kMonsterHighSw) {
                    expect_true(creature->getTypeId() == monsterHighId,
                                "the exclusive high-sw bucket must only ever yield the registered high monster");
                    sawRegisteredMonster = true;
                }
            }
        }
    });

    // (2) Genuine monster candidates are still selected after the player exclusion.
    expect_true(producedEncounter,
                "the handler should still assemble non-empty encounters after excluding player templates");
    expect_true(sawRegisteredMonster,
                "a registered monster template must still be selectable as an encounter candidate");

    objectHandler->unregisterConfig(playerTemplateId);
    objectHandler->unregisterConfig(monsterLowId);
    objectHandler->unregisterConfig(monsterHighId);
}

// READ-ONLY source-of-truth inventory for later CCreature/CPlayer migration tickets
// ([EPIC_01][STORY_01][SUBSTORY_01]). Loads a normally-configured game (CGameLoader::loadGame
// registers every res/config CONFIG file -- including res/config/monsters.json -- via
// initConfigurations, and loads global plugins via initScriptHandler; see
// src/core/CLoader.cpp:1191-1199,1230-1244) and enumerates the concrete CCreature subtypes exactly
// as the engine sees them. For each concrete id it records the resolved class name from
// CObjectHandler::getClass (src/handler/CObjectHandler.cpp:122-131) and whether that class resolves
// to CPlayer or plain CCreature using the same meta()->inherits(...) test that
// CObjectHandler::getAllSubTypes itself applies (src/handler/CObjectHandler.cpp:104-120). The
// inventory is emitted to stdout (the captured source-of-truth artifact) and asserted to be
// produced on a loaded game without crashing. This test excludes no ids and mutates no config.
void test_creature_subtype_inventory_is_enumerable_on_loaded_game() {
    auto game = load_empty_game();
    auto objectHandler = game->getObjectHandler();

    // getAllSubTypes("CCreature") returns every registered subtype whose configured class inherits
    // CCreature; because CPlayer inherits CCreature (src/object/CPlayer.h:24), player templates are
    // legitimately part of this set and must be classified, not excluded.
    std::vector<std::string> subTypes = objectHandler->getAllSubTypes("CCreature");

    // Deterministic, ordered inventory: sort the concrete ids so the captured list is stable across
    // runs / unordered-registry iteration. We intentionally do not de-duplicate or filter.
    std::sort(subTypes.begin(), subTypes.end());

    expect_true(!subTypes.empty(),
                "loaded game should expose at least one concrete CCreature subtype for the inventory");

    struct InventoryEntry {
        std::string id;
        std::string resolvedClass;
        bool resolvesToPlayer = false;
        bool resolvesToCreature = false;
    };
    std::vector<InventoryEntry> inventory;
    inventory.reserve(subTypes.size());

    std::cout << "[creature-subtype-inventory] CCreature subtypes on loaded game: " << subTypes.size() << "\n";

    for (const std::string &type : subTypes) {
        InventoryEntry entry;
        entry.id = type;
        entry.resolvedClass = objectHandler->getClass(type);

        // Classify via the type prototype's meta inheritance, mirroring getAllSubTypes' own check.
        // A type already present in this list inherits CCreature by construction; whether it ALSO
        // inherits CPlayer distinguishes player templates from plain creatures. Fall back to the
        // resolved class name when no prototype is registered for the class so the row is still
        // emitted (no id is silently dropped).
        if (auto prototype = objectHandler->getType(entry.resolvedClass)) {
            entry.resolvesToPlayer = prototype->meta()->inherits("CPlayer");
            entry.resolvesToCreature = prototype->meta()->inherits("CCreature");
        } else {
            entry.resolvesToPlayer = (entry.resolvedClass == "CPlayer");
            entry.resolvesToCreature = true;
        }

        expect_true(!entry.resolvedClass.empty(),
                    "every enumerated CCreature subtype should resolve to a non-empty class name");
        expect_true(entry.resolvesToCreature, "every enumerated CCreature subtype should classify as a CCreature");

        const char *classification = entry.resolvesToPlayer ? "CPlayer" : "CCreature";
        std::cout << "[creature-subtype-inventory]   id=" << entry.id << " class=" << entry.resolvedClass
                  << " resolvesTo=" << classification << "\n";

        inventory.push_back(std::move(entry));
    }

    expect_true(inventory.size() == subTypes.size(),
                "inventory should record exactly one row per enumerated CCreature subtype id");
}

void test_tooltip_handler_exposes_present_archetypes_without_duplicate_descriptions() {
    // EPIC_07/STORY_02/SUBSTORY_01: creature tooltips should surface the race and
    // class archetypes only when they are present, and never repeat a description
    // that is already shown.
    auto legacy = std::make_shared<CCreature>();
    legacy->setLabel("Wandering Rat");
    legacy->setDescription("A small, mangy rat.");

    const auto legacyTooltip = CTooltipHandler::buildTooltip(legacy);
    expect_true(legacyTooltip.find("Wandering Rat") != std::string::npos,
                "legacy creature tooltips should still show the creature label");
    expect_true(legacyTooltip.find("A small, mangy rat.") != std::string::npos,
                "legacy creature tooltips should still show the creature description");

    auto race = std::make_shared<CCreatureRace>();
    race->setLabel("Orc");
    race->setDescription("Brutish and strong.");
    auto creatureClass = std::make_shared<CCreatureClass>();
    creatureClass->setLabel("Warrior");
    creatureClass->setDescription("Master of arms.");

    auto archetyped = std::make_shared<CCreature>();
    archetyped->setLabel("Grommash");
    archetyped->setDescription("A scarred veteran.");
    archetyped->setRace(race);
    archetyped->setCreatureClass(creatureClass);

    const auto archetypeTooltip = CTooltipHandler::buildTooltip(archetyped);
    const auto count_occurrences = [](const std::string &haystack, const std::string &needle) {
        int count = 0;
        for (std::size_t pos = haystack.find(needle); pos != std::string::npos;
             pos = haystack.find(needle, pos + needle.size())) {
            count++;
        }
        return count;
    };

    expect_true(count_occurrences(archetypeTooltip, "Orc") == 1,
                "present race archetypes should appear exactly once in the tooltip");
    expect_true(count_occurrences(archetypeTooltip, "Brutish and strong.") == 1,
                "present race descriptions should appear exactly once in the tooltip");
    expect_true(count_occurrences(archetypeTooltip, "Warrior") == 1,
                "present class archetypes should appear exactly once in the tooltip");
    expect_true(count_occurrences(archetypeTooltip, "Master of arms.") == 1,
                "present class descriptions should appear exactly once in the tooltip");
    expect_true(count_occurrences(archetypeTooltip, "A scarred veteran.") == 1,
                "the creature description should never be duplicated by archetype lines");

    // A shared description across the creature and its archetypes must not be echoed
    // multiple times.
    auto sharedDescRace = std::make_shared<CCreatureRace>();
    sharedDescRace->setLabel("Human");
    sharedDescRace->setDescription("A scarred veteran.");
    auto shared = std::make_shared<CCreature>();
    shared->setLabel("Reginald");
    shared->setDescription("A scarred veteran.");
    shared->setRace(sharedDescRace);

    const auto sharedTooltip = CTooltipHandler::buildTooltip(shared);
    expect_true(count_occurrences(sharedTooltip, "A scarred veteran.") == 1,
                "an archetype sharing the creature description must not duplicate that line");
    expect_true(count_occurrences(sharedTooltip, "Human") == 1,
                "the race label should still appear when only its description is a duplicate");

    // Creatures without archetypes must not emit any archetype lines.
    auto noArchetype = std::make_shared<CCreature>();
    noArchetype->setLabel("Plain Creature");
    noArchetype->setDescription("Nothing special.");
    const auto plainTooltip = CTooltipHandler::buildTooltip(noArchetype);
    expect_true(plainTooltip == "Plain Creature\nNothing special.",
                "creatures without archetypes should not gain any archetype lines");
}

class ScriptFlowNativeObjectTypes {
  public:
    ScriptFlowNativeObjectTypes() : modules(pybind11::module_::import("sys").attr("modules")) {
        hadGameModule = modules.contains("_game");
        if (hadGameModule) {
            previous = modules["_game"];
        }
        auto module = pybind11::reinterpret_borrow<pybind11::module_>(PyImport_AddModule("_handlerFlowNativeObjects"));
        if (!pybind11::hasattr(module, "CGameObject")) {
            pybind11::class_<CGameObject, std::shared_ptr<CGameObject>>(module, "CGameObject");
        }
        modules["_game"] = module;
    }

    ~ScriptFlowNativeObjectTypes() {
        if (hadGameModule) {
            modules["_game"] = previous;
        } else {
            modules.attr("pop")("_game", pybind11::none());
        }
    }

  private:
    pybind11::dict modules;
    pybind11::object previous;
    bool hadGameModule = false;
};

pybind11::object nativeFlowObject(const std::shared_ptr<CGameObject> &object) { return pybind11::cast(object); }

std::unique_ptr<CScriptFlow> waitCallbackFlow(const std::shared_ptr<CGame> &game, pybind11::dict &scope,
                                              pybind11::tuple arguments) {
    scope["arguments"] = std::move(arguments);
    pybind11::exec(R"(
events = []

def nativeWait():
    events.append('entered')
    try:
        answer = yield {'operation': 'gui.waitMilliseconds', 'args': arguments, 'kwargs': {}}
        events.append(answer)
    except RuntimeError as failure:
        events.append(str(failure))
    finally:
        events.append('closed')
)",
                   scope);
    return game->getScriptHandler()->createCallbackFlow(scope["nativeWait"].cast<pybind11::function>(), game);
}

void testWaitStateSnapshotsPreserveRemainingDurationWithoutRebasingLiveTime() {
    auto now = std::make_shared<CWaitState::Clock::time_point>();
    auto game = makeWindowlessFightGame();
    game->getObjectHandler()->registerType("CGameObject", [] { return std::make_shared<CGameObject>(); });
    game->getObjectHandler()->registerType("CWaitState",
                                           [now] { return std::make_shared<CWaitState>([now] { return *now; }); });
    auto state = game->createObject<CWaitState>("CWaitState");
    state->setRemainingMilliseconds(4000);
    auto coordinator = game->createObject<CGameObject>("CGameObject");
    coordinator->setObjectProperty("pendingWait", state);
    const auto lease = state->tryStart();
    expect_true(lease.has_value(), "a fresh wait state must acquire its native lease");
    if (!lease) {
        game->getContext()->shutdown();
        return;
    }
    *now += std::chrono::microseconds(1500001);
    auto snapshot = CSerialization::serializeExpected(coordinator);
    expect_true(snapshot.has_value(), "a coordinator-owned running wait must serialize through object properties");
    if (snapshot) {
        const auto &properties = snapshot->at("properties").at("pendingWait").at("properties");
        expect_true(properties.at("remainingMilliseconds").is_number_integer() &&
                        properties.at("remainingMilliseconds").get<int>() == 2500 && !properties.contains("deadline") &&
                        !properties.contains("running") && !properties.contains("activeLease"),
                    "a save must ceil the remaining millisecond without recording a deadline or active lease");
        *now += std::chrono::hours(48);
        auto decoded = CSerialization::deserializeExpected<std::shared_ptr<CGameObject>>(game, *snapshot);
        expect_true(decoded.has_value(), "a paused wait snapshot must deserialize through its registered native type");
        if (decoded) {
            auto restored = std::dynamic_pointer_cast<CWaitState>((*decoded)->getObjectProperty("pendingWait"));
            expect_true(restored && restored != state && !restored->isRunning() &&
                            restored->getRemainingMilliseconds() == 2500,
                        "restoration must retain saved remaining time without catching up for time spent offline");
            if (restored) {
                const auto resumed = restored->tryStart();
                *now += std::chrono::milliseconds(2499);
                expect_true(resumed && restored->getRemainingMilliseconds() == 1 && !restored->complete(*resumed),
                            "a resumed wait must use the saved remainder and never complete one millisecond early");
                *now += std::chrono::milliseconds(1);
                expect_true(resumed && restored->complete(*resumed) && !restored->isRunning(),
                            "the resumed wait must complete only when its actual remaining duration elapses");
            }
        }
    }
    state->pause(*lease);
    state->setRemainingMilliseconds(4000);
    const auto saving = state->tryStart();
    *now += std::chrono::milliseconds(1000);
    auto map = game->getMap();
    map->setObjectProperty("pendingWait", state);
    map->setProperty("unitUnserializableWaitProbe", std::function<void()>([] {}));
    expect_true(!CMapLoader::saveWithResult(map, "unit-wait-unserializable"),
                "an unsupported snapshot property must fail before writing a save");
    *now += std::chrono::milliseconds(1000);
    expect_true(saving && state->isRunning() && state->getRemainingMilliseconds() == 2000,
                "a failed save must not pause, extend, or restart the live wait deadline");
    if (saving) {
        state->pause(*saving);
    }
    game->getContext()->shutdown();
}

void testWaitStateRejectsInvalidDurationsMutationsAndDuplicateLeases() {
    std::fputs("[handler-test] BODY testWaitStateRejectsInvalidDurationsMutationsAndDuplicateLeases\n", stderr);
    std::fflush(stderr);
    auto now = std::make_shared<CWaitState::Clock::time_point>();
    auto state = std::make_shared<CWaitState>([now] { return *now; });
    for (int invalid : {-1, 60001}) {
        bool rejected = false;
        try {
            state->setRemainingMilliseconds(invalid);
        } catch (const std::invalid_argument &) {
            rejected = true;
        }
        expect_true(rejected && state->getRemainingMilliseconds() == 0,
                    "wait durations outside the closed native range must be rejected without mutation");
    }
    state->setRemainingMilliseconds(60000);
    const auto lease = state->tryStart();
    expect_true(lease && !state->tryStart(), "a native wait holder must admit only one active waiter");
    bool mutationRejected = false;
    try {
        state->setRemainingMilliseconds(5);
    } catch (const std::logic_error &) {
        mutationRejected = true;
    }
    *now += std::chrono::microseconds(1);
    expect_true(mutationRejected && state->getRemainingMilliseconds() == 60000,
                "running waits must reject mutation and ceil partial milliseconds");
    state->invalidateForMapBindingChange();
    *now += std::chrono::seconds(20);
    expect_true(lease && state->isInvalidated(*lease) && !state->isRunning() &&
                    state->getRemainingMilliseconds() == 60000 && !state->tryStart() && !state->complete(*lease),
                "an invalidated wait must freeze immediately and retain its lease until the old waiter unwinds");
    if (lease) {
        state->pause(*lease);
    }
    const auto next = state->tryStart();
    if (lease) {
        state->pause(*lease);
    }
    expect_true(next && state->isRunning(), "cleanup from an old lease must not pause a newer wait");
    if (next) {
        state->pause(*next);
    }
    state->setRemainingMilliseconds(0);
    const auto zero = state->tryStart();
    expect_true(zero && state->complete(*zero), "a zero-duration wait must complete without adding time");
}

void testScriptWaitFlowCompletesAndRejectsInvalidObjectArguments() {
    std::fputs("[handler-test] BODY testScriptWaitFlowCompletesAndRejectsInvalidObjectArguments\n", stderr);
    std::fflush(stderr);
    ScriptFlowNativeObjectTypes types;
    std::fputs("[handler-test] SCRIPT_WAIT setup=native-types-ready\n", stderr);
    std::fflush(stderr);
    auto game = makeWindowlessFightGame();
    std::fputs("[handler-test] SCRIPT_WAIT setup=game-ready\n", stderr);
    std::fflush(stderr);
    auto foreign = makeWindowlessFightGame();
    std::fputs("[handler-test] SCRIPT_WAIT setup=foreign-ready\n", stderr);
    std::fflush(stderr);
    for (int variant = 0; variant < 9; ++variant) {
        std::fprintf(stderr, "[handler-test] SCRIPT_WAIT variant=%d phase=begin\n", variant);
        std::fflush(stderr);
        auto state = std::make_shared<CWaitState>();
        state->setGame(variant == 1 ? foreign : game);
        auto arguments = pybind11::make_tuple(nativeFlowObject(state));
        if (variant == 2) {
            auto item = std::make_shared<CItem>();
            item->setGame(game);
            arguments = pybind11::make_tuple(nativeFlowObject(item));
        } else if (variant == 3) {
            arguments = pybind11::make_tuple(0);
        } else if (variant == 4) {
            arguments = pybind11::tuple();
        } else if (variant == 5) {
            arguments = pybind11::make_tuple(nativeFlowObject(state), 0);
        }
        if (variant >= 6) {
            vstd::event_loop<>::instance()->invoke([game, foreign, state, variant] {
                if (variant == 6) {
                    auto original = game->getMap();
                    auto replacement = std::make_shared<CMap>();
                    replacement->setGame(game);
                    game->setMap(replacement);
                    game->setMap(original);
                } else if (variant == 7) {
                    game->getContext()->advanceTransitionGeneration();
                } else {
                    state->setGame(foreign);
                }
            });
        }
        std::fprintf(stderr, "[handler-test] SCRIPT_WAIT variant=%d phase=arguments-ready\n", variant);
        std::fflush(stderr);
        pybind11::dict scope;
        auto pending = game->getContext()->spawnTask(
            game->getGuiHandler()->runScriptFlowAsync(waitCallbackFlow(game, scope, std::move(arguments))));
        std::fprintf(stderr, "[handler-test] SCRIPT_WAIT variant=%d phase=spawned\n", variant);
        std::fflush(stderr);
        expect_true(pumpHandlerUntil([&] { return pending.finished(); }), "a native wait flow must settle");
        bool cancelled = false;
        if (pending.finished()) {
            try {
                pending.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        std::fprintf(stderr, "[handler-test] SCRIPT_WAIT variant=%d phase=settled\n", variant);
        std::fflush(stderr);
        auto events = scope["events"].cast<pybind11::list>();
        const auto validEvents =
            variant >= 6
                ? cancelled && events.size() == 2 && events[1].cast<std::string>() == "closed"
                : !cancelled && events.size() == 3 && events[2].cast<std::string>() == "closed" &&
                      (variant == 0 ? (pybind11::isinstance<pybind11::bool_>(events[1]) && events[1].cast<bool>())
                                    : pybind11::isinstance<pybind11::str>(events[1]));
        expect_true(validEvents && !state->isRunning(),
                    "only a same-session wait-state token may complete the native UI wait operation");
        scope.clear();
        std::fprintf(stderr, "[handler-test] SCRIPT_WAIT variant=%d phase=cleared\n", variant);
        std::fflush(stderr);
    }
    game->getContext()->shutdown();
    foreign->getContext()->shutdown();
}

void testScriptWaitSurvivesFailedSaveResourceBindingWithoutDispatchingMapChanges() {
    auto game = makeWindowlessFightGame();
    auto map = game->getMap();
    auto context = game->getContext();
    const auto generation = context->captureTransitionGeneration();
    const auto publishedEpoch = game->getMapBindingEpoch();
    game->getObjectHandler()->registerType("CMap", [] { return std::make_shared<CMap>(); });
    int candidateWaits = 0;
    game->getObjectHandler()->registerType("CWaitState", [&candidateWaits] {
        ++candidateWaits;
        return std::make_shared<CWaitState>();
    });
    auto loop = vstd::event_loop<>::instance();
    const auto pending = loop->getPendingTaskCount();
    const auto delayed = loop->getDelayedTaskCount();
    auto other = std::make_shared<CMap>();
    other->setGame(game);
    for (int repeat = 0; repeat < 128; ++repeat) {
        game->setMap(other);
        game->setMap(other);
        game->setMap(map);
    }
    expect_true(game->getMapBindingEpoch() == publishedEpoch + 256 &&
                    loop->getPendingTaskCount() == pending && loop->getDelayedTaskCount() == delayed &&
                    context->isTransitionGenerationCurrent(generation),
                "maps without wait observers must add no queued callbacks, delays, or transition generations");
    const auto resourceEpoch = game->getMapBindingEpoch();
    auto now = std::make_shared<CWaitState::Clock::time_point>();
    auto state = std::make_shared<CWaitState>([now] { return *now; });
    state->setGame(game);
    state->setRemainingMilliseconds(4000);
    const auto lease = state->tryStart();
    game->connect("mapBindingChanged", state, "invalidateForMapBindingChange");
    *now += std::chrono::milliseconds(1000);
    const auto document = std::make_shared<json>();
    (*document)["class"] = "CMap";
    auto &properties = (*document)["properties"];
    properties["mapName"] = "";
    properties["objects"] = json::array();
    properties["tiles"] = json::array();
    properties["triggers"] = json::array();
    properties["invalidWait"] = {{"class", "CWaitState"}, {"properties", {{"remainingMilliseconds", 60001}}}};
    const auto envelope = CSaveFormat::buildEnvelope(document, "");
    const auto slot =
        "native-wait-invalid-load-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    const auto resources = game->getResourcesProvider();
    bool persisted = envelope && resources->save(CSaveFormat::primaryPath(slot), CJsonUtil::to_string(*envelope, -1));
    expect_true(persisted, "the invalid candidate must reach the real saved-map resource loading transaction");
    if (persisted) {
        CGameLoader::loadSavedGame(game, slot);
    }
    *now += std::chrono::milliseconds(1000);
    const auto unchanged = lease && candidateWaits == 1 && game->getMap() == map &&
                           game->getMapBindingEpoch() == resourceEpoch &&
                           context->isTransitionGenerationCurrent(generation) && state->isRunning() &&
                           !state->isInvalidated(*lease) && state->getRemainingMilliseconds() == 2000;
    expect_true(unchanged,
                "failed-load temporary map bindings must preserve the live wait and published scene generation");
    game->disconnect("mapBindingChanged", state, "invalidateForMapBindingChange");
    if (lease) {
        state->pause(*lease);
    }
    if (persisted && unchanged) {
        std::error_code ignored;
        std::filesystem::remove(resources->getPath(CSaveFormat::primaryPath(slot)), ignored);
    }
    context->shutdown();
}

void testScriptWaitCancellationAndMapBindingLossFreezeRemainingTime() {
    ScriptFlowNativeObjectTypes types;
    auto loop = vstd::event_loop<>::instance();
    for (int variant = 0; variant < 4; ++variant) {
        auto game = makeWindowlessFightGame();
        auto context = game->getContext();
        auto original = game->getMap();
        auto now = std::make_shared<CWaitState::Clock::time_point>();
        auto state = std::make_shared<CWaitState>([now] { return *now; });
        state->setGame(game);
        state->setRemainingMilliseconds(60000);
        const auto delayed = loop->getDelayedTaskCount();
        pybind11::dict scope;
        auto pending = context->spawnTask(game->getGuiHandler()->runScriptFlowAsync(
            waitCallbackFlow(game, scope, pybind11::make_tuple(nativeFlowObject(state)))));
        expect_true(state->isRunning() && !pending.finished() && loop->getDelayedTaskCount() == delayed + 1,
                    "one native wait must schedule exactly one cancellable delay without pumping work");
        *now += std::chrono::milliseconds(1234);
        game->setMap(original);
        expect_true(state->isRunning() && state->getRemainingMilliseconds() == 58766,
                    "a no-op map binding must not pause an active wait");
        if (variant >= 2) {
            auto replacement = std::make_shared<CMap>();
            replacement->setGame(game);
            game->setMap(replacement);
            if (variant == 3) {
                game->setMap(original);
            }
            *now += std::chrono::milliseconds(2000);
            expect_true(!state->isRunning() && state->getRemainingMilliseconds() == 58766 && !state->tryStart(),
                        "map loss and an away/back round trip must synchronously freeze and invalidate the lease");
        }
        if (variant == 1) {
            context->shutdown();
        } else {
            pending.requestStop();
        }
        expect_true(pumpHandlerUntil([&] { return pending.finished(); }), "a cancelled wait must settle promptly");
        bool cancelled = false;
        if (pending.finished()) {
            try {
                pending.get();
            } catch (const vstd::task_cancelled &) {
                cancelled = true;
            }
        }
        auto events = scope["events"].cast<pybind11::list>();
        const auto available = state->tryStart();
        expect_true(cancelled && events.size() == 2 && events[1].cast<std::string>() == "closed" && available &&
                        loop->getDelayedTaskCount() == delayed,
                    "cancellation must close the flow, release its lease and timer, and never report success");
        if (available) {
            state->pause(*available);
        }
        scope.clear();
        context->shutdown();
    }
}

void testSyncScriptWaitReleasesTheFinalGameOwner() {
    auto loop = vstd::event_loop<>::instance();
    auto game = makeWindowlessFightGame();
    auto context = game->getContext();
    auto handler = game->getGuiHandler();
    auto state = std::make_shared<CWaitState>();
    state->setGame(game);
    state->setRemainingMilliseconds(60000);
    std::weak_ptr<CGame> lifetime = game;
    bool callbackRan = false;
    bool released = false;
    bool waitingWhenReleased = false;
    loop->invoke([&] {
        callbackRan = true;
        waitingWhenReleased = state->isRunning();
        game.reset();
        released = lifetime.expired();
        if (!released) {
            context->shutdown();
        }
    });
    const auto completed = handler->waitMilliseconds(state);
    expect_true(callbackRan && waitingWhenReleased && released && lifetime.expired() && !completed &&
                    !context->isActive() && !state->isRunning(),
                "a native wait must release its final game owner before awaiting and pause during shutdown");
    context->shutdown();
}

} // namespace

class SaveAdmissionVisitProbe : public CGameObject {
    V_META(SaveAdmissionVisitProbe, CGameObject,
           V_PROPERTY(SaveAdmissionVisitProbe, int, serializationVisit, getSerializationVisit, setSerializationVisit))
  public:
    int visits = 0;
    int getSerializationVisit() {
        ++visits;
        throw std::runtime_error("intentional admission graph stop before resource writes");
    }
    void setSerializationVisit(int) {}
};

class SaveAdmissionClosingPanel : public CGamePanel {
  public:
    std::function<void()> callback;
    void close() override {
        if (auto current = std::exchange(callback, {})) {
            current();
        }
    }
};

void testSaveAdmissionRejectsBeforeQuestAndGraphWork() {
    auto game = makeWindowlessFightGame();
    auto map = game->getMap();
    map->setMapName("empty");
    auto player = add_test_player(game);
    auto quest = std::make_shared<QuestLifecycleProbe>();
    quest->setGame(game);
    player->setQuests({quest});
    CTypes::register_type<SaveAdmissionVisitProbe, CGameObject>();
    auto probe = std::make_shared<SaveAdmissionVisitProbe>();
    probe->setGame(game);
    map->setObjectProperty("saveAdmissionProbe", probe);
    auto operation = map->tryBeginUnsafeOperation();
    expect_true(operation.has_value(), "an explicit native operation must acquire inactive admission");
    if (operation) {
        expect_true(!CMapLoader::saveWithResult(map, "unit-save-admission-no-write") && quest->captures.empty() &&
                        probe->visits == 0,
                    "busy save admission must reject before quest capture or any reflected graph getter");
        operation->finish();
        expect_true(!CMapLoader::saveWithResult(map, "unit-save-admission-no-write") && quest->captures.size() == 1 &&
                        probe->visits == 1,
                    "released admission must reach real capture/serialization; the test getter then prevents a write");
        auto afterFailure = map->tryBeginUnsafeOperation();
        expect_true(afterFailure.has_value(), "failed serialization must release its snapshot capability");
        if (afterFailure) {
            afterFailure->finish();
        }
    }
    game->getContext()->shutdown();
}

void testSaveAdmissionOwnersMovesAndSnapshots() {
    auto game = makeWindowlessFightGame();
    auto map = game->getMap();
    auto first = map->tryBeginUnsafeOperation();
    auto second = map->tryBeginUnsafeOperation();
    expect_true(first && second && !map->tryBeginSaveSnapshot(),
                "every independent unsafe owner must exclude snapshots");
    if (first && second) {
        auto moved = std::move(*first);
        first.reset();
        second->finish();
        expect_true(moved.isCurrent() && !map->tryBeginSaveSnapshot(),
                    "moving an owner must transfer exactly one admission hold without quarantining its source");
        moved.finish();
        moved.finish();
        auto snapshot = map->tryBeginSaveSnapshot();
        expect_true(snapshot.has_value() && !map->tryBeginUnsafeOperation() && !map->tryBeginSaveSnapshot(),
                    "a live snapshot must exclude reentrant mutation and another snapshot without holding callbacks");
        snapshot.reset();
        auto resumed = map->tryBeginUnsafeOperation();
        expect_true(resumed.has_value(), "snapshot teardown must permit later opted-in work");
        if (resumed) {
            resumed->finish();
        }
    }
    {
        auto abandoned = map->tryBeginUnsafeOperation();
        expect_true(abandoned.has_value(), "an unsettled owner fixture must acquire admission");
    }
    expect_true(!map->tryBeginSaveSnapshot() && !map->tryBeginUnsafeOperation(),
                "an owner destroyed without a receipt settlement must quarantine rather than silently permit saves");
    game->getContext()->shutdown();
}

void testSaveAdmissionSurvivesMapAndGameOwnerChanges() {
    auto game = makeWindowlessFightGame();
    auto oldMap = game->getMap();
    auto operation = oldMap->tryBeginUnsafeOperation();
    auto replacement = std::make_shared<CMap>();
    replacement->setGame(game);
    game->setMap(replacement);
    expect_true(operation && !operation->isCurrent() && !oldMap->tryBeginSaveSnapshot() &&
                    !replacement->tryBeginSaveSnapshot(),
                "map binding changes must invalidate ownership while keeping old and replacement snapshots blocked");
    if (operation) {
        operation->finish();
    }
    expect_true(replacement->tryBeginSaveSnapshot().has_value(),
                "known-complete interruption settlement must release session admission for the replacement map");
    auto detachedOperation = replacement->tryBeginUnsafeOperation();
    std::weak_ptr<CGame> weakGame = game;
    game.reset();
    expect_true(
        weakGame.expired() && detachedOperation && !detachedOperation->isCurrent() &&
            !replacement->tryBeginSaveSnapshot(),
        "a lease must retain its map marker without keeping the final game owner alive or allowing fallback saves");
    if (detachedOperation) {
        detachedOperation->finish();
    }
    expect_true(replacement->tryBeginSaveSnapshot().has_value(),
                "a detached map with no unsafe owner must retain compatibility snapshot admission");
}

void testSaveAdmissionQuarantineRequiresVerifiedInstall() {
    auto game = load_empty_game();
    auto original = game->getMap();
    add_test_player(game);
    const auto resources = game->getResourcesProvider();
    const auto slot =
        "native-save-admission-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    const bool saved = CMapLoader::saveWithResult(original, slot);
    expect_true(saved, "the recovery fixture must create an actual quiescent native checkpoint");
    if (!saved) {
        game->getContext()->shutdown();
        return;
    }
    auto operation = original->tryBeginUnsafeOperation();
    expect_true(operation.has_value(), "the recovery fixture must acquire the operation it quarantines");
    if (!operation) {
        game->getContext()->shutdown();
        return;
    }
    if (operation) {
        operation->quarantine();
    }
    CGameLoader::loadSavedGame(game, slot + "-missing");
    expect_true(game->getMap() == original && !original->tryBeginSaveSnapshot(),
                "a failed primary/backup load must preserve quarantine and the active map");
    auto candidate = CMapLoader::loadSavedMap(game, slot);
    expect_true(candidate && candidate != original && game->getMap() == original,
                "candidate-only restore must not install or settle admission");
    if (!candidate) {
        game->getContext()->shutdown();
        return;
    }
    game->setMap(candidate);
    expect_true(!candidate->tryBeginSaveSnapshot(), "manual candidate installation must not clear session quarantine");

    auto gui = std::make_shared<WindowlessFightTestGui>();
    gui->setGame(game);
    game->setGui(gui);
    auto panel = std::make_shared<SaveAdmissionClosingPanel>();
    panel->setGame(game);
    gui->addChild(panel);
    bool reentrantSaveRejected = false;
    bool reentrantOperationRejected = false;
    std::weak_ptr<CGame> weakGame = game;
    panel->callback = [&, weakGame] {
        if (auto owner = weakGame.lock()) {
            reentrantSaveRejected = !owner->getMap()->tryBeginSaveSnapshot();
            reentrantOperationRejected = !owner->getMap()->tryBeginUnsafeOperation();
            owner->getContext()->advanceTransitionGeneration();
        }
    };
    CGameLoader::loadSavedGame(game, slot);
    expect_true(
        reentrantSaveRejected && reentrantOperationRejected && !game->getMap()->tryBeginSaveSnapshot(),
        "verified installation callbacks must stay excluded and generation supersession must retain quarantine");

    CGameLoader::loadSavedGame(game, slot);
    auto restored = game->getMap();
    const bool recovered =
        restored != original && restored != candidate && restored->tryBeginSaveSnapshot().has_value();
    expect_true(
        recovered && !original->tryBeginSaveSnapshot(),
        "only verified installation may clear session quarantine; the old partially mutated map stays quarantined");
    auto active = restored->tryBeginUnsafeOperation();
    CGameLoader::loadSavedGame(game, slot);
    expect_true(active && game->getMap() == restored && !restored->tryBeginSaveSnapshot(),
                "verified recovery must not load through or clear another active unsafe owner");
    if (active) {
        active->finish();
    }
    const bool corruptedPrimary = resources->save(CSaveFormat::primaryPath(slot), std::string("{}"));
    auto backupOperation = restored->tryBeginUnsafeOperation();
    if (backupOperation) {
        backupOperation->quarantine();
    }
    CGameLoader::loadSavedGame(game, slot);
    const bool backupRecovered =
        corruptedPrimary && game->getMap() != restored && game->getMap()->tryBeginSaveSnapshot().has_value();
    expect_true(backupRecovered, "a verified backup installation must be an eligible quarantine recovery checkpoint");
    if (recovered && backupRecovered && reentrantSaveRejected && reentrantOperationRejected) {
        for (const auto &relative : {CSaveFormat::primaryPath(slot), CSaveFormat::backupPath(slot)}) {
            const auto path = resources->getPath(relative);
            if (!path.empty()) {
                std::filesystem::remove(path);
            }
        }
    }
    game->getContext()->shutdown();
}

class NativeSavePolicyObjectProbe : public CMapObject {
  public:
    int creates = 0;
    bool observed = false;
    void onCreate(std::shared_ptr<CGameEvent>) override {
        ++creates;
        observed = getMap()->getBoolProperty("guardNativeEncounterSaves");
    }
};

void testAuthoredNativeSavePolicyIsStrictAndPrecedesObjects() {
    const std::vector<std::optional<json>> declarations{std::nullopt, json(false),  json(true),    json(nullptr),
                                                        json(1),      json("true"), json::array(), json::object()};
    for (std::size_t index = 0; index < declarations.size(); ++index) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        map->setBoolProperty("guardNativeEncounterSaves", true);
        auto probe = std::make_shared<NativeSavePolicyObjectProbe>();
        game->getObjectHandler()->registerType("NativeSavePolicyObjectProbe", [probe] { return probe; });
        json properties = json::object();
        if (declarations[index]) {
            properties["guardNativeEncounterSaves"] = *declarations[index];
        }
        json object = {{"type", "NativeSavePolicyObjectProbe"},
                       {"name", "nativePolicyObject"},
                       {"x", 0},
                       {"y", 0},
                       {"width", 32},
                       {"height", 32}};
        json layer = {{"type", "objectgroup"}, {"properties", {{"level", "0"}}}, {"objects", json::array({object})}};
        auto document = std::make_shared<json>(json{{"properties", properties}, {"layers", json::array({layer})}});
        bool rejected = false;
        try {
            CMapLoader::loadFromTmx(map, document);
        } catch (const std::runtime_error &error) {
            rejected =
                std::string(error.what()).find("guardNativeEncounterSaves must be a boolean") != std::string::npos;
        }
        const bool valid = index < 3;
        const bool expected = index == 2;
        expect_true(
            valid ? (!rejected && probe->creates == 1 && probe->observed == expected &&
                     map->getBoolProperty("guardNativeEncounterSaves") == expected)
                  : (rejected && probe->creates == 0 && map->getObjects().empty()),
            "absent/false/true authored policy must precede object hooks; explicit non-booleans reject loading");
        game->getContext()->shutdown();
    }
}

void testVerifiedRestoreReappliesAuthoritativeNativeSavePolicy() {
    for (int mode = 0; mode < 4; ++mode) {
        auto game = load_empty_game();
        auto original = game->getMap();
        original->setMapName("test");
        add_test_player(game);
        auto authored =
            std::const_pointer_cast<json>(game->getConfigurationProvider()->getConfiguration("maps/test/map.json"));
        expect_true(authored && authored->is_object(), "the native restore fixture requires the authored test map");
        if (!authored || !authored->is_object()) {
            game->getContext()->shutdown();
            continue;
        }
        // The provider owns mutable parsed JSON in this context's private cache; resource files stay untouched.
        auto &properties = (*authored)["properties"];
        if (!properties.is_object()) {
            properties = json::object();
        }
        properties.erase("guardNativeEncounterSaves");
        if (mode != 0) {
            properties["guardNativeEncounterSaves"] = mode == 3 ? json("false") : json(mode == 2);
        }
        original->setBoolProperty("guardNativeEncounterSaves", mode != 2);
        const auto slot = "native-authored-save-policy-" + std::to_string(mode) + "-" +
                          std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
        const bool saved = CMapLoader::saveWithResult(original, slot);
        expect_true(saved, "authoritative policy restore must use an actual native checkpoint");
        auto unsafe = original->tryBeginUnsafeOperation();
        expect_true(saved && unsafe.has_value(), "the restore fixture must own the quarantine it attempts to recover");
        if (!saved || !unsafe) {
            game->getContext()->shutdown();
            continue;
        }
        unsafe->quarantine();
        CGameLoader::loadSavedGame(game, slot);
        const bool restored = game->getMap() != original;
        const bool policyRestored =
            mode == 3 ? (!restored && !original->tryBeginSaveSnapshot())
                      : (restored && game->getMap()->getBoolProperty("guardNativeEncounterSaves") == (mode == 2) &&
                         game->getMap()->tryBeginSaveSnapshot().has_value());
        expect_true(policyRestored, "restore must override saved ad-hoc values from authored absent/false/true policy "
                                    "and reject malformed policy");
        if (policyRestored) {
            auto resources = game->getResourcesProvider();
            for (const auto &relative : {CSaveFormat::primaryPath(slot), CSaveFormat::backupPath(slot)}) {
                const auto path = resources->getPath(relative);
                if (!path.empty()) {
                    std::filesystem::remove(path);
                }
            }
        }
        game->getContext()->shutdown();
    }
}

class VerifiedResumePolicyProbe : public CMapObject {
  public:
    int creates = 0;
    std::string observed;
    void onCreate(std::shared_ptr<CGameEvent>) override {
        ++creates;
        observed = getMap()->getStringProperty("verifiedLoadResumeReceiver");
    }
};

void testVerifiedLoadResumePolicyIsStrictAndPrecedesObjects() {
    const std::vector<std::optional<json>> declarations{std::nullopt,
                                                        json(""),
                                                        json("resumeReceiver"),
                                                        json(nullptr),
                                                        json(true),
                                                        json(1),
                                                        json::array(),
                                                        json::object(),
                                                        json(std::string(257, 'x')),
                                                        json(std::string("bad\0name", 8))};
    for (std::size_t index = 0; index < declarations.size(); ++index) {
        auto game = makeWindowlessFightGame();
        auto map = game->getMap();
        map->setStringProperty("verifiedLoadResumeReceiver", "savedAdHocReceiver");
        auto probe = std::make_shared<VerifiedResumePolicyProbe>();
        game->getObjectHandler()->registerType("VerifiedResumePolicyProbe", [probe] { return probe; });
        json properties = json::object();
        if (declarations[index]) {
            properties["verifiedLoadResumeReceiver"] = *declarations[index];
        }
        json object = {{"type", "VerifiedResumePolicyProbe"},
                       {"name", "resumePolicyProbe"},
                       {"x", 0},
                       {"y", 0},
                       {"width", 32},
                       {"height", 32}};
        json layer = {{"type", "objectgroup"}, {"objects", json::array({object})}};
        bool rejected = false;
        try {
            CMapLoader::loadFromTmx(
                map, std::make_shared<json>(json{{"properties", properties}, {"layers", json::array({layer})}}));
        } catch (const std::runtime_error &error) {
            rejected = std::string(error.what()).find("verifiedLoadResumeReceiver") != std::string::npos;
        }
        const bool valid = index < 3;
        const auto expected = index == 2 ? "resumeReceiver" : "";
        expect_true(valid ? (!rejected && probe->creates == 1 && probe->observed == expected)
                          : (rejected && probe->creates == 0 && map->getObjects().empty()),
                    "resume policy must be an authored bounded string before object hooks; absent/empty disables it");
        game->getContext()->shutdown();
    }
}

struct VerifiedResumeState {
    std::weak_ptr<CGame> game;
    int calls = 0;
    bool snapshotAvailable = false;
    bool unsafeAvailable = false;
};

struct VerifiedResumeFixture {
    std::shared_ptr<CGame> game = load_empty_game();
    std::shared_ptr<VerifiedResumeState> state = std::make_shared<VerifiedResumeState>();
    std::shared_ptr<CResourcesProvider> resources = game->getResourcesProvider();
    std::string slot;
    bool ready = false;

    VerifiedResumeFixture() {
        game->getMap()->setMapName("test");
        state->game = game;
        auto gui = std::make_shared<WindowlessFightTestGui>();
        gui->setGame(game);
        game->setGui(gui);
        add_test_player(game);
        pybind11::dict scope;
        scope["__name__"] = "verified_resume_probe";
        scope["observe"] = pybind11::cpp_function([shared = state] {
            ++shared->calls;
            if (auto owner = shared->game.lock()) {
                auto map = owner->getMap();
                shared->snapshotAvailable = map->tryBeginSaveSnapshot().has_value();
                auto unsafe = map->tryBeginUnsafeOperation();
                shared->unsafeAvailable = unsafe.has_value();
                if (unsafe) {
                    unsafe->finish();
                }
            }
        });
        pybind11::exec(R"(
class Receiver:
    def resumeAfterVerifiedLoadFlow(self):
        observe()
        if False:
            yield None
)",
                       scope);
        const pybind11::object receiverType = scope["Receiver"];
        game->getObjectHandler()->registerType("VerifiedLoadReceiverProbe", [receiverType] {
            auto receiver = std::make_shared<CMapObject>();
            CPythonOverrides::retain(receiver, receiverType());
            return receiver;
        });
        auto receiver = game->createObject<CMapObject>("VerifiedLoadReceiverProbe");
        receiver->setName("resumeReceiver");
        game->getMap()->addObject(receiver);
        // Change only this fixture context's parsed configuration cache, never resource files.
        auto authored =
            std::const_pointer_cast<json>(game->getConfigurationProvider()->getConfiguration("maps/test/map.json"));
        expect_true(authored && authored->is_object(), "resume fixture needs the authored test-map configuration");
        if (!authored || !authored->is_object()) {
            return;
        }
        if (!(*authored)["properties"].is_object()) {
            (*authored)["properties"] = json::object();
        }
        (*authored)["properties"]["verifiedLoadResumeReceiver"] = "resumeReceiver";
        game->getMap()->setStringProperty("verifiedLoadResumeReceiver", "savedAdHocReceiver");
        slot = "native-verified-resume-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
        ready = CMapLoader::saveWithResult(game->getMap(), slot);
        expect_true(ready, "resume fixture must use an actual native save");
    }

    void cleanup(bool successful) {
        if (successful && !slot.empty()) {
            for (const auto &relative : {CSaveFormat::primaryPath(slot), CSaveFormat::backupPath(slot)}) {
                const auto path = resources->getPath(relative);
                if (!path.empty()) {
                    std::filesystem::remove(path);
                }
            }
        }
        if (game) {
            game->getContext()->shutdown();
        }
    }
};

void testVerifiedLoadResumesActualFlowOnlyAfterPostedLeaseRelease() {
    VerifiedResumeFixture fixture;
    if (!fixture.ready) {
        fixture.cleanup(false);
        return;
    }
    constexpr int INSTALLATIONS = 8;
    bool successful = true;
    for (int index = 0; index < INSTALLATIONS; ++index) {
        auto original = fixture.game->getMap();
        auto unsafe = original->tryBeginUnsafeOperation();
        expect_true(unsafe.has_value(), "resume fixture must own the quarantine it recovers");
        if (!unsafe) {
            fixture.cleanup(false);
            return;
        }
        unsafe->quarantine();
        fixture.state->snapshotAvailable = false;
        fixture.state->unsafeAvailable = false;
        const bool backup_recovery = index == INSTALLATIONS / 2;
        if (backup_recovery) {
            fixture.resources->save(CSaveFormat::primaryPath(fixture.slot), "{ invalid");
        }
        CGameLoader::loadSavedGame(fixture.game, fixture.slot);
        const bool installed = fixture.game->getMap() != original;
        const bool queued = installed && fixture.state->calls == index &&
                            fixture.game->getMap()->getStringProperty("verifiedLoadResumeReceiver") == "resumeReceiver";
        expect_true(queued,
                    "verified load must reapply authored receiver and return before its posted real UiFlow runs");
        const bool repaired =
            !backup_recovery ||
            CSaveFormat::decodeDocument(fixture.resources->loadJson(CSaveFormat::primaryPath(fixture.slot)))
                .has_value();
        expect_true(repaired, "backup repair must complete before the verified resume task can dispatch");
        vstd::event_loop<>::instance()->run();
        const bool resumed =
            fixture.state->calls == index + 1 && fixture.state->snapshotAvailable && fixture.state->unsafeAvailable;
        expect_true(resumed, "each verified installation must resume once after restore exclusivity is released");
        successful = successful && queued && repaired && resumed;
    }
    std::printf("verified-load-resume installations=%d dispatches=%d expected=%d\n", INSTALLATIONS,
                fixture.state->calls, INSTALLATIONS);
    fixture.cleanup(successful);
}

void testVerifiedLoadResumeRejectsSupersededWeakBindings() {
    for (int mode = 0; mode < 6; ++mode) {
        VerifiedResumeFixture fixture;
        if (!fixture.ready) {
            fixture.cleanup(false);
            return;
        }
        auto original = fixture.game->getMap();
        CGameLoader::loadSavedGame(fixture.game, fixture.slot);
        auto installed = fixture.game->getMap();
        const bool queued = installed != original && fixture.state->calls == 0;
        if (mode == 0) {
            fixture.game->getContext()->advanceTransitionGeneration();
        } else if (mode == 1) {
            auto replacement = std::make_shared<CMap>();
            replacement->setGame(fixture.game);
            fixture.game->setMap(replacement);
        } else if (mode == 2) {
            installed->setStringProperty("verifiedLoadResumeReceiver", "anotherReceiver");
        } else if (mode == 3) {
            installed->removeObject(installed->getObjectByName("resumeReceiver"));
            auto replacement = fixture.game->createObject<CMapObject>("VerifiedLoadReceiverProbe");
            replacement->setName("resumeReceiver");
            installed->addObject(replacement);
        } else if (mode == 4) {
            fixture.game->getContext()->shutdown();
        } else {
            fixture.game.reset();
            expect_true(fixture.state->game.expired(), "queued resume must not retain the game's final owner");
        }
        vstd::event_loop<>::instance()->run();
        const bool suppressed = fixture.state->calls == 0;
        expect_true(queued && suppressed,
                    "stale generation/map/policy/receiver/context/game must suppress posted resume");
        fixture.cleanup(queued && suppressed);
    }
}

void testUnverifiedOrRejectedLoadsNeverDispatchResume() {
    int rejected_dispatches = 0;
    for (int mode = 0; mode < 7; ++mode) {
        VerifiedResumeFixture fixture;
        if (!fixture.ready) {
            fixture.cleanup(false);
            return;
        }
        auto original = fixture.game->getMap();
        std::optional<CGameContext::UnsafeOperationLease> unsafe;
        std::optional<CGameContext::SaveSnapshotLease> snapshot;
        bool expected_outcome = true;
        if (mode == 0) {
            CGameLoader::loadSavedGame(fixture.game, fixture.slot + "-missing");
        } else if (mode == 1) {
            unsafe = original->tryBeginUnsafeOperation();
            expected_outcome = unsafe.has_value();
            CGameLoader::loadSavedGame(fixture.game, fixture.slot);
        } else if (mode == 2) {
            snapshot = original->tryBeginSaveSnapshot();
            expected_outcome = snapshot.has_value();
            CGameLoader::loadSavedGame(fixture.game, fixture.slot);
        } else if (mode == 3) {
            auto candidate = CMapLoader::loadSavedMap(fixture.game, fixture.slot);
            fixture.game->setMap(candidate);
            expected_outcome = candidate != original && candidate->getObjectByName("resumeReceiver") != nullptr &&
                               candidate->getStringProperty("verifiedLoadResumeReceiver") == "resumeReceiver";
        } else if (mode == 4) {
            auto authored = std::const_pointer_cast<json>(
                fixture.game->getConfigurationProvider()->getConfiguration("maps/test/map.json"));
            (*authored)["properties"]["verifiedLoadResumeReceiver"] = true;
            CGameLoader::loadSavedGame(fixture.game, fixture.slot);
        } else if (mode == 5) {
            unsafe = original->tryBeginUnsafeOperation();
            expected_outcome = unsafe.has_value();
            if (unsafe) {
                unsafe->quarantine();
            }
            auto panel = std::make_shared<SaveAdmissionClosingPanel>();
            panel->setGame(fixture.game);
            auto supersessions = std::make_shared<int>(0);
            panel->callback = [supersessions, weakGame = fixture.state->game] {
                ++*supersessions;
                if (auto owner = weakGame.lock()) {
                    owner->getContext()->advanceTransitionGeneration();
                }
            };
            fixture.game->getGui()->addChild(panel);
            CGameLoader::loadSavedGame(fixture.game, fixture.slot);
            expected_outcome =
                expected_outcome && *supersessions == 1 && !fixture.game->getMap()->tryBeginSaveSnapshot();
        } else {
            auto authored = std::const_pointer_cast<json>(
                fixture.game->getConfigurationProvider()->getConfiguration("maps/test/map.json"));
            (*authored)["properties"].erase("verifiedLoadResumeReceiver");
            CGameLoader::loadSavedGame(fixture.game, fixture.slot);
            expected_outcome = fixture.game->getMap() != original &&
                               fixture.game->getMap()->getStringProperty("verifiedLoadResumeReceiver").empty() &&
                               fixture.game->getMap()->tryBeginSaveSnapshot().has_value();
        }
        if (mode == 0 || mode == 1 || mode == 2 || mode == 4) {
            expected_outcome = expected_outcome && fixture.game->getMap() == original;
        }
        vstd::event_loop<>::instance()->run();
        const bool suppressed = fixture.state->calls == 0;
        rejected_dispatches += fixture.state->calls;
        expect_true(expected_outcome && suppressed,
                    "failed/admission-rejected/candidate-only/malformed/superseded loads must not dispatch resume");
        if (unsafe) {
            unsafe->finish();
        }
        snapshot.reset();
        fixture.cleanup(expected_outcome && suppressed);
    }
    expect_true(rejected_dispatches == 0,
                "seven rejected, unverified or disabled load paths have a zero authored-dispatch budget");
    std::printf("verified-load-resume rejected-or-disabled-paths=7 dispatches=%d expected=0\n", rejected_dispatches);
}

void testSevenSunsWarningRetiredActorEffectCycleEndsWithItsMapWhileGameLives() {
    std::shared_ptr<CGame> livingGame;
    std::weak_ptr<CMap> dyingMap;
    std::weak_ptr<CCreature> actor;
    std::weak_ptr<CEffect> effect;
    {
        SevenSunsWarningFixture fixture;
        livingGame = fixture.game;
        dyingMap = fixture.map;
        actor = fixture.warning;
        effect = fixture.effect;
        auto session = fixture.begin();
        SevenSunsWarningFixture::finish(*session);
        session->close();
        session.reset();
        auto destination = std::make_shared<CMap>();
        destination->setGame(livingGame);
        livingGame->setMap(destination);
    }
    vstd::event_loop<>::instance()->runReady();
    expect_true(livingGame->getContext()->isActive() && dyingMap.expired() && actor.expired() && effect.expired(),
                "dropping the retired scene map must break its native actor/effect cycle while the game still lives");
}

void testSevenSunsWarningRestoredWholeMapOwnsAndReleasesRetiredEffectCycles() {
    json snapshot;
    std::shared_ptr<CGame> originalGame;
    {
        SevenSunsWarningFixture fixture;
        originalGame = fixture.game;
        auto session = fixture.begin();
        SevenSunsWarningFixture::finish(*session);
        session->close();
        session.reset();
        auto saved = CSerialization::serializeExpected(fixture.map, "unit-seven-suns-whole-map");
        expect_true(saved.has_value(), "the whole map with its retired scene owner must serialize");
        if (!saved)
            return;
        snapshot = *saved;
        expect_true(snapshot.at("properties").contains("sceneRetiredObjects"),
                    "an active retired lifetime owner must be present in the native map snapshot");
        auto destination = std::make_shared<CMap>();
        destination->setGame(originalGame);
        originalGame->setMap(destination);
    }
    vstd::event_loop<>::instance()->runReady();
    auto restoredGame = std::make_shared<CGame>();
    auto objects = restoredGame->getObjectHandler();
    objects->registerType("CMap", [] { return std::make_shared<CMap>(); });
    objects->registerType("CPlayer", [] { return std::make_shared<CPlayer>(); });
    objects->registerType("CBuilding", [] { return std::make_shared<CBuilding>(); });
    objects->registerType("CCreature", [] { return std::make_shared<CCreature>(); });
    objects->registerType("CItem", [] { return std::make_shared<CItem>(); });
    objects->registerType("CWeapon", [] { return std::make_shared<CWeapon>(); });
    objects->registerType("CEffect", [] { return std::make_shared<CEffect>(); });
    objects->registerType("CStats", [] { return std::make_shared<CStats>(); });
    objects->registerType("CQuest", [] { return std::make_shared<CQuest>(); });
    objects->registerType("CTrigger", [] { return std::make_shared<CTrigger>(); });
    objects->registerType("CController", [] { return std::make_shared<CController>(); });
    objects->registerType("CMonsterFightController", [] { return std::make_shared<CMonsterFightController>(); });
    objects->registerType("CPlayerController", [] { return std::make_shared<CPlayerController>(); });
    objects->registerType("CPlayerFightController", [] { return std::make_shared<CPlayerFightController>(); });
    std::weak_ptr<CCreature> actor;
    std::weak_ptr<CEffect> effect;
    std::weak_ptr<CMap> dyingMap;
    {
        auto decoded = CSerialization::deserializeExpected<std::shared_ptr<CGameObject>>(
            restoredGame, snapshot, "unit-seven-suns-restored-whole-map");
        expect_true(decoded.has_value(), "the whole map must restore the ordinary retired collection");
        if (!decoded)
            return;
        auto map = std::dynamic_pointer_cast<CMap>(*decoded);
        expect_true(map != nullptr, "the restored scene snapshot must remain a map");
        if (!map)
            return;
        restoredGame->setMap(map);
        auto clock = map->getObjectByName("cityClock");
        auto retained =
            std::dynamic_pointer_cast<CCreature>(clock->getObjectProperty(SevenSunsWarningFixture::ActorKey));
        expect_true(retained && retained->getEffects().size() == 1 && !map->getObjectByName("cityAr0601Actor2"),
                    "the restored retired actor must stay alive and absent from the map registry");
        if (!retained || retained->getEffects().size() != 1)
            return;
        auto retainedEffect = *retained->getEffects().begin();
        expect_true(retainedEffect->getCaster() == retained && retainedEffect->getVictim() == retained,
                    "whole-map aliases must resolve to the single retired actor owned by the restored collection");
        actor = retained;
        effect = retainedEffect;
        dyingMap = map;
        auto destination = std::make_shared<CMap>();
        destination->setGame(restoredGame);
        restoredGame->setMap(destination);
    }
    vstd::event_loop<>::instance()->runReady();
    expect_true(originalGame->getContext()->isActive() && restoredGame->getContext()->isActive() &&
                    dyingMap.expired() && actor.expired() && effect.expired(),
                "restored map destruction must release retired cycles without shutdown or explicit effect cleanup");
}

void testSevenSunsWarningOldMapCleanupPreservesActorAdoptedByAnotherLiveMap() {
    std::shared_ptr<CGame> livingGame;
    std::shared_ptr<CMap> destination;
    std::weak_ptr<CCreature> actor;
    std::weak_ptr<CEffect> effect;
    {
        SevenSunsWarningFixture fixture;
        livingGame = fixture.game;
        auto session = fixture.begin();
        SevenSunsWarningFixture::finish(*session);
        session->close();
        session.reset();
        destination = std::make_shared<CMap>();
        destination->setGame(livingGame);
        livingGame->setMap(destination);
        destination->addObject(fixture.warning);
        actor = fixture.warning;
        effect = fixture.effect;
    }
    vstd::event_loop<>::instance()->runReady();
    auto adopted = actor.lock();
    expect_true(adopted && adopted->getEffects().size() == 1 && !effect.expired() &&
                    destination->getObjectByName("cityAr0601Actor2") == adopted,
                "old scene cleanup must not erase an actor's effects after another live map adopts it");
    adopted.reset();
    auto next = std::make_shared<CMap>();
    next->setGame(livingGame);
    livingGame->setMap(next);
    destination.reset();
    vstd::event_loop<>::instance()->runReady();
    expect_true(actor.expired() && effect.expired() && livingGame->getContext()->isActive(),
                "the actual destination owner must release the actor/effect cycle when that map dies");
}

void testSevenSunsWarningDefaultMapSnapshotOmitsTheEmptyRetirementCollection() {
    SevenSunsWarningFixture fixture;
    const auto saved = CSerialization::serializeExpected(fixture.map, "unit-default-scene-retirement");
    expect_true(saved && !saved->at("properties").contains("sceneRetiredObjects") &&
                    fixture.warning->getEffects().size() == 1,
                "ordinary maps keep their default snapshot shape until a private scene retirement owns an actor");
}

void testSevenSunsWarningReflectedOwnerTamperingQuarantinesAndStillCleansCycles() {
    std::shared_ptr<CGame> livingGame;
    std::weak_ptr<CCreature> actor;
    std::weak_ptr<CEffect> effect;
    {
        SevenSunsWarningFixture fixture;
        livingGame = fixture.game;
        actor = fixture.warning;
        effect = fixture.effect;
        fixture.duringJournalFactory = [&] {
            fixture.map->setProperty<std::set<std::shared_ptr<CMapObject>>>("sceneRetiredObjects", {});
        };
        auto session = fixture.begin();
        SevenSunsWarningFixture::step(*session, 0);
        SevenSunsWarningFixture::step(*session, 7);
        bool rejected = false;
        try {
            SevenSunsWarningFixture::step(*session, 9);
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.destroyCalls == 0,
                    "removing the reflected retired owner during an admitted callback cannot commit source success");
        session.reset();
        auto destination = std::make_shared<CMap>();
        destination->setGame(livingGame);
        livingGame->setMap(destination);
    }
    vstd::event_loop<>::instance()->runReady();
    expect_true(livingGame->getContext()->isActive() && actor.expired() && effect.expired(),
                "the private monotonic lifetime anchor must clean cycles even after reflected-owner tampering");
}

void testSevenSunsWarningSwallowedNestedBeginCannotAcknowledgeRetirement() {
    SevenSunsWarningFixture fixture;
    fixture.duringJournalFactory = [&] {
        try {
            auto nested = fixture.begin();
        } catch (const std::exception &) {
        }
    };
    auto session = fixture.begin();
    SevenSunsWarningFixture::step(*session, 0);
    SevenSunsWarningFixture::step(*session, 7);
    bool rejected = false;
    try {
        SevenSunsWarningFixture::step(*session, 9);
    } catch (const std::exception &) {
        rejected = true;
    }
    expect_true(rejected && fixture.state().at("status").get<std::string>() == "pending" &&
                    !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.destroyCalls == 0 &&
                    fixture.clock->getObjectProperty(SevenSunsWarningFixture::ActorKey) == fixture.warning,
                "swallowing nested begin rejection must poison the admitted outer warning owner");
}

void testSevenSunsWarningOtherUnsafeQuarantineCannotBecomeSuccess() {
    SevenSunsWarningFixture fixture;
    fixture.duringJournalFactory = [&] {
        auto other = fixture.map->tryBeginUnsafeOperation();
        expect_true(other.has_value(), "the fixture must reach the existing nonexclusive native admission seam");
        if (other)
            other->quarantine();
    };
    auto session = fixture.begin();
    SevenSunsWarningFixture::step(*session, 0);
    SevenSunsWarningFixture::step(*session, 7);
    bool rejected = false;
    try {
        SevenSunsWarningFixture::step(*session, 9);
    } catch (const std::exception &) {
        rejected = true;
    }
    expect_true(rejected && fixture.state().at("status").get<std::string>() == "pending" &&
                    !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.destroyCalls == 0,
                "current pointer/generation alone cannot acknowledge an already quarantined native admission");
}

void testSevenSunsWarningCapacityPreflightNeverPublishesAnUnreadableOwnResult() {
    for (int mode = 0; mode < 3; ++mode) {
        SevenSunsWarningFixture fixture;
        json source = json::object();
        if (mode == 0) {
            source["GLOBAL"] = json::object();
            for (int index = 0; index < 1024; ++index)
                source["GLOBAL"]["Other" + std::to_string(index)] = index;
        } else if (mode == 1) {
            for (int index = 0; index < 256; ++index)
                source["AREA" + std::to_string(index)] = json::object();
        } else {
            json talks = json::object();
            for (int index = 0; index < 2048; ++index)
                talks["Other" + std::to_string(index)] = json::object();
            fixture.map->setStringProperty("plugin_cityTalked", "city-json:" + talks.dump());
        }
        fixture.map->setStringProperty("plugin_citySourceGlobals", "city-json:" + source.dump());
        auto session = fixture.begin();
        const auto globalsBefore = fixture.map->getStringProperty("plugin_citySourceGlobals");
        bool rejected = false;
        try {
            SevenSunsWarningFixture::step(*session, 0);
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && fixture.map->getStringProperty("plugin_citySourceGlobals") == globalsBefore &&
                        fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey).empty() &&
                        fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning &&
                        fixture.map->tryBeginSaveSnapshot().has_value() && fixture.questFactories == 0,
                    "a valid-at-capacity store must refuse before effects rather than commit an unreadable next state");
        session->close();
    }
}

void testSevenSunsWarningRejectsOverflowingJsonAuthorityInsteadOfAliasingLowBits() {
    for (const auto *value : {"4294967297", "-4294967295", "18446744073709551615"}) {
        SevenSunsWarningFixture fixture;
        fixture.map->setStringProperty("plugin_citySourceGlobals",
                                       std::string("city-json:{\"GLOBAL\":{\"AskedForTour\":") + value + "}}");
        bool rejected = false;
        try {
            auto session = fixture.begin();
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning &&
                        fixture.questFactories == 0 && !fixture.map->tryBeginSaveSnapshot().has_value(),
                    "out-of-range JSON integers cannot alias source AskedForTour=1 through a narrowing cast");
    }
}

void testSevenSunsWarningUiFlowDispatchOwnsTokensAndRejectsOversizedSourceEdges() {
    ScriptFlowNativeObjectTypes types;
    for (int variant = 0; variant < 3; ++variant) {
        SevenSunsWarningFixture fixture;
        pybind11::dict scope;
        scope["clock"] = nativeFlowObject(fixture.clock);
        scope["actor"] = nativeFlowObject(fixture.warning);
        scope["variant"] = variant;
        pybind11::exec(R"(
events = []
def nativeWarning():
    try:
        arguments = (clock, actor) if variant != 1 else (clock,)
        view = yield {'operation': 'gui.beginSevenSunsWarning', 'args': arguments, 'kwargs': {}}
        for edge in (0, 7, 9):
            supplied = edge + (4294967296 if variant == 2 else 0)
            view = yield {'operation': 'gui.advanceSevenSunsWarning', 'args': (view['revision'], supplied), 'kwargs': {}}
        events.append(view['status'])
        yield {'operation': 'gui.endSevenSunsWarning', 'args': (), 'kwargs': {}}
    finally:
        events.append('closed')
)",
                       scope);
        auto flow = fixture.game->getScriptHandler()->createCallbackFlow(
            scope["nativeWarning"].cast<pybind11::function>(), fixture.game);
        auto pending =
            fixture.game->getContext()->spawnTask(fixture.game->getGuiHandler()->runScriptFlowAsync(std::move(flow)));
        expect_true(pumpHandlerUntil([&] { return pending.finished(); }), "finite native warning flow must settle");
        bool rejected = false;
        if (pending.finished()) {
            try {
                pending.get();
            } catch (const std::exception &) {
                rejected = true;
            }
        }
        const auto events = scope["events"].cast<pybind11::list>();
        expect_true(events.size() == (variant == 0 ? 2 : 1) &&
                        events[events.size() - 1].cast<std::string>() == "closed",
                    "both completed and rejected owned native UI flows must close their Python generator");
        if (variant == 0) {
            expect_true(!rejected && !fixture.map->getObjectByName("cityAr0601Actor2") && fixture.questFactories == 1 &&
                            fixture.state().at("status").get<std::string>() == "retired",
                        "actual UI-flow tokens must drive the owned source cursor and exact native retirement");
        } else {
            expect_true(rejected && fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning &&
                            fixture.questFactories == 0 &&
                            fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey).empty(),
                        "missing native tokens and oversized JSON edge authority must fail before source effects");
        }
        scope.clear();
        fixture.game->getContext()->shutdown();
    }
}

void testSevenSunsWarningJournalMembershipLossCannotBecomeAcceptedRetirement() {
    SevenSunsWarningFixture fixture;
    int journalChecks = 0;
    auto session = fixture.begin([&] {
        if (fixture.questFactories == 1 && fixture.journal() && ++journalChecks == 3)
            fixture.player->setQuests({});
    });
    SevenSunsWarningFixture::step(*session, 0);
    SevenSunsWarningFixture::step(*session, 7);
    bool rejected = false;
    try {
        SevenSunsWarningFixture::step(*session, 9);
    } catch (const std::exception &) {
        rejected = true;
    }
    expect_true(rejected && !fixture.journal() && fixture.state().at("status").get<std::string>() == "pending" &&
                    !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.destroyCalls == 0 &&
                    fixture.clock->getObjectProperty(SevenSunsWarningFixture::ActorKey) == fixture.warning,
                "a journal invalidated at a real continuation boundary cannot publish accepted retirement");
}

void testSevenSunsWarningSharedNamesIgnoreAsciiCaseAndRejectAmbiguousAliases() {
    {
        SevenSunsWarningFixture fixture;
        fixture.map->setStringProperty("plugin_citySourceGlobals",
                                       "city-json:{\"GLOBAL\":{\"aSkEdFoRtOuR\":1,\"cHeCkEdSeVeNsUnS\":73,\"Other\":9},"
                                       "\"global\":{\"AskedForTour\":2}}");
        auto session = fixture.begin();
        SevenSunsWarningFixture::finish(*session, {2, 5, 16});
        const auto encoded = fixture.map->getStringProperty("plugin_citySourceGlobals");
        const auto globals = json::parse(std::string_view(encoded).substr(std::string_view("city-json:").size()));
        expect_true(globals.at("GLOBAL").at("aSkEdFoRtOuR").get<int>() == 1 &&
                        globals.at("GLOBAL").at("cHeCkEdSeVeNsUnS").get<int>() == 2 &&
                        !globals.at("GLOBAL").contains("AskedForTour") &&
                        !globals.at("GLOBAL").contains("CheckedSevenSuns") &&
                        globals.at("GLOBAL").at("Other").get<int>() == 9 &&
                        globals.at("global").at("AskedForTour").get<int>() == 2,
                    "classic variable names ignore ASCII case while source scope GLOBAL stays case-sensitive");
        session->close();
    }
    {
        SevenSunsWarningFixture fixture;
        fixture.map->setStringProperty("plugin_citySourceGlobals",
                                       "city-json:{\"GLOBAL\":{\"AskedForTour\":1,\"ASKEDFORTOUR\":2}}");
        bool rejected = false;
        try {
            auto session = fixture.begin();
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.questFactories == 0 &&
                        fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning,
                    "ambiguous case aliases fail closed before any source effect, without picking a winner");
    }
}

void testSevenSunsWarningEveryReachableDefaultGlobalPathUsesNativeCursor() {
    constexpr std::array<std::array<int, 3>, 9> paths{{
        {0, 7, 9},
        {0, 8, 16},
        {1, 3, 15},
        {1, 4, 9},
        {1, 5, 16},
        {1, 6, 16},
        {2, 3, 15},
        {2, 4, 9},
        {2, 6, 16},
    }};
    std::set<int> observedEdges;
    for (const auto &path : paths) {
        SevenSunsWarningFixture fixture;
        auto session = fixture.begin();
        expect_true(session != nullptr, "each source path must start against the exact admitted actor");
        if (!session)
            continue;
        json result;
        for (const int edge : path) {
            result = SevenSunsWarningFixture::step(*session, edge);
            observedEdges.insert(edge);
            expect_true(fixture.map->tryBeginSaveSnapshot().has_value(),
                        "every completed native edge is a stable save boundary, including nonterminal choices");
        }
        expect_true(result.at("status").get<std::string>() == "retired" && fixture.questFactories == 1 &&
                        fixture.destroyCalls == 0 && fixture.stockAndEffectIntact(),
                    "all nine AskedForTour=0 entry paths reach one exact non-victory native escape");
        session->close();
    }
    expect_true(observedEdges == std::set<int>({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16}),
                "the native path matrix must exercise all12 reachable edges and no external-entry source edge");
}

void testSevenSunsWarningRetiresSameLivingActorAndPublishesOneJournal() {
    for (const auto &path : {std::array{0, 7, 9}, std::array{1, 3, 15}, std::array{2, 6, 16}}) {
        SevenSunsWarningFixture fixture;
        const auto objectCount = fixture.map->getObjects().size();
        const auto effectOwners = fixture.game->getContext()->getEffectOwnerCount();
        const auto experience = fixture.player->getExp();
        const auto gold = fixture.player->getGold();
        auto session = fixture.begin();
        expect_true(session != nullptr, "accepted exact source warning actor must create a native session");
        if (!session)
            continue;
        json result;
        for (const int edge : path)
            result = SevenSunsWarningFixture::step(*session, edge);
        auto note = fixture.journal();
        expect_true(result.at("status").get<std::string>() == "retired" &&
                        !fixture.map->getObjectByName("cityAr0601Actor2") &&
                        fixture.clock->getObjectProperty(SevenSunsWarningFixture::ActorKey) == fixture.warning &&
                        fixture.state().at("status").get<std::string>() == "retired" &&
                        fixture.state().at("lastEdge").get<int>() == path.back() && fixture.stockAndEffectIntact(),
                    "each reachable escape must retain the same living actor and its actual possessions/effect");
        expect_true(note && !note->getObjective().empty() && !note->getReward().empty() && !note->getHint().empty() &&
                        fixture.player->getQuests().size() == 1 && fixture.player->getCompletedQuests().empty() &&
                        fixture.questFactories == 1 && fixture.actorFactories == 0 && fixture.itemFactories == 0 &&
                        fixture.destroyCalls == 0 && fixture.player->getExp() == experience &&
                        fixture.player->getGold() == gold && fixture.map->getObjects().size() + 1 == objectCount &&
                        fixture.game->getContext()->getEffectOwnerCount() == effectOwners &&
                        fixture.protectedActorsIntact(),
                    "retirement creates one readable journal lead and no actor/item, destroy, victory or reward");
        for (const auto *area : {"AR0601", "AR0602", "AR0603"})
            expect_true(!fixture.map->getBoolProperty(std::string("plugin_cityCombatObserved_") + area),
                        "EscapeArea must not grant a floor-clear combat observation");
        expect_true(fixture.map->tryBeginSaveSnapshot().has_value(),
                    "a completely committed escape releases bounded native mutation admission");
        session->close();
    }
}

void testSevenSunsWarningCommittedChoiceSurvivesCancellationAndRemainsSaveable() {
    for (const int edge : {0, 1, 2}) {
        SevenSunsWarningFixture fixture;
        auto session = fixture.begin();
        expect_true(session != nullptr, "source warning session must start");
        if (!session)
            continue;
        SevenSunsWarningFixture::step(*session, edge);
        const auto committed = fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey);
        const auto state = fixture.state();
        expect_true(state.at("status").get<std::string>() == "active" &&
                        state.at("globals").at("CheckedSevenSuns").get<int>() == 2 &&
                        state.at("globals").at("AskedForTour").get<int>() == (edge == 1 ? 1 : 0) &&
                        fixture.map->getBoolProperty("plugin_cityHistoryFrozen") &&
                        fixture.warning->getNumericProperty("plugin_cityTalkCount") == 1 &&
                        fixture.map->getStringProperty("plugin_cityTalked").find("cityAr0601Actor2") !=
                            std::string::npos &&
                        fixture.map->tryBeginSaveSnapshot().has_value(),
                    "instant source globals/talk/history commit before later UI, without a cross-UI save lease");
        session->close();
        session.reset();
        expect_true(fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey) == committed &&
                        fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning &&
                        fixture.questFactories == 0 && fixture.destroyCalls == 0 && fixture.stockAndEffectIntact() &&
                        fixture.map->tryBeginSaveSnapshot().has_value(),
                    "later cancellation must retain the earlier source choice, actor and saveable stable cursor");
    }
}

void testSevenSunsWarningRefusesWrongSourceAndMapAwayBackBeforeCommit() {
    for (int mode = 0; mode < 4; ++mode) {
        SevenSunsWarningFixture fixture;
        auto session = fixture.begin();
        expect_true(session != nullptr, "source warning session must start before stale-boundary injection");
        if (!session)
            continue;
        if (mode == 0) {
            auto foreign = std::make_shared<CMap>();
            foreign->setGame(fixture.game);
            fixture.game->setMap(foreign);
            fixture.game->setMap(fixture.map);
        } else if (mode == 1) {
            fixture.warning->setStringProperty("sourceCreature", "DOPMER");
        } else if (mode == 2) {
            fixture.warning->setStringProperty("sourceActor", "AR0601#actor1");
        } else {
            fixture.warning->setStringProperty("sourceDialogue", "DOPMER");
        }
        const auto prior = fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey);
        bool rejected = false;
        try {
            SevenSunsWarningFixture::step(*session, 0);
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey) == prior &&
                        fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning &&
                        fixture.questFactories == 0 && fixture.destroyCalls == 0 &&
                        fixture.map->tryBeginSaveSnapshot().has_value(),
                    "known stale/wrong source must refuse before mutation; public away-and-back is not equality");
        session->close();
    }
}

void testSevenSunsWarningRejectsWrongRevisionAndSourceConditionalEdge() {
    SevenSunsWarningFixture fixture;
    auto session = fixture.begin();
    expect_true(session != nullptr, "source warning session must start");
    if (!session)
        return;
    SevenSunsWarningFixture::step(*session, 2);
    const auto prior = fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey);
    for (int mode = 0; mode < 3; ++mode) {
        bool rejected = false;
        try {
            const auto revision = session->view().at("revision").get<int>();
            session->advance(mode == 0 ? revision - 1 : revision, mode == 2 ? 14 : 5);
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey) == prior &&
                        fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning &&
                        fixture.questFactories == 0 && fixture.map->tryBeginSaveSnapshot().has_value(),
                    "old revision, AskedForTour=0 edge5 and unreachable Enemy edge14 cannot commit effects");
    }
    session->close();
}

void testSevenSunsWarningReplayRequiresExactRetainedOwnerAndCreatesNothing() {
    SevenSunsWarningFixture fixture;
    auto session = fixture.begin();
    expect_true(session != nullptr, "source warning session must start");
    if (!session)
        return;
    SevenSunsWarningFixture::finish(*session);
    session->close();
    session.reset();
    const auto receipt = fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey);
    const auto note = fixture.journal();
    for (int pass = 0; pass < 8; ++pass) {
        auto replay = fixture.begin();
        expect_true(replay && replay->view().at("status").get<std::string>() == "retired",
                    "the exact retained retired actor must acknowledge completed source work without replay");
        if (replay)
            replay->close();
    }
    expect_true(fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey) == receipt &&
                    fixture.journal() == note && fixture.questFactories == 1 && fixture.actorFactories == 0 &&
                    fixture.itemFactories == 0 && fixture.destroyCalls == 0 && fixture.stockAndEffectIntact(),
                "replay cannot construct stock/actors/journals or change the settled source receipt");
}

void testSevenSunsWarningClassifiesPendingAndOrphanStateBeforeMissingPlayer() {
    for (int mode = 0; mode < 3; ++mode) {
        SevenSunsWarningFixture fixture;
        if (mode == 0) {
            fixture.map->setStringProperty(SevenSunsWarningFixture::StateKey,
                                           "city-json:{\"version\":1,\"status\":\"pending\",\"revision\":1,"
                                           "\"globals\":{\"AskedForTour\":0,\"CheckedSevenSuns\":2},\"lastEdge\":0,"
                                           "\"cursor\":2,\"journal\":null}");
        } else if (mode == 1) {
            fixture.map->setStringProperty(SevenSunsWarningFixture::StateKey, "city-json:{broken");
        } else {
            fixture.clock->setObjectProperty(SevenSunsWarningFixture::ActorKey, fixture.warning);
        }
        fixture.map->detachPlayer();
        bool rejected = false;
        try {
            auto session = fixture.begin();
            if (session)
                session->close();
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.questFactories == 0 &&
                        fixture.destroyCalls == 0 &&
                        fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning,
                    "pending, malformed or orphan ownership must quarantine before clean missing-player refusal");
    }
}

void testSevenSunsWarningPostRemovalFailureQuarantinesAndPreservesPrimaryError() {
    SevenSunsWarningFixture fixture;
    bool saveBlockedDuringRetirement = false;
    auto session = fixture.begin([&] {
        if (!fixture.map->getObjectByName("cityAr0601Actor2")) {
            saveBlockedDuringRetirement = !fixture.map->tryBeginSaveSnapshot().has_value();
            throw std::runtime_error("Seven Suns native post-removal guard failure");
        }
    });
    expect_true(session != nullptr, "source warning session must start");
    if (!session)
        return;
    SevenSunsWarningFixture::step(*session, 0);
    SevenSunsWarningFixture::step(*session, 7);
    bool primary = false;
    try {
        SevenSunsWarningFixture::step(*session, 9);
    } catch (const std::exception &error) {
        primary = std::string(error.what()) == "Seven Suns native post-removal guard failure";
    }
    expect_true(primary && saveBlockedDuringRetirement && !fixture.map->getObjectByName("cityAr0601Actor2") &&
                    fixture.clock->getObjectProperty(SevenSunsWarningFixture::ActorKey) == fixture.warning &&
                    fixture.state().at("status").get<std::string>() == "pending" &&
                    !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.destroyCalls == 0 &&
                    fixture.stockAndEffectIntact(),
                "a real post-removal guard error must retain the live owner/pending receipt and quarantine save");
    // This injects a post-removal guard exception, not a navigation allocator or deferred signal-slot failure.
}

void testSevenSunsWarningJournalFactoryFailureCannotAcknowledgeEscape() {
    SevenSunsWarningFixture fixture;
    fixture.duringJournalFactory = [] { throw std::runtime_error("Seven Suns native journal constructor failure"); };
    auto session = fixture.begin();
    expect_true(session != nullptr, "source warning session must start");
    if (!session)
        return;
    SevenSunsWarningFixture::step(*session, 0);
    SevenSunsWarningFixture::step(*session, 7);
    bool primary = false;
    try {
        SevenSunsWarningFixture::step(*session, 9);
    } catch (const std::exception &error) {
        primary = std::string(error.what()) == "Seven Suns native journal constructor failure";
    }
    expect_true(primary && fixture.questFactories == 1 && !fixture.journal() &&
                    fixture.state().at("status").get<std::string>() == "pending" &&
                    !fixture.map->tryBeginSaveSnapshot().has_value() && fixture.destroyCalls == 0 &&
                    fixture.stockAndEffectIntact(),
                "an admitted journal failure preserves the original error and cannot become accepted/saveable");
}

void testSevenSunsWarningRetainedActorEffectAliasesRoundTrip() {
    SevenSunsWarningFixture fixture;
    auto session = fixture.begin();
    expect_true(session != nullptr, "source warning session must start");
    if (!session)
        return;
    SevenSunsWarningFixture::finish(*session);
    session->close();
    session.reset();
    auto admission = fixture.map->tryBeginSaveSnapshot();
    expect_true(admission.has_value(), "the settled retained owner must be snapshot-admissible");
    if (!admission)
        return;
    const auto snapshot = CSerialization::serializeExpected(fixture.clock, "unit-seven-suns-retired-owner");
    expect_true(snapshot.has_value(), "the retained living actor must serialize through the actual native codec");
    if (!snapshot)
        return;
    auto restoredGame = std::make_shared<CGame>();
    auto objects = restoredGame->getObjectHandler();
    objects->registerType("CBuilding", [] { return std::make_shared<CBuilding>(); });
    objects->registerType("CCreature", [] { return std::make_shared<CCreature>(); });
    objects->registerType("CItem", [] { return std::make_shared<CItem>(); });
    objects->registerType("CWeapon", [] { return std::make_shared<CWeapon>(); });
    objects->registerType("CEffect", [] { return std::make_shared<CEffect>(); });
    objects->registerType("CStats", [] { return std::make_shared<CStats>(); });
    objects->registerType("CController", [] { return std::make_shared<CController>(); });
    objects->registerType("CMonsterFightController", [] { return std::make_shared<CMonsterFightController>(); });
    const auto restored = CSerialization::deserializeExpected<std::shared_ptr<CGameObject>>(
        restoredGame, *snapshot, "unit-seven-suns-retired-owner");
    expect_true(restored.has_value(), "native retained actor/effect graph must deserialize with typed aliases");
    if (restored) {
        auto actor =
            std::dynamic_pointer_cast<CCreature>((*restored)->getObjectProperty(SevenSunsWarningFixture::ActorKey));
        expect_true(actor && actor != fixture.warning && actor->isAlive() && actor->getItems().size() == 1 &&
                        actor->getEquipped().size() == 1 && actor->getEffects().size() == 1,
                    "roundtrip must restore one living retained actor with its actual carried/equipped/effect state");
        if (actor && actor->getEffects().size() == 1) {
            const auto effect = *actor->getEffects().begin();
            expect_true(effect->getCaster() == actor && effect->getVictim() == actor,
                        "effect aliases must resolve to the exact restored retained actor, not a duplicate");
        }
    }
    // This is a native in-memory actor-graph roundtrip; whole-map save/load and UI journal proof remain separate.
}

void testSevenSunsWarningSessionDoesNotKeepClosedGameAlive() {
    SevenSunsWarningFixture fixture;
    auto session = fixture.begin();
    expect_true(session != nullptr, "source warning session must capture its non-owning game binding");
    if (!session)
        return;
    const auto prior = fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey);
    const std::weak_ptr<CGame> weakGame = fixture.game;
    fixture.game.reset();
    expect_true(weakGame.expired(), "an idle cross-UI warning capability must not keep the game/session graph alive");
    bool rejected = false;
    try {
        session->requireCurrent();
    } catch (const std::exception &) {
        rejected = true;
    }
    session.reset();
    expect_true(rejected && fixture.questFactories == 0 && fixture.actorFactories == 0 && fixture.itemFactories == 0 &&
                    fixture.destroyCalls == 0 &&
                    fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey) == prior,
                "an expired game refuses the captured capability and teardown performs no source effects");
    // Context shutdown may legitimately release effect references; that is separate from warning retirement.
}

void testSevenSunsWarningUsesSharedSourceGlobalsWithoutClampingOrDroppingScopes() {
    const auto shared = [](const SevenSunsWarningFixture &fixture) {
        const auto encoded = fixture.map->getStringProperty("plugin_citySourceGlobals");
        constexpr std::string_view prefix = "city-json:";
        return json::parse(encoded.starts_with(prefix) ? std::string_view(encoded).substr(prefix.size())
                                                       : std::string_view(encoded));
    };
    for (const int asked : {1, 2, -1}) {
        SevenSunsWarningFixture fixture;
        fixture.map->setStringProperty(
            "plugin_citySourceGlobals",
            "city-json:" +
                json{{"GLOBAL", {{"AskedForTour", asked}, {"CheckedSevenSuns", 73}, {"OtherSourceGlobal", 9}}},
                     {"AR0601", {{"KeepLocal", 17}}}}
                    .dump());
        expect_true(fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey).empty(),
                    "shared-global regression starts without a warning-specific receipt");
        auto session = fixture.begin();
        expect_true(session != nullptr,
                    "preexisting integer source globals are admitted without a warning-specific value clamp");
        if (!session)
            continue;
        SevenSunsWarningFixture::step(*session, 2);
        if (asked == 1) {
            SevenSunsWarningFixture::step(*session, 5);
            const auto answer = SevenSunsWarningFixture::step(*session, 16);
            expect_true(answer.at("status").get<std::string>() == "retired" && fixture.questFactories == 1,
                        "preexisting shared AskedForTour=1 enables the actual source edge5 escape route");
        } else {
            bool offered = false;
            for (const auto &edge : session->view().at("choices"))
                offered = offered || edge.get<int>() == 5;
            const auto prior = fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey);
            bool rejected = false;
            try {
                SevenSunsWarningFixture::step(*session, 5);
            } catch (const std::exception &) {
                rejected = true;
            }
            expect_true(!offered && rejected && fixture.questFactories == 0 &&
                            fixture.map->getStringProperty(SevenSunsWarningFixture::StateKey) == prior &&
                            fixture.map->getObjectByName("cityAr0601Actor2") == fixture.warning &&
                            fixture.map->tryBeginSaveSnapshot().has_value(),
                        "AskedForTour=2 or negative remains a valid integer but cannot satisfy equality-to-one");
        }
        const auto globals = shared(fixture);
        expect_true(globals.at("GLOBAL").at("AskedForTour").get<int>() == asked &&
                        globals.at("GLOBAL").at("CheckedSevenSuns").get<int>() == 2 &&
                        globals.at("GLOBAL").at("OtherSourceGlobal").get<int>() == 9 &&
                        globals.at("AR0601").at("KeepLocal").get<int>() == 17 &&
                        fixture.state().at("globals").at("AskedForTour").get<int>() == asked &&
                        fixture.state().at("globals").at("CheckedSevenSuns").get<int>() == 2,
                    "source writes preserve unrelated globals/scopes and the warning row only audits actual values");
        session->close();
    }
}

void testSevenSunsMerchantRejectsUnsignedDumpAliasingBeforeSourceAuthority() {
    for (const std::string raw : {"4294967297", "18446744073709551615", "-2147483649"}) {
        SevenSunsMerchantFixture f;
        f.map->setStringProperty("plugin_citySourceGlobals", "city-json:{\"GLOBAL\":{\"Laola\":" + raw + "}}");
        bool rejected = false;
        try {
            auto flow = f.beginMerchant();
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(
            rejected && f.protectedActors[0]->getNumericProperty("plugin_cityDopmerTalkCount") == 0 &&
                f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey).empty() && f.actorFactories == 0 &&
                !f.map->tryBeginSaveSnapshot().has_value(),
            "raw uint64/signed32 overflow cannot alias a source integer through CJson dump before admitted effects");
    }
    for (const std::string raw : {"-2147483648", "2147483647"}) {
        SevenSunsMerchantFixture f;
        f.map->setStringProperty("plugin_citySourceGlobals", "city-json:{\"GLOBAL\":{\"Laola\":" + raw + "}}");
        auto flow = f.beginMerchant();
        SevenSunsMerchantFixture::step(*flow, 0);
        auto globals = json::parse(f.map->getStringProperty("plugin_citySourceGlobals").substr(10));
        expect_true(globals.at("GLOBAL").at("Laola").dump() == raw && f.map->tryBeginSaveSnapshot().has_value(),
                    "valid signed32 endpoints remain exact source integers and survive unrelated first-choice writes");
    }
}

#include "seven_suns_merchant_stock_cases.h"

void testSevenSunsMerchantAllThirteenPathsCoverTwentyFourNativeEdges() {
    struct Path {
        int prior;
        std::vector<int> edges;
        bool reveal;
    };
    const std::array<Path, 13> paths{{
        {0, {0, 3}, false},
        {0, {1, 4, 8}, false},
        {0, {1, 5, 9, 7}, false},
        {0, {1, 5, 10, 8}, false},
        {0, {1, 5, 11, 12}, true},
        {0, {1, 6, 7}, false},
        {0, {2, 7}, false},
        {1, {13, 16}, false},
        {1, {14, 17}, true},
        {1, {15, 17}, true},
        {2, {18, 21}, true},
        {2, {19, 22}, true},
        {2, {20, 23}, true},
    }};
    std::set<int> covered;
    for (const auto &path : paths) {
        SevenSunsMerchantFixture f;
        f.earlierConversations(path.prior);
        auto flow = f.beginMerchant();
        expect_true(flow->view().at("status").get<std::string>() == "ready", "supported native DOPMER flow starts");
        auto answer = SevenSunsMerchantFixture::finish(*flow, path.edges);
        for (int edge : path.edges)
            covered.insert(edge);
        expect_true(
            answer.at("status").get<std::string>() == "closed" &&
                answer.at("revealRequested").get<bool>() == path.reveal &&
                f.protectedActors[0]->getNumericProperty("plugin_cityDopmerTalkCount") == path.prior + 1 &&
                f.merchantRow().at("edges").size() == path.edges.size() &&
                f.merchantRow().at("lastEdge").get<int>() == path.edges.back() &&
                f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) == f.protectedActors[0] &&
                f.actorFactories == 0 && f.merchantDestroyed == 0 && f.player->getQuests().empty() &&
                f.map->tryBeginSaveSnapshot().has_value(),
            "all source paths close with exact prefix/count/global effects and no immediate replacement or journal");
        auto globals = json::parse(std::string_view(f.map->getStringProperty("plugin_citySourceGlobals")).substr(10));
        if (path.reveal)
            expect_true(globals.at("GLOBAL").at("Doppleganger").get<int>() == 1 &&
                            globals.at("GLOBAL").at("Laola").get<int>() == 1,
                        "reveal source globals commit before coordinator turn");
    }
    expect_true(covered.size() == 24 && *covered.begin() == 0 && *covered.rbegin() == 23,
                "native source path inventory covers every one of the24 audited DOPMER edges");
}

void testSevenSunsMerchantInitiationCancelReopenAndLegacyRefusalAreOwned() {
    SevenSunsMerchantFixture f;
    for (int count = 1; count <= 3; ++count) {
        auto flow = f.beginMerchant();
        auto view = flow->view();
        expect_true(
            view.at("sourceTalkCount").get<int>() == count &&
                view.at("state").get<int>() == (count == 1   ? 0
                                                : count == 2 ? 7
                                                             : 10) &&
                f.protectedActors[0]->getNumericProperty("plugin_cityTalkCount") == 0 &&
                f.map->getStringProperty("plugin_citySourceGlobals").empty() &&
                f.map->tryBeginSaveSnapshot().has_value(),
            "native source count commits at admitted initiation, independently of a selected reply and generic talk");
        const auto receipt = f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey);
        flow->close();
        flow.reset();
        expect_true(f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey) == receipt,
                    "cancel never rewinds an admitted source initiation");
    }
    auto fourth = f.beginMerchant();
    expect_true(fourth->view().at("status").get<std::string>() == "refused" &&
                    fourth->view().at("reason").get<std::string>() == "noAuditedEntry" &&
                    fourth->view().at("lineage").get<std::string>() == SevenSunsMerchantFixture::Names[0] &&
                    f.protectedActors[0]->getNumericProperty("plugin_cityDopmerTalkCount") == 3,
                "source countthree has no audited fourth entry and is not silently saturated");
    SevenSunsMerchantFixture legacy;
    legacy.protectedActors[0]->setNumericProperty("plugin_cityTalkCount", 8);
    auto rejected = legacy.beginMerchant();
    expect_true(rejected->view().at("reason").get<std::string>() == "legacyCountUnknown" &&
                    legacy.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey).empty() &&
                    legacy.map->tryBeginSaveSnapshot().has_value(),
                "generic legacy count cannot manufacture source authority");
}

void testSevenSunsMerchantCoordinatorReplacesOnlyTheActiveSourceFloorWithoutCredit() {
    SevenSunsMerchantFixture f;
    const auto expectUnsettled = [&](std::size_t start) {
        for (std::size_t i = start; i < SevenSunsMerchantFixture::Names.size(); ++i) {
            const auto key = std::string("plugin_citySevenSunsMerchantNew_") + SevenSunsMerchantFixture::Names[i];
            expect_true(!f.clock->hasProperty(key), "an unsettled lineage has no replacement property");
            expect_true(!f.replacement(i), "an absent replacement property returns a null fixture observation");
            expect_true(!f.clock->hasProperty(key), "observing an absent replacement must not create its property");
        }
    };
    expectUnsettled(0);
    auto flow = f.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    expectUnsettled(0);
    const auto objects = f.map->getObjects().size(), triggers = f.map->getEventHandler()->getTriggers().size();
    const int gold = f.player->getGold(), xp = f.player->getExp();
    f.map->setTurn(17);
    auto first = f.settle();
    expect_true(first.at("checked").get<int>() == 4 && first.at("replaced").get<int>() == 2 && f.replacement(0) &&
                    f.replacement(1) && !f.replacement(2) && !f.replacement(3) &&
                    f.map->getObjectByName(SevenSunsMerchantFixture::Names[2]) == f.protectedActors[2],
                "shared reveal settles exactly the two eligible active-floor actors and leaves the other floor intact");
    expectUnsettled(2);
    for (std::size_t i = 0; i < 2; ++i) {
        auto replacement = f.replacement(i);
        expect_true(replacement != f.protectedActors[i] &&
                        replacement->getName() == SevenSunsMerchantFixture::Names[i] &&
                        replacement->getStringProperty("sourceCreature") == "DOPPSS" &&
                        replacement->getStringProperty("sourceActor") == SevenSunsMerchantFixture::Sources[i] &&
                        replacement->getStringProperty("sourceArea") == "AR0601" &&
                        replacement->getStringProperty("simulationRegion") == "AR0601" && !replacement->isNpc() &&
                        replacement->getTypeId() == "citySevenSunsRevealedDoppss" && replacement->getHp() == 28 &&
                        replacement->getStats()->getDmgMin() == 1 && replacement->getStats()->getDmgMax() == 12 &&
                        replacement->getStats()->getHit() == 75 && replacement->getWeapon() &&
                        replacement->getWeapon()->getBoolProperty("plugin_cityUndroppable") &&
                        f.oldOwnershipIntact(i) && f.merchantRow(i).at("settledTurn").get<int>() == 17,
                    "distinct native replacement retains lineage and actual weapon/body conversion without "
                    "transferring old stock");
    }
    expect_true(f.map->getObjects().size() == objects && f.map->getEventHandler()->getTriggers().size() == triggers &&
                    f.merchantDestroyed == 0 && f.newDestroyed == 0 && f.player->getGold() == gold &&
                    f.player->getExp() == xp && f.map->getObjectByName("cityAr0601Actor2") == f.warning &&
                    f.map->getObjectByName("cityAr0603Actor1") == f.protectedActors[4] &&
                    f.map->getObjectByName("cityAr0603Actor2") == f.protectedActors[5] &&
                    !f.map->getBoolProperty("plugin_cityCombatObserved_AR0601"),
                "quiet replacement gives no old death/loot/XP/combat observation and preserves DOPPSM/Jhasso/basement "
                "controls");
    f.focus(2);
    f.map->setTurn(18);
    auto second = f.settle();
    expect_true(second.at("checked").get<int>() == 4 && second.at("replaced").get<int>() == 2 && f.replacement(2) &&
                    f.replacement(3) && f.merchantRow(2).at("settledTurn").get<int>() == 18,
                "later real active-floor scheduling can independently reveal the remaining two source lineages");
}

void testSevenSunsMerchantSharedGlobalsKeepSourceOrderCaseAndOtherScopes() {
    SevenSunsMerchantFixture f;
    f.map->setStringProperty("plugin_citySourceGlobals",
                             "city-json:{\"GLOBAL\":{\"cHeCkEdSeVeNsUnS\":1,\"dOpPlEgAnGeR\":0,\"Laola\":73,\"Other\":"
                             "9},\"global\":{\"Keep\":17}}");
    std::vector<std::pair<int, int>> revealWrites;
    std::pair<int, int> previous{0, 73};
    auto observe = [&] {
        auto text = f.map->getStringProperty("plugin_citySourceGlobals");
        auto snapshot = json::parse(std::string_view(text).substr(10)).at("GLOBAL");
        std::pair<int, int> current{snapshot.at("dOpPlEgAnGeR").get<int>(), snapshot.at("Laola").get<int>()};
        if (current != previous) {
            revealWrites.push_back(current);
            previous = current;
        }
    };
    auto flow = f.beginMerchant(0, observe);
    SevenSunsMerchantFixture::step(*flow, 1);
    auto intermediate = json::parse(std::string_view(f.map->getStringProperty("plugin_citySourceGlobals")).substr(10));
    expect_true(intermediate.at("GLOBAL").at("cHeCkEdSeVeNsUnS").get<int>() == 2 &&
                    intermediate.at("GLOBAL").at("dOpPlEgAnGeR").get<int>() == 0 &&
                    intermediate.at("GLOBAL").at("Laola").get<int>() == 73 &&
                    f.map->getBoolProperty("plugin_cityHistoryFrozen"),
                "first source choice sets Checked2 without inventing the later reveal and freezes history natively");
    SevenSunsMerchantFixture::finish(*flow, {5, 11, 12});
    flow.reset();
    auto final = json::parse(std::string_view(f.map->getStringProperty("plugin_citySourceGlobals")).substr(10));
    expect_true(final.at("GLOBAL").at("dOpPlEgAnGeR").get<int>() == 1 &&
                    final.at("GLOBAL").at("Laola").get<int>() == 1 && !final.at("GLOBAL").contains("Doppleganger") &&
                    final.at("GLOBAL").at("Other").get<int>() == 9 && final.at("global").at("Keep").get<int>() == 17,
                "classic name casing and literal GLOBAL scope remain distinct");
    expect_true(revealWrites == std::vector<std::pair<int, int>>{{1, 73}, {1, 1}},
                "native continuation witnesses Doppleganger1 before the separate Laola1 write");
}

void testSevenSunsMerchantRejectsStaleEpochRegionActorPlayerAndRevision() {
    for (int mode = 0; mode < 6; ++mode) {
        SevenSunsMerchantFixture f;
        auto flow = f.beginMerchant();
        const auto before = f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey);
        if (mode == 0) {
            auto other = std::make_shared<CMap>();
            other->setGame(f.game);
            f.game->setMap(other);
            f.game->setMap(f.map);
        }
        if (mode == 1) {
            f.map->setActiveSimulationRegion("AR0602");
            f.map->setActiveSimulationRegion("AR0601");
        }
        if (mode == 2)
            f.protectedActors[0]->setStringProperty("sourceActor", "AR0601#actor3");
        if (mode == 3)
            f.player->setGame(std::make_shared<CGame>());
        if (mode == 4)
            f.clock->setGame(std::make_shared<CGame>());
        bool rejected = false;
        try {
            flow->advance(flow->view().at("revision").get<int>() + (mode == 5), 0);
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(
            rejected && f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey) == before &&
                f.map->getStringProperty("plugin_citySourceGlobals").empty() && f.actorFactories == 0,
            "map/area away-back, source/player/clock replacement and wrong revision refuse before source effects");
        flow->close();
    }
}

void testSevenSunsMerchantFactoryReentryOrOwnerMutationCannotAcknowledgeReplacement() {
    for (int mode = 0; mode < 5; ++mode) {
        SevenSunsMerchantFixture f;
        auto flow = f.beginMerchant();
        SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
        flow.reset();
        std::shared_ptr<CGame> foreign = std::make_shared<CGame>();
        f.duringActionFactory = [&] {
            if (mode == 0)
                f.protectedActors[0]->setNumericProperty("sourceAllegiance", 255);
            if (mode == 1)
                f.map->setGame(foreign);
            if (mode == 2)
                f.player->setGame(foreign);
            if (mode == 3)
                f.clock->setGame(foreign);
            if (mode == 4) {
                try {
                    auto nested = f.beginMerchant();
                } catch (const std::exception &) {
                }
            }
        };
        bool rejected = false;
        try {
            f.settle();
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) == f.protectedActors[0] &&
                        f.merchantDestroyed == 0 && f.oldOwnershipIntact() &&
                        !f.map->tryBeginSaveSnapshot().has_value() &&
                        f.merchantRow().at("status").get<std::string>() == "pending",
                    "admitted callback source/owner/reentry failure retains old owner, pending receipt and quarantine");
    }
}

void testSevenSunsMerchantAdmissionAndLegacyEligibilityRetryWithoutMutation() {
    SevenSunsMerchantFixture f;
    auto flow = f.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    const auto receipt = f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey);
    auto snapshot = f.map->tryBeginSaveSnapshot();
    auto answer = f.settle();
    expect_true(snapshot && answer.at("status").get<std::string>() == "retry" &&
                    answer.at("replaced").get<int>() == 0 &&
                    f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey) == receipt &&
                    f.actorFactories == 0 && f.merchantDestroyed == 0,
                "closed save admission retries without mutation or constructors");
    snapshot.reset();
    f.protectedActors[1]->setNumericProperty("plugin_cityTalkCount", 5);
    auto later = f.settle();
    expect_true(later.at("status").get<std::string>() == "retry" && later.at("replaced").get<int>() == 1 &&
                    !f.replacement(1) &&
                    f.map->getObjectByName(SevenSunsMerchantFixture::Names[1]) == f.protectedActors[1],
                "unknown legacy source count is not silently reset by background replacement");
}

void testSevenSunsMerchantFailureAfterDetachQuarantinesBothRetainedOwners() {
    SevenSunsMerchantFixture f;
    auto flow = f.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    bool rejected = false;
    try {
        CSevenSunsMerchantDialogue::settle(f.game, f.clock, [&] {
            if (!f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]))
                throw std::runtime_error("merchant post-detach continuation failed");
        });
    } catch (const std::runtime_error &error) {
        rejected = std::string(error.what()) == "merchant post-detach continuation failed";
    }
    expect_true(
        rejected && !f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) &&
            f.clock->getObjectProperty("plugin_citySevenSunsMerchantOld_cityAr0601Actor1") == f.protectedActors[0] &&
            f.replacement() && f.replacement() != f.protectedActors[0] && f.oldOwnershipIntact() &&
            f.merchantDestroyed == 0 && !f.map->tryBeginSaveSnapshot().has_value() &&
            f.merchantRow().at("status").get<std::string>() == "pending",
        "post-removal signal/navigation/continuation failure preserves both references, original error and quarantine");
}

void testSevenSunsMerchantRepeatedSettlementNeverReseedsChangedOrDefeatedStock() {
    SevenSunsMerchantFixture f;
    auto flow = f.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    f.settle();
    auto actor = f.replacement();
    expect_true(actor != nullptr, "first coordinator turn creates a real new actor");
    if (!actor)
        return;
    actor->setHp(1);
    actor->setGold(actor->getGold() + 11);
    for (const auto &item : actor->getItems()) {
        actor->removeItem(item);
        f.player->addItem(item);
        break;
    }
    const auto receipt = f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey);
    const auto factories = f.actorFactories, items = f.itemFactories;
    auto replay = f.settle();
    expect_true(replay.at("replaced").get<int>() == 0 && f.replacement() == actor && actor->getHp() == 1 &&
                    f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey) == receipt &&
                    f.actorFactories == factories && f.itemFactories == items,
                "settled replay validates ownership/certificate without restoring legitimate HP/gold/items");
    actor->setHp(0);
    f.map->removeObject(actor);
    auto dead = f.settle();
    expect_true(
        dead.at("replaced").get<int>() == 0 && f.replacement() == actor && f.newDestroyed == 1 &&
            f.merchantDestroyed == 0 && f.oldOwnershipIntact() && actor->getWeapon() &&
            actor->getWeapon()->getBoolProperty("plugin_cityUndroppable") && f.actorFactories == factories &&
            f.itemFactories == items,
        "same-name existing death hook observes actual new death; retired old merchant is never killed or reseeded");
}

void testSevenSunsMerchantMissingAttackWitnessNeverUsesDamageAsRevealAuthority() {
    SevenSunsMerchantFixture f;
    auto flow = f.beginMerchant();
    expect_true(!flow->view().at("attackRevealSupported").get<bool>(),
                "attack-attempt/offensive-spell support remains explicit pending");
    flow->close();
    flow.reset();
    f.protectedActors[0]->setHp(1);
    auto turn = f.settle();
    expect_true(turn.at("replaced").get<int>() == 0 && !f.replacement() &&
                    f.map->getStringProperty("plugin_citySourceGlobals").empty(),
                "a damage/HP change alone cannot fabricate the source AttackedBy action or replacement predicate");
}

void testSevenSunsMerchantIdleFlowDoesNotRetainGameOwner() {
    SevenSunsMerchantFixture f;
    auto flow = f.beginMerchant();
    std::weak_ptr<CGame> game = f.game;
    f.game.reset();
    expect_true(game.expired(), "merchant UI suspension retains only a weak game owner");
    bool refused = false;
    try {
        SevenSunsMerchantFixture::step(*flow, 0);
    } catch (const std::exception &) {
        refused = true;
    }
    expect_true(refused, "dropped game owner cannot accept a later source edge");
    flow->close();
}

void testSevenSunsMerchantCombatParticipantClaimRetriesBeforeQuietRemoval() {
    SevenSunsMerchantFixture f;
    auto flow = f.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    auto control = std::make_shared<ReentrantEncounterController>();
    int calls = 0;
    bool observed = false;
    control->reenter = [&] {
        if (++calls != 1)
            return;
        const auto before = f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey);
        auto result = f.settle();
        observed = result.at("status").get<std::string>() == "retry" && !f.replacement() &&
                   f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) == f.protectedActors[0] &&
                   f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey) == before;
    };
    f.player->setFightController(control);
    f.protectedActors[0]->setFightController(std::make_shared<NoProgressFightController>());
    CFightHandler::fightManyResult(f.player, {f.protectedActors[0]});
    expect_true(observed && calls > 0,
                "actual native encounter ownership prevents source quiet removal before any field writes");
}

void testSevenSunsMerchantNativeUiFlowOwnsCursorClosesAndRejectsOversizedEdges() {
    ScriptFlowNativeObjectTypes types;
    for (int variant = 0; variant < 3; ++variant) {
        SevenSunsMerchantFixture f;
        pybind11::dict scope;
        scope["clock"] = nativeFlowObject(f.clock);
        scope["actor"] = nativeFlowObject(f.protectedActors[0]);
        scope["variant"] = variant;
        pybind11::exec(R"(
events=[]
def merchant():
    try:
        args=(clock,actor) if variant!=1 else (clock,)
        view=yield {'operation':'gui.beginSevenSunsMerchant','args':args,'kwargs':{}}
        for edge in (0,3):
            selected=edge+(4294967296 if variant==2 else 0)
            view=yield {'operation':'gui.advanceSevenSunsMerchant','args':(view['revision'],selected),'kwargs':{}}
        events.append(view['status'])
    finally:
        events.append('closed')
)",
                       scope);
        auto flow =
            f.game->getScriptHandler()->createCallbackFlow(scope["merchant"].cast<pybind11::function>(), f.game);
        auto pending = f.game->getContext()->spawnTask(f.game->getGuiHandler()->runScriptFlowAsync(std::move(flow)));
        expect_true(pumpHandlerUntil([&] { return pending.finished(); }), "finite merchant native UI flow settles");
        bool rejected = false;
        try {
            pending.get();
        } catch (const std::exception &) {
            rejected = true;
        }
        const auto events = scope["events"].cast<pybind11::list>();
        expect_true(events.size() == (variant == 0 ? 2 : 1) &&
                        events[events.size() - 1].cast<std::string>() == "closed" && rejected == (variant != 0) &&
                        f.actorFactories == 0 && f.merchantDestroyed == 0,
                    "real native-token flow drives only bounded source edges and closes on invalid arity/overflow");
        scope.clear();
        f.game->getContext()->shutdown();
    }
}

void testSevenSunsMerchantRetiredOldEffectCycleEndsWithMapWhileGameLives() {
    std::shared_ptr<CGame> livingGame;
    std::weak_ptr<CMap> oldMap;
    std::weak_ptr<CCreature> oldActor;
    std::weak_ptr<CEffect> oldEffect;
    {
        SevenSunsMerchantFixture f;
        livingGame = f.game;
        oldMap = f.map;
        oldActor = f.protectedActors[0];
        oldEffect = f.oldEffects[0];
        auto flow = f.beginMerchant();
        SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
        flow.reset();
        f.settle();
        auto destination = std::make_shared<CMap>();
        destination->setGame(livingGame);
        livingGame->setMap(destination);
    }
    vstd::event_loop<>::instance()->runReady();
    expect_true(livingGame->getContext()->isActive() && oldMap.expired() && oldActor.expired() && oldEffect.expired(),
                "retired old merchant/effect aliases expire through map-owned teardown without explicit cleanup or "
                "game shutdown");
}

void testSevenSunsMerchantWholeMapCodecPreservesOldNewAliasesAndOnceOwnedReceipt() {
    SevenSunsMerchantFixture original;
    auto flow = original.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    original.settle();
    auto snapshot = CSerialization::serializeExpected(original.map, "unit-merchant-whole-map");
    expect_true(snapshot.has_value(),
                "whole city-scene graph includes ordinary replacement refs and retired lifetime collection");
    if (!snapshot)
        return;
    SevenSunsMerchantFixture restored;
    auto objects = restored.game->getObjectHandler();
    objects->registerType("CMap", [] { return std::make_shared<CMap>(); });
    objects->registerType("CPlayer", [] { return std::make_shared<CPlayer>(); });
    objects->registerType("CBuilding", [] { return std::make_shared<CBuilding>(); });
    objects->registerType("CEffect", [] { return std::make_shared<CEffect>(); });
    objects->registerType("CTrigger", [] { return std::make_shared<CTrigger>(); });
    objects->registerType("CController", [] { return std::make_shared<CController>(); });
    std::weak_ptr<CMap> dyingMap;
    std::weak_ptr<CCreature> dyingActor;
    std::weak_ptr<CEffect> dyingEffect;
    {
        auto decoded = CSerialization::deserializeExpected<std::shared_ptr<CGameObject>>(restored.game, *snapshot,
                                                                                         "unit-merchant-restored-map");
        expect_true(decoded.has_value(), "actual native map codec restores fixed source stock and all old/new aliases");
        if (!decoded)
            return;
        auto map = std::dynamic_pointer_cast<CMap>(*decoded);
        expect_true(map != nullptr, "the whole-map codec must return an actual map");
        if (!map)
            return;
        auto registeredPlayer = std::dynamic_pointer_cast<CPlayer>(map->getObjectByName("player"));
        expect_true(registeredPlayer && !map->getAssignedPlayer() && map->getActiveSimulationRegion() == "AR0601",
                    "raw map decoding restores the registered player and source floor before cache rehydration");
        std::string playerRestoreError;
        const bool playerRestored = map->restorePlayerAfterLoad(playerRestoreError);
        expect_true(playerRestored && playerRestoreError.empty() && map->getAssignedPlayer() == registeredPlayer &&
                        map->getObjectByName("player") == registeredPlayer && registeredPlayer &&
                        registeredPlayer->getGame() == restored.game,
                    "the production post-codec restore must assign the same registered player before settlement");
        if (!playerRestored)
            return;
        restored.game->setMap(map);
        auto clock = map->getObjectByName("cityClock");
        auto old = std::dynamic_pointer_cast<CCreature>(
            clock->getObjectProperty("plugin_citySevenSunsMerchantOld_cityAr0601Actor1"));
        auto current = std::dynamic_pointer_cast<CCreature>(
            clock->getObjectProperty("plugin_citySevenSunsMerchantNew_cityAr0601Actor1"));
        expect_true(old && current && old != current && map->getObjectByName("cityAr0601Actor1") == current &&
                        old->isAlive() && old->getEffects().size() == 1 &&
                        (*old->getEffects().begin())->getCaster() == old &&
                        (*old->getEffects().begin())->getVictim() == old && current->getWeapon() &&
                        current->getStringProperty("sourceActor") == "AR0601#actor1",
                    "codec roundtrip retains distinct old and new owners, old self-effect aliases and actual new "
                    "equipped weapon");
        const auto receipt = map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey);
        auto replay = CSevenSunsMerchantDialogue::settle(restored.game, clock, {});
        expect_true(replay.at("replaced").get<int>() == 0 &&
                        map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey) == receipt &&
                        map->tryBeginSaveSnapshot().has_value(),
                    "restored certified replacement receipt never rerolls or reseeds");
        dyingMap = map;
        dyingActor = old;
        if (old && !old->getEffects().empty())
            dyingEffect = *old->getEffects().begin();
        auto destination = std::make_shared<CMap>();
        destination->setGame(restored.game);
        restored.game->setMap(destination);
    }
    vstd::event_loop<>::instance()->runReady();
    expect_true(restored.game->getContext()->isActive() && dyingMap.expired() && dyingActor.expired() &&
                    dyingEffect.expired(),
                "restored whole-map retirement cleanup breaks old actor/effect cycles while its game remains live");
}

void testSevenSunsMerchantRevisionLimitRefusesWithoutUnreadableOwnOutput() {
    SevenSunsMerchantFixture f;
    auto first = f.beginMerchant();
    first->close();
    first.reset();
    auto doc = f.merchantDocument();
    doc["actors"][SevenSunsMerchantFixture::Names[0]]["revision"] = 999999;
    f.map->setStringProperty(SevenSunsMerchantFixture::MerchantStateKey, "city-json:" + doc.dump());
    const auto before = f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey);
    auto refused = f.beginMerchant();
    expect_true(refused->view().at("reason").get<std::string>() == "revisionLimit" &&
                    f.map->getStringProperty(SevenSunsMerchantFixture::MerchantStateKey) == before &&
                    f.protectedActors[0]->getNumericProperty("plugin_cityDopmerTalkCount") == 1 &&
                    f.map->tryBeginSaveSnapshot().has_value(),
                "admitted revision cap never creates its own next unreadable receipt");
}

int main() {
#if defined(_WIN32)
    native_test_diagnostics::installWindowsHandlerCrashDiagnostics();
#endif
    pybind11::scoped_interpreter guard{};
    pybind11::module_::import("sys").attr("path").attr("insert")(0, GAME_HANDLER_TEST_PYTHON_ROOT);
    pybind11::module_::import("ui");
    const auto runTimedGuiCancellationTest = [](const char *name, void (*test)()) {
        const auto started = std::chrono::steady_clock::now();
        std::cout << "[handler-test] ENTER " << name << std::endl;
        test();
        const auto elapsed =
            std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - started).count();
        std::cout << "[handler-test] EXIT " << name << " elapsedMs=" << elapsed << std::endl;
    };
    nativeTestProfile().run("testGameplayMetadataIsAvailableBeforePluginLoading",
                            testGameplayMetadataIsAvailableBeforePluginLoading);

    nativeTestProfile().run("testScriptFlowBootstrapDoesNotRequireGameplayModule",
                            testScriptFlowBootstrapDoesNotRequireGameplayModule);
    nativeTestProfile().run("testSyncGuiWaitReleasesLastGameOwner", testSyncGuiWaitReleasesLastGameOwner);
    nativeTestProfile().run("test_script_handler_executes_commands_and_wraps_functions",
                            test_script_handler_executes_commands_and_wraps_functions);
    nativeTestProfile().run("test_handler_constructors_are_covered_by_native_tests",
                            test_handler_constructors_are_covered_by_native_tests);
    nativeTestProfile().run("test_creature_scale_preserves_level_plus_sw_invariant",
                            test_creature_scale_preserves_level_plus_sw_invariant);
    nativeTestProfile().run("test_tooltip_handler_exposes_present_archetypes_without_duplicate_descriptions",
                            test_tooltip_handler_exposes_present_archetypes_without_duplicate_descriptions);
    nativeTestProfile().run("test_rng_handler_builds_encounters_from_concrete_creature_sw",
                            test_rng_handler_builds_encounters_from_concrete_creature_sw);
    nativeTestProfile().run("test_rng_handler_scales_fresh_creatures_before_map_insertion",
                            test_rng_handler_scales_fresh_creatures_before_map_insertion);
    nativeTestProfile().run("test_rng_handler_excludes_noncombatants_from_encounters",
                            test_rng_handler_excludes_noncombatants_from_encounters);
    nativeTestProfile().run("test_rng_handler_excludes_archetype_definitions_from_encounters",
                            test_rng_handler_excludes_archetype_definitions_from_encounters);
    nativeTestProfile().run("test_rng_handler_excludes_player_templates_from_encounters",
                            test_rng_handler_excludes_player_templates_from_encounters);
    nativeTestProfile().run("test_rng_handler_captures_encounter_power_and_scale_baseline",
                            test_rng_handler_captures_encounter_power_and_scale_baseline);
    nativeTestProfile().run("test_rng_handler_encounter_candidates_stay_in_stable_power_buckets",
                            test_rng_handler_encounter_candidates_stay_in_stable_power_buckets);
    nativeTestProfile().run("test_rng_handler_distinguishes_associated_classes_with_neutral_scale",
                            test_rng_handler_distinguishes_associated_classes_with_neutral_scale);
    nativeTestProfile().run("test_creature_subtype_inventory_is_enumerable_on_loaded_game",
                            test_creature_subtype_inventory_is_enumerable_on_loaded_game);
    nativeTestProfile().run("test_event_handler_trigger_registration_uses_named_comparison_helpers",
                            test_event_handler_trigger_registration_uses_named_comparison_helpers);
    nativeTestProfile().run("testObjectEntryTracePreservesActualCauseAndContactBeforeNpcDeparture",
                            testObjectEntryTracePreservesActualCauseAndContactBeforeNpcDeparture);
    nativeTestProfile().run("testObjectEntryTraceRequiresOptInAndCanonicalColocatedCause",
                            testObjectEntryTraceRequiresOptInAndCanonicalColocatedCause);
    nativeTestProfile().run("testAsyncObjectEntryTraceWaitsForHooksAndPreservesContactOnResume",
                            testAsyncObjectEntryTraceWaitsForHooksAndPreservesContactOnResume);
    nativeTestProfile().run("test_fight_handler_rejects_stale_and_cross_map_participants",
                            test_fight_handler_rejects_stale_and_cross_map_participants);
    nativeTestProfile().run("test_fight_handler_attributes_lethal_effects_to_valid_casters",
                            test_fight_handler_attributes_lethal_effects_to_valid_casters);
    nativeTestProfile().run("test_fight_handler_reports_explicit_outcomes_and_final_status",
                            test_fight_handler_reports_explicit_outcomes_and_final_status);
    nativeTestProfile().run("test_fight_handler_reports_invalid_result_metadata",
                            test_fight_handler_reports_invalid_result_metadata);
    nativeTestProfile().run("test_fight_handler_reports_cancelled_quit_event",
                            test_fight_handler_reports_cancelled_quit_event);
    nativeTestProfile().run("test_fight_handler_ends_original_started_controllers",
                            test_fight_handler_ends_original_started_controllers);
    nativeTestProfile().run("test_fight_handler_reports_cancelled_closed_fight_panel", [&] {
        runTimedGuiCancellationTest("test_fight_handler_reports_cancelled_closed_fight_panel",
                                    test_fight_handler_reports_cancelled_closed_fight_panel);
    });
    nativeTestProfile().run("test_player_fight_controller_returns_cancelled_when_attached_fight_panel_cancels", [&] {
        runTimedGuiCancellationTest("test_player_fight_controller_returns_cancelled_when_attached_fight_panel_cancels",
                                    test_player_fight_controller_returns_cancelled_when_attached_fight_panel_cancels);
    });
    nativeTestProfile().run("test_fight_handler_returns_cancelled_when_player_control_cancels", [&] {
        runTimedGuiCancellationTest("test_fight_handler_returns_cancelled_when_player_control_cancels",
                                    test_fight_handler_returns_cancelled_when_player_control_cancels);
    });
    nativeTestProfile().run("test_fight_panel_resets_status_between_sequential_encounters",
                            test_fight_panel_resets_status_between_sequential_encounters);
    nativeTestProfile().run("testEffectTickCappingAndExpiryIgnoreAllocationOrder",
                            testEffectTickCappingAndExpiryIgnoreAllocationOrder);
    nativeTestProfile().run("testEffectTickLethalityTimingAndCasterIgnoreAllocationOrder",
                            testEffectTickLethalityTimingAndCasterIgnoreAllocationOrder);
    nativeTestProfile().run("testDuplicateDefeatRejectsDuringRealLootAndRemoval",
                            testDuplicateDefeatRejectsDuringRealLootAndRemoval);
    nativeTestProfile().run("testConcurrentPlayerDefeatPublishesOnlyRecoveredReceipt",
                            testConcurrentPlayerDefeatPublishesOnlyRecoveredReceipt);
    nativeTestProfile().run("testDefeatCancellationAndFailureDrainOwnedRecovery",
                            testDefeatCancellationAndFailureDrainOwnedRecovery);
    nativeTestProfile().run("testRecursiveDefeatRejectsBeforeItsOwnRecovery",
                            testRecursiveDefeatRejectsBeforeItsOwnRecovery);
    nativeTestProfile().run("testOverlappingEncounterCannotStartSharedControllers",
                            testOverlappingEncounterCannotStartSharedControllers);
    nativeTestProfile().run("testDefeatAdmissionRefusalAndAbandonedOwnersPreserveBoundaries",
                            testDefeatAdmissionRefusalAndAbandonedOwnersPreserveBoundaries);
    nativeTestProfile().run("testFailedOrdinaryDefeatRequiresVerifiedRestore",
                            testFailedOrdinaryDefeatRequiresVerifiedRestore);
    nativeTestProfile().run("testDefeatCallbackShutdownKeepsContextTaskAncestry",
                            testDefeatCallbackShutdownKeepsContextTaskAncestry);
    nativeTestProfile().run("testEncounterParticipantClaimsReleaseAfterThrowAndCancel",
                            testEncounterParticipantClaimsReleaseAfterThrowAndCancel);
    nativeTestProfile().run("testEncounterOwnershipIgnoresSanitizedIneligibleCandidates",
                            testEncounterOwnershipIgnoresSanitizedIneligibleCandidates);
    nativeTestProfile().run("testDefeatRecoveryCertificationRejectsReplacedOrUnfinishedOwners",
                            testDefeatRecoveryCertificationRejectsReplacedOrUnfinishedOwners);
    nativeTestProfile().run("testInternalDefeatLeaseSurvivesParentControllerCleanup",
                            testInternalDefeatLeaseSurvivesParentControllerCleanup);
    nativeTestProfile().run("testOwnedDefeatStopsAfterCallbackPublicationBeforeFurtherRewards",
                            testOwnedDefeatStopsAfterCallbackPublicationBeforeFurtherRewards);
    nativeTestProfile().run("testOwnedDefeatLootContinuationRejectsStalePublicationAndCancellation",
                            testOwnedDefeatLootContinuationRejectsStalePublicationAndCancellation);
    nativeTestProfile().run("testOwnedDefeatRemovalCannotCertifyAnAwayBackPublication",
                            testOwnedDefeatRemovalCannotCertifyAnAwayBackPublication);
    nativeTestProfile().run("testOwnedDefeatGuardsLazyRngFactoryEnumeration",
                            testOwnedDefeatGuardsLazyRngFactoryEnumeration);
    nativeTestProfile().run("testOwnedDefeatStopsBeforeSecondRandomLootFactory",
                            testOwnedDefeatStopsBeforeSecondRandomLootFactory);
    nativeTestProfile().run("testOwnedDefeatNestedFactoryStopsBeforeNextPropertyAndConstructor",
                            testOwnedDefeatNestedFactoryStopsBeforeNextPropertyAndConstructor);
    nativeTestProfile().run("testOwnedDefeatFirstMetadataCallbackStopsBeforeSecondMetadataAndSetter",
                            testOwnedDefeatFirstMetadataCallbackStopsBeforeSecondMetadataAndSetter);
    nativeTestProfile().run("testOwnedDefeatCodecBoundaryPreservesOriginalFailureAndStopsContinuation",
                            testOwnedDefeatCodecBoundaryPreservesOriginalFailureAndStopsContinuation);
    nativeTestProfile().run("testOwnedDefeatGraphActorBindingPreservesPrimaryBeforeRootAndProperties",
                            testOwnedDefeatGraphActorBindingPreservesPrimaryBeforeRootAndProperties);
    nativeTestProfile().run("testScopedEquipmentTailStopsAfterCallbackInvalidation",
                            testScopedEquipmentTailStopsAfterCallbackInvalidation);
    nativeTestProfile().run("testQueuedSceneTransitionWaitsForOwnedDefeatAndControllerCleanup",
                            testQueuedSceneTransitionWaitsForOwnedDefeatAndControllerCleanup);
    nativeTestProfile().run("testQueuedSceneCombatDeferralReleasesAfterThrowAndKeepsDirectReplacementCancellation",
                            testQueuedSceneCombatDeferralReleasesAfterThrowAndKeepsDirectReplacementCancellation);
    nativeTestProfile().run("testOwnedDefeatPresentationFollowsSuccessfulControllerCleanup",
                            testOwnedDefeatPresentationFollowsSuccessfulControllerCleanup);
    nativeTestProfile().run("testPublicDefeatPreservesItsIndependentPostedPresentation",
                            testPublicDefeatPreservesItsIndependentPostedPresentation);
    nativeTestProfile().run("testAsyncCombatAwaitsLootWithoutPumpingOrGrantingRewardsEarly",
                            testAsyncCombatAwaitsLootWithoutPumpingOrGrantingRewardsEarly);
    nativeTestProfile().run("testWorkerStartedCombatDefersControllerAndPanelCreationToMain",
                            testWorkerStartedCombatDefersControllerAndPanelCreationToMain);
    nativeTestProfile().run("testOwnedLootCancellationCompensationRetainsExactItemsAndRejectsUncertainReplay",
                            testOwnedLootCancellationCompensationRetainsExactItemsAndRejectsUncertainReplay);
    nativeTestProfile().run("testCancelledLootSettlesStartedRewardsOnceAndSkipsQueuedCombat",
                            testCancelledLootSettlesStartedRewardsOnceAndSkipsQueuedCombat);
    nativeTestProfile().run("testAsyncEventsAwaitOrderedTriggerSnapshotsAfterObjectHooks",
                            testAsyncEventsAwaitOrderedTriggerSnapshotsAfterObjectHooks);
    nativeTestProfile().run("testAsyncLeaveHooksRejectStaleMovesAndCleanCancellation",
                            testAsyncLeaveHooksRejectStaleMovesAndCleanCancellation);
    nativeTestProfile().run("testArrivalHooksRejectChangedMapAndGeneration",
                            testArrivalHooksRejectChangedMapAndGeneration);
    nativeTestProfile().run("testAsyncNamedSpawnsAwaitEntryWithoutPumping",
                            testAsyncNamedSpawnsAwaitEntryWithoutPumping);
    nativeTestProfile().run("testDisposableItemCommitConsumesBeforeReceiptsAndCancellation",
                            testDisposableItemCommitConsumesBeforeReceiptsAndCancellation);
    nativeTestProfile().run("testScriptCallbackFlowUsesInitializedUiModule",
                            testScriptCallbackFlowUsesInitializedUiModule);
    nativeTestProfile().run("testItemPositionCommitOwnsConsumptionBeforeArrivalCancellation",
                            testItemPositionCommitOwnsConsumptionBeforeArrivalCancellation);
    nativeTestProfile().run("testIndividualQuestCancellationHonorsExplicitRewardCommit",
                            testIndividualQuestCancellationHonorsExplicitRewardCommit);
    nativeTestProfile().run("testAsyncRemovalAwaitsDestroyHooksAndFinalizesCancellation",
                            testAsyncRemovalAwaitsDestroyHooksAndFinalizesCancellation);
    nativeTestProfile().run("testAsyncEventHooksStopAfterContextShutdown", testAsyncEventHooksStopAfterContextShutdown);
    nativeTestProfile().run("test_fight_handler_counts_effect_duration_as_progress",
                            test_fight_handler_counts_effect_duration_as_progress);
    nativeTestProfile().run("test_player_quest_completion_ignores_reentry_and_captures_final_callback_state",
                            test_player_quest_completion_ignores_reentry_and_captures_final_callback_state);
    nativeTestProfile().run("test_player_quest_completion_accepts_cleared_active_set",
                            test_player_quest_completion_accepts_cleared_active_set);
    nativeTestProfile().run("test_player_quest_completion_skips_removed_snapshot_entries",
                            test_player_quest_completion_skips_removed_snapshot_entries);
    nativeTestProfile().run("test_player_quest_completion_defers_new_quests_until_next_pass",
                            test_player_quest_completion_defers_new_quests_until_next_pass);
    nativeTestProfile().run("test_player_quest_completion_restores_guard_after_native_exceptions",
                            test_player_quest_completion_restores_guard_after_native_exceptions);
    nativeTestProfile().run("test_player_capture_quest_journal_passes_membership_without_completing",
                            test_player_capture_quest_journal_passes_membership_without_completing);
    nativeTestProfile().run("test_playtest_trace_records_native_limits_and_quest_completion",
                            test_playtest_trace_records_native_limits_and_quest_completion);
    nativeTestProfile().run("test_playtest_trace_environment_targets_and_fallback_ids",
                            test_playtest_trace_environment_targets_and_fallback_ids);
    nativeTestProfile().run("test_fight_handler_records_outcome_trace_metadata",
                            test_fight_handler_records_outcome_trace_metadata);
    nativeTestProfile().run("testAsyncCombatTraceCapturesResourcesBeforeControllerSuspension",
                            testAsyncCombatTraceCapturesResourcesBeforeControllerSuspension);
    nativeTestProfile().run("test_player_respawn_normalizes_wrapped_entry_coords",
                            test_player_respawn_normalizes_wrapped_entry_coords);

    nativeTestProfile().run("testSaveAdmissionRejectsBeforeQuestAndGraphWork",
                            testSaveAdmissionRejectsBeforeQuestAndGraphWork);
    nativeTestProfile().run("testSaveAdmissionOwnersMovesAndSnapshots",
                            testSaveAdmissionOwnersMovesAndSnapshots);
    nativeTestProfile().run("testSaveAdmissionSurvivesMapAndGameOwnerChanges",
                            testSaveAdmissionSurvivesMapAndGameOwnerChanges);
    nativeTestProfile().run("testSaveAdmissionQuarantineRequiresVerifiedInstall",
                            testSaveAdmissionQuarantineRequiresVerifiedInstall);
    nativeTestProfile().run("testAuthoredNativeSavePolicyIsStrictAndPrecedesObjects",
                            testAuthoredNativeSavePolicyIsStrictAndPrecedesObjects);
    nativeTestProfile().run("testVerifiedRestoreReappliesAuthoritativeNativeSavePolicy",
                            testVerifiedRestoreReappliesAuthoritativeNativeSavePolicy);
    nativeTestProfile().run("testVerifiedLoadResumePolicyIsStrictAndPrecedesObjects", testVerifiedLoadResumePolicyIsStrictAndPrecedesObjects);
    nativeTestProfile().run("testVerifiedLoadResumesActualFlowOnlyAfterPostedLeaseRelease", testVerifiedLoadResumesActualFlowOnlyAfterPostedLeaseRelease);
    nativeTestProfile().run("testVerifiedLoadResumeRejectsSupersededWeakBindings", testVerifiedLoadResumeRejectsSupersededWeakBindings);
    nativeTestProfile().run("testUnverifiedOrRejectedLoadsNeverDispatchResume", testUnverifiedOrRejectedLoadsNeverDispatchResume);
    nativeTestProfile().run("testWaitStateSnapshotsPreserveRemainingDurationWithoutRebasingLiveTime",
                            testWaitStateSnapshotsPreserveRemainingDurationWithoutRebasingLiveTime);
    nativeTestProfile().run("testWaitStateRejectsInvalidDurationsMutationsAndDuplicateLeases",
                            testWaitStateRejectsInvalidDurationsMutationsAndDuplicateLeases);
    nativeTestProfile().run("testScriptWaitFlowCompletesAndRejectsInvalidObjectArguments",
                            testScriptWaitFlowCompletesAndRejectsInvalidObjectArguments);
    nativeTestProfile().run("testScriptWaitSurvivesFailedSaveResourceBindingWithoutDispatchingMapChanges",
                            testScriptWaitSurvivesFailedSaveResourceBindingWithoutDispatchingMapChanges);
    nativeTestProfile().run("testScriptWaitCancellationAndMapBindingLossFreezeRemainingTime",
                            testScriptWaitCancellationAndMapBindingLossFreezeRemainingTime);
    nativeTestProfile().run("testSyncScriptWaitReleasesTheFinalGameOwner", testSyncScriptWaitReleasesTheFinalGameOwner);
    nativeTestProfile().run("testSevenSunsWarningRetiredActorEffectCycleEndsWithItsMapWhileGameLives",
                            testSevenSunsWarningRetiredActorEffectCycleEndsWithItsMapWhileGameLives);
    nativeTestProfile().run("testSevenSunsWarningRestoredWholeMapOwnsAndReleasesRetiredEffectCycles",
                            testSevenSunsWarningRestoredWholeMapOwnsAndReleasesRetiredEffectCycles);
    nativeTestProfile().run("testSevenSunsWarningOldMapCleanupPreservesActorAdoptedByAnotherLiveMap",
                            testSevenSunsWarningOldMapCleanupPreservesActorAdoptedByAnotherLiveMap);
    nativeTestProfile().run("testSevenSunsWarningDefaultMapSnapshotOmitsTheEmptyRetirementCollection",
                            testSevenSunsWarningDefaultMapSnapshotOmitsTheEmptyRetirementCollection);
    nativeTestProfile().run("testSevenSunsWarningReflectedOwnerTamperingQuarantinesAndStillCleansCycles",
                            testSevenSunsWarningReflectedOwnerTamperingQuarantinesAndStillCleansCycles);
    nativeTestProfile().run("testSevenSunsWarningSwallowedNestedBeginCannotAcknowledgeRetirement",
                            testSevenSunsWarningSwallowedNestedBeginCannotAcknowledgeRetirement);
    nativeTestProfile().run("testSevenSunsWarningOtherUnsafeQuarantineCannotBecomeSuccess",
                            testSevenSunsWarningOtherUnsafeQuarantineCannotBecomeSuccess);
    nativeTestProfile().run("testSevenSunsWarningCapacityPreflightNeverPublishesAnUnreadableOwnResult",
                            testSevenSunsWarningCapacityPreflightNeverPublishesAnUnreadableOwnResult);
    nativeTestProfile().run("testSevenSunsWarningRejectsOverflowingJsonAuthorityInsteadOfAliasingLowBits",
                            testSevenSunsWarningRejectsOverflowingJsonAuthorityInsteadOfAliasingLowBits);
    nativeTestProfile().run("testSevenSunsWarningUiFlowDispatchOwnsTokensAndRejectsOversizedSourceEdges",
                            testSevenSunsWarningUiFlowDispatchOwnsTokensAndRejectsOversizedSourceEdges);
    nativeTestProfile().run("testSevenSunsWarningJournalMembershipLossCannotBecomeAcceptedRetirement",
                            testSevenSunsWarningJournalMembershipLossCannotBecomeAcceptedRetirement);
    nativeTestProfile().run("testSevenSunsWarningSharedNamesIgnoreAsciiCaseAndRejectAmbiguousAliases",
                            testSevenSunsWarningSharedNamesIgnoreAsciiCaseAndRejectAmbiguousAliases);
    nativeTestProfile().run("testSevenSunsWarningEveryReachableDefaultGlobalPathUsesNativeCursor",
                            testSevenSunsWarningEveryReachableDefaultGlobalPathUsesNativeCursor);
    nativeTestProfile().run("testSevenSunsWarningRetiresSameLivingActorAndPublishesOneJournal",
                            testSevenSunsWarningRetiresSameLivingActorAndPublishesOneJournal);
    nativeTestProfile().run("testSevenSunsWarningCommittedChoiceSurvivesCancellationAndRemainsSaveable",
                            testSevenSunsWarningCommittedChoiceSurvivesCancellationAndRemainsSaveable);
    nativeTestProfile().run("testSevenSunsWarningRefusesWrongSourceAndMapAwayBackBeforeCommit",
                            testSevenSunsWarningRefusesWrongSourceAndMapAwayBackBeforeCommit);
    nativeTestProfile().run("testSevenSunsWarningRejectsWrongRevisionAndSourceConditionalEdge",
                            testSevenSunsWarningRejectsWrongRevisionAndSourceConditionalEdge);
    nativeTestProfile().run("testSevenSunsWarningReplayRequiresExactRetainedOwnerAndCreatesNothing",
                            testSevenSunsWarningReplayRequiresExactRetainedOwnerAndCreatesNothing);
    nativeTestProfile().run("testSevenSunsWarningClassifiesPendingAndOrphanStateBeforeMissingPlayer",
                            testSevenSunsWarningClassifiesPendingAndOrphanStateBeforeMissingPlayer);
    nativeTestProfile().run("testSevenSunsWarningPostRemovalFailureQuarantinesAndPreservesPrimaryError",
                            testSevenSunsWarningPostRemovalFailureQuarantinesAndPreservesPrimaryError);
    nativeTestProfile().run("testSevenSunsWarningJournalFactoryFailureCannotAcknowledgeEscape",
                            testSevenSunsWarningJournalFactoryFailureCannotAcknowledgeEscape);
    nativeTestProfile().run("testSevenSunsWarningRetainedActorEffectAliasesRoundTrip",
                            testSevenSunsWarningRetainedActorEffectAliasesRoundTrip);
    nativeTestProfile().run("testSevenSunsWarningSessionDoesNotKeepClosedGameAlive",
                            testSevenSunsWarningSessionDoesNotKeepClosedGameAlive);
    nativeTestProfile().run("testSevenSunsWarningUsesSharedSourceGlobalsWithoutClampingOrDroppingScopes",
                            testSevenSunsWarningUsesSharedSourceGlobalsWithoutClampingOrDroppingScopes);
    nativeTestProfile().run("testSevenSunsMerchantRejectsUnsignedDumpAliasingBeforeSourceAuthority",
                            testSevenSunsMerchantRejectsUnsignedDumpAliasingBeforeSourceAuthority);
    nativeTestProfile().run("testSevenSunsStockExhaustive8000FiniteOutcomesAndInputBounds",
                            testSevenSunsStockExhaustive8000FiniteOutcomesAndInputBounds);
    nativeTestProfile().run("testSevenSunsStockPreparedFourLineagesUseRealWeaponAndConcretePossessions",
                            testSevenSunsStockPreparedFourLineagesUseRealWeaponAndConcretePossessions);
    nativeTestProfile().run("testSevenSunsStockPreparedRejectsControllerActionAndInitialMetadataChanges",
                            testSevenSunsStockPreparedRejectsControllerActionAndInitialMetadataChanges);
    nativeTestProfile().run("testSevenSunsStockSettledValidationAllowsActualMutableHealthInventoryAndEquipment",
                            testSevenSunsStockSettledValidationAllowsActualMutableHealthInventoryAndEquipment);
    nativeTestProfile().run("testSevenSunsStockMatchingActorAndClockForgeryCannotPassFiniteReplay",
                            testSevenSunsStockMatchingActorAndClockForgeryCannotPassFiniteReplay);
    nativeTestProfile().run("testSevenSunsStockFailedUnpublishedSelfEffectExpiresWithMapWhileGameLives",
                            testSevenSunsStockFailedUnpublishedSelfEffectExpiresWithMapWhileGameLives);
    nativeTestProfile().run("testSevenSunsStockStagedLifetimeRespectsRealForeignMapAdoption",
                            testSevenSunsStockStagedLifetimeRespectsRealForeignMapAdoption);
    nativeTestProfile().run("testSevenSunsStockNaturalReplacementActualDefeatAwards420ExactlyOnce",
                            testSevenSunsStockNaturalReplacementActualDefeatAwards420ExactlyOnce);
    nativeTestProfile().run("testSevenSunsStockForgedDedicatedDefeatCannotFallBackToGenericXp",
                            testSevenSunsStockForgedDedicatedDefeatCannotFallBackToGenericXp);
    nativeTestProfile().run("testSevenSunsMerchantAllThirteenPathsCoverTwentyFourNativeEdges",
                            testSevenSunsMerchantAllThirteenPathsCoverTwentyFourNativeEdges);
    nativeTestProfile().run("testSevenSunsMerchantInitiationCancelReopenAndLegacyRefusalAreOwned",
                            testSevenSunsMerchantInitiationCancelReopenAndLegacyRefusalAreOwned);
    nativeTestProfile().run("testSevenSunsMerchantCoordinatorReplacesOnlyTheActiveSourceFloorWithoutCredit",
                            testSevenSunsMerchantCoordinatorReplacesOnlyTheActiveSourceFloorWithoutCredit);
    nativeTestProfile().run("testSevenSunsMerchantSharedGlobalsKeepSourceOrderCaseAndOtherScopes",
                            testSevenSunsMerchantSharedGlobalsKeepSourceOrderCaseAndOtherScopes);
    nativeTestProfile().run("testSevenSunsMerchantRejectsStaleEpochRegionActorPlayerAndRevision",
                            testSevenSunsMerchantRejectsStaleEpochRegionActorPlayerAndRevision);
    nativeTestProfile().run("testSevenSunsMerchantFactoryReentryOrOwnerMutationCannotAcknowledgeReplacement",
                            testSevenSunsMerchantFactoryReentryOrOwnerMutationCannotAcknowledgeReplacement);
    nativeTestProfile().run("testSevenSunsMerchantAdmissionAndLegacyEligibilityRetryWithoutMutation",
                            testSevenSunsMerchantAdmissionAndLegacyEligibilityRetryWithoutMutation);
    nativeTestProfile().run("testSevenSunsMerchantFailureAfterDetachQuarantinesBothRetainedOwners",
                            testSevenSunsMerchantFailureAfterDetachQuarantinesBothRetainedOwners);
    nativeTestProfile().run("testSevenSunsMerchantRepeatedSettlementNeverReseedsChangedOrDefeatedStock",
                            testSevenSunsMerchantRepeatedSettlementNeverReseedsChangedOrDefeatedStock);
    nativeTestProfile().run("testSevenSunsMerchantMissingAttackWitnessNeverUsesDamageAsRevealAuthority",
                            testSevenSunsMerchantMissingAttackWitnessNeverUsesDamageAsRevealAuthority);
    nativeTestProfile().run("testSevenSunsMerchantIdleFlowDoesNotRetainGameOwner",
                            testSevenSunsMerchantIdleFlowDoesNotRetainGameOwner);
    nativeTestProfile().run("testSevenSunsMerchantCombatParticipantClaimRetriesBeforeQuietRemoval",
                            testSevenSunsMerchantCombatParticipantClaimRetriesBeforeQuietRemoval);
    nativeTestProfile().run("testSevenSunsMerchantNativeUiFlowOwnsCursorClosesAndRejectsOversizedEdges",
                            testSevenSunsMerchantNativeUiFlowOwnsCursorClosesAndRejectsOversizedEdges);
    nativeTestProfile().run("testSevenSunsMerchantRetiredOldEffectCycleEndsWithMapWhileGameLives",
                            testSevenSunsMerchantRetiredOldEffectCycleEndsWithMapWhileGameLives);
    nativeTestProfile().run("testSevenSunsMerchantWholeMapCodecPreservesOldNewAliasesAndOnceOwnedReceipt",
                            testSevenSunsMerchantWholeMapCodecPreservesOldNewAliasesAndOnceOwnedReceipt);
    nativeTestProfile().run("testSevenSunsMerchantRevisionLimitRefusesWithoutUnreadableOwnOutput",
                            testSevenSunsMerchantRevisionLimitRefusesWithoutUnreadableOwnOutput);
    return finish_tests();
}
