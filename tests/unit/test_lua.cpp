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

#include "core/CGame.h"
#include "core/CLoader.h"
#include "core/CLuaOverrides.h"
#include "handler/CEventHandler.h"
#include "handler/CLuaHandler.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CObject.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

// A bare CGame skips CGameLoader::initObjectHandler, so tests whose probe configs use
// {"class": "CGameObject"} install the base factory themselves.
void register_base_game_object_factory(const std::shared_ptr<CGame> &game) {
    game->getObjectHandler()->registerType("CGameObject", []() { return std::make_shared<CGameObject>(); });
}

constexpr const char *PROBE_TILE_PLUGIN = R"lua(
function load(context)
    context.registerType("LuaProbeTile", {
        base = "CTile",
        onStep = function(self, creature)
            creature:setNumericProperty("luaTouched", 1)
            local steps = self:hasProperty("steps") and self:getNumericProperty("steps") or 0
            self:setNumericProperty("steps", steps + 1)
            self.probe = "stepped"
        end,
    })
end
)lua";

void test_lua_plugin_registers_constructible_type() {
    auto game = std::make_shared<CGame>();
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_tile.lua", PROBE_TILE_PLUGIN),
                "a valid Lua plugin must load");

    auto tile = game->createObject<CGameObject>("LuaProbeTile");
    expect_true(tile != nullptr, "a Lua-registered type name must be constructible");
    expect_true(tile != nullptr && tile->getType() == "LuaProbeTile",
                "the constructed object reports its registered type");
    expect_true(std::dynamic_pointer_cast<CTile>(tile) != nullptr,
                "a Lua type with base CTile must construct a real CTile subclass");
}

void test_lua_hook_dispatch_and_property_bridge() {
    auto game = std::make_shared<CGame>();
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_tile.lua", PROBE_TILE_PLUGIN),
                "a valid Lua plugin must load");

    // The typed createObject<CTile> overload is the exact path CMap::replaceTile takes.
    auto tile = game->createObject<CTile>("LuaProbeTile");
    expect_true(tile != nullptr, "the probe tile must construct through the typed createObject path");
    if (!tile) {
        return;
    }
    auto creature = std::make_shared<CCreature>();

    tile->onStep(creature);
    expect_true(creature->getNumericProperty("luaTouched") == 1,
                "the Lua onStep hook must run and touch the creature through the curated API");
    expect_true(tile->getNumericProperty("steps") == 1, "hook state written via setNumericProperty persists on self");
    expect_true(tile->getStringProperty("probe") == "stepped",
                "property writes through the __newindex bridge land in dynamic properties");

    tile->onStep(creature);
    expect_true(tile->getNumericProperty("steps") == 2, "each dispatch reads the persisted counter back");
}

void test_lua_config_json_and_reflection_construction() {
    auto game = std::make_shared<CGame>();
    const std::string plugin = std::string(PROBE_TILE_PLUGIN) + R"lua(
local function unused() end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_tile.lua", plugin),
                "the probe plugin must load");

    const char *configPlugin = R"lua(
function load(context)
    context.registerConfigJson("luaProbeInstance",
        '{"class": "LuaProbeTile", "properties": {"power": 3}}')
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_config.lua", configPlugin),
                "the config plugin must load");

    auto probe = game->createObject<CGameObject>("luaProbeInstance");
    expect_true(probe != nullptr, "a Lua-registered config referencing a Lua-registered class constructs");
    expect_true(probe != nullptr && probe->getNumericProperty("power") == 3,
                "reflection-driven property application works for Lua-backed types");
}

void test_lua_factory_objects_are_released() {
    auto game = std::make_shared<CGame>();
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_tile.lua", PROBE_TILE_PLUGIN),
                "the lifetime-probe plugin must load");
    const auto originalEntries = CLuaOverrides::instances().size();
    std::weak_ptr<CGameObject> observer;
    {
        auto tile = game->getObjectHandler()->getType("LuaProbeTile");
        expect_true(tile != nullptr, "a temporary Lua factory object must construct");
        observer = tile;
    }
    expect_true(observer.expired(), "the override registry must not keep a discarded factory object alive");
    expect_true(CLuaOverrides::instances().size() == originalEntries,
                "destroying a Lua factory object must remove its override entry");

    auto tile = game->createObject<CTile>("LuaProbeTile");
    observer = tile;
    if (tile) {
        tile->onStep(std::make_shared<CCreature>());
    }
    game->getLuaHandler()->releaseState();
    tile.reset();
    expect_true(observer.expired(), "a dispatched Lua object must be released after the state and caller release it");
    expect_true(CLuaOverrides::instances().size() == originalEntries,
                "Lua state shutdown must not leave entries for discarded objects");
}

void test_lua_sandbox_blocks_dangerous_globals() {
    auto game = std::make_shared<CGame>();
    register_base_game_object_factory(game);
    // The blocked-global scan runs at chunk top level, before the plugin defines its own
    // `load` entry point (which would otherwise shadow the stdlib name being probed).
    const char *probe = R"lua(
local leaked = {}
local blocked = {"os", "io", "package", "require", "dofile", "loadfile", "load", "loadstring",
                 "debug", "coroutine", "collectgarbage", "getmetatable", "setmetatable",
                 "rawget", "rawset", "rawequal", "rawlen", "_G"}
for _, name in ipairs(blocked) do
    if _ENV[name] ~= nil then
        leaked[#leaked + 1] = name
    end
end
if string.dump ~= nil then
    leaked[#leaked + 1] = "string.dump"
end
if ("x").dump ~= nil then
    leaked[#leaked + 1] = "method.dump"
end
if math.randomseed ~= nil then
    leaked[#leaked + 1] = "math.randomseed"
end

function load(context)
    context.registerConfigJson("luaSandboxProbe",
        '{"class": "CGameObject", "properties": {"leaked": "' .. table.concat(leaked, ",") .. '"}}')
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_sandbox.lua", probe),
                "the sandbox probe plugin must load");
    auto report = game->createObject<CGameObject>("luaSandboxProbe");
    expect_true(report != nullptr, "the sandbox probe must report through registerConfigJson");
    if (!report) {
        return;
    }
    expect_true(report->getStringProperty("leaked").empty(),
                ("the sandbox must not leak blocked globals, got: " + report->getStringProperty("leaked")).c_str());
}

void test_lua_rejects_bytecode_chunks() {
    auto game = std::make_shared<CGame>();
    const std::string bytecode = std::string("\x1b") + "Lua precompiled garbage";
    expect_true(!game->getLuaHandler()->loadPlugin(game, "plugins/bytecode.lua", bytecode),
                "precompiled Lua bytecode must be rejected by the text-only chunk mode");
}

void test_lua_load_contract_and_syntax_errors() {
    auto game = std::make_shared<CGame>();
    expect_true(!game->getLuaHandler()->loadPlugin(game, "plugins/no_load.lua", "local x = 1"),
                "a plugin without a load function must be rejected");
    expect_true(!game->getLuaHandler()->loadPlugin(game, "plugins/broken.lua", "function load(context"),
                "a plugin with a syntax error must be rejected");
    expect_true(
        !game->getLuaHandler()->loadPlugin(game, "plugins/raising.lua", "function load(context) error('boom') end"),
        "a plugin whose load errors must be rejected");
}

void test_lua_error_containment_and_bool_hooks() {
    auto game = std::make_shared<CGame>();
    const char *plugin = R"lua(
function load(context)
    context.registerType("LuaRaisingTile", {
        base = "CTile",
        onStep = function(self, creature)
            error("boom")
        end,
    })
    context.registerType("LuaProbeScroll", {
        base = "CScroll",
        isDisposable = function(self)
            return true
        end,
    })
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_errors.lua", plugin),
                "the error-probe plugin must load");

    auto tile = std::dynamic_pointer_cast<CTile>(game->createObject<CGameObject>("LuaRaisingTile"));
    auto creature = std::make_shared<CCreature>();
    expect_true(tile != nullptr, "the raising tile must construct");
    if (tile) {
        tile->onStep(creature); // must log and continue, never crash or abort the caller
        expect_true(!creature->hasProperty("luaTouched"), "a hook that errors must not half-apply effects");
    }

    auto scroll = std::dynamic_pointer_cast<CScroll>(game->createObject<CGameObject>("LuaProbeScroll"));
    expect_true(scroll != nullptr, "the probe scroll must construct");
    expect_true(scroll != nullptr && scroll->isDisposable(), "bool-returning hooks must round-trip a Lua true");
}

void test_lua_release_state_makes_dispatch_a_safe_noop() {
    auto game = std::make_shared<CGame>();
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_tile.lua", PROBE_TILE_PLUGIN),
                "the probe plugin must load");
    auto tile = std::dynamic_pointer_cast<CTile>(game->createObject<CGameObject>("LuaProbeTile"));
    expect_true(tile != nullptr, "the probe tile must construct");
    if (!tile) {
        return;
    }

    game->getLuaHandler()->releaseState();
    auto creature = std::make_shared<CCreature>();
    tile->onStep(creature); // expired handler => fall back to the base implementation, no crash
    expect_true(!creature->hasProperty("luaTouched"),
                "after releaseState a retained Lua object must dispatch as no-override");
}

void test_lua_register_type_validation() {
    auto game = std::make_shared<CGame>();
    register_base_game_object_factory(game);
    const char *plugin = R"lua(
function load(context)
    local unknownBase = context.registerType("LuaBadBase", {base = "CQuest"})
    local missingSpec = context.registerType("LuaNoSpec")
    context.registerConfigJson("luaRegisterTypeProbe",
        '{"class": "CGameObject", "properties": {"unknownBase": ' .. tostring(unknownBase == true)
        .. ', "missingSpec": ' .. tostring(missingSpec == true) .. '}}')
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/probe_register.lua", plugin),
                "the registerType-probe plugin must load");
    auto report = game->createObject<CGameObject>("luaRegisterTypeProbe");
    expect_true(report != nullptr, "the registerType probe must report");
    expect_true(report != nullptr && !report->getBoolProperty("unknownBase"), "an unsupported base must be rejected");
    expect_true(report != nullptr && !report->getBoolProperty("missingSpec"), "a missing spec table must be rejected");
    expect_true(game->getObjectHandler()->getType("LuaBadBase") == nullptr,
                "a rejected registration must not install a factory");
}

void test_lua_trusted_path_gate() {
    expect_true(CPluginLoader::isTrustedLuaPluginPath("plugins/tile.lua"), "plugins/*.lua is trusted");
    expect_true(CPluginLoader::isTrustedLuaPluginPath("plugins/nested/extra.lua"),
                "nested plugin directories are trusted");
    expect_true(!CPluginLoader::isTrustedLuaPluginPath("maps/test/script.lua"),
                "map script.lua is not part of the v1 Lua surface");
    expect_true(!CPluginLoader::isTrustedLuaPluginPath("../plugins/tile.lua"), "parent traversal is rejected");
    expect_true(!CPluginLoader::isTrustedLuaPluginPath("plugins/tile.py"), "non-.lua suffixes are rejected");
    expect_true(!CPluginLoader::isTrustedLuaPluginPath("C:/plugins/tile.lua"), "absolute paths are rejected");
    expect_true(!CPluginLoader::isTrustedLuaPluginPath(""), "empty paths are rejected");
}

void testLuaDispatchesEverySupportedHookAndReleasesObjects() {
    auto game = std::make_shared<CGame>();
    const char *plugin = R"lua(
function load(context)
    local function mark(self, event)
        self.calls = (self.calls or 0) + 1
        self.sawNil = event == nil
    end
    context.registerType("LuaEveryTile", {base = "CTile", onStep = mark})
    context.registerType("LuaEveryEffect", {base = "CEffect", onEffect = mark})
    context.registerType("LuaEveryPotion", {base = "CPotion", onUse = mark})
    context.registerType("LuaEveryScroll", {
        base = "CScroll", onUse = mark,
        isDisposable = function(self) return self.consume == true end,
    })
    context.registerType("LuaEveryInteraction", {
        base = "CInteraction",
        performAction = function(self, first, second)
            first.target = second
            second.actor = first
            mark(self, first)
        end,
        configureEffect = function(self, effect)
            effect.configured = true
            return self.allow == true
        end,
    })
    context.registerType("LuaEveryTrigger", {
        base = "CTrigger",
        trigger = function(self, object, event)
            object.triggerCause = event:getCause()
            mark(self, event)
        end,
    })
    for _, base in ipairs({"CBuilding", "CEvent"}) do
        context.registerType("LuaEvery" .. base, {
            base = base, onEnter = mark, onLeave = mark, onTurn = mark,
            onCreate = mark, onDestroy = mark,
        })
    end
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/every_hook.lua", plugin),
                "all eight supported Lua bases must register");
    const auto initial_entries = CLuaOverrides::instances().size();
    std::vector<std::weak_ptr<CGameObject>> observers;
    {
        auto tile = game->createObject<CTile>("LuaEveryTile");
        auto effect = game->createObject<CEffect>("LuaEveryEffect");
        auto potion = game->createObject<CPotion>("LuaEveryPotion");
        auto scroll = game->createObject<CScroll>("LuaEveryScroll");
        auto interaction = game->createObject<CInteraction>("LuaEveryInteraction");
        auto trigger = game->createObject<CTrigger>("LuaEveryTrigger");
        auto building = game->createObject<CBuilding>("LuaEveryCBuilding");
        auto event_object = game->createObject<CEvent>("LuaEveryCEvent");
        expect_true(tile && effect && potion && scroll && interaction && trigger && building && event_object,
                    "each supported Lua base must construct with its native type");
        if (!(tile && effect && potion && scroll && interaction && trigger && building && event_object)) {
            return;
        }
        observers = {tile, effect, potion, scroll, interaction, trigger, building, event_object};
        auto first = std::make_shared<CCreature>();
        auto second = std::make_shared<CCreature>();
        auto event = std::make_shared<CGameEventCaused>(CGameEvent::CType::onUse, first);
        tile->onStep(nullptr);
        effect->onEffect();
        potion->onUse(event);
        scroll->onUse(event);
        expect_true(tile->getBoolProperty("sawNil") && effect->getBoolProperty("sawNil"),
                    "missing native arguments must reach Lua as nil");
        expect_true(potion->getNumericProperty("calls") == 1 && scroll->getNumericProperty("calls") == 1,
                    "potion and scroll hooks must receive native use events");
        expect_true(!scroll->isDisposable(), "a Lua false must override the native bool result");
        scroll->setBoolProperty("consume", true);
        expect_true(scroll->isDisposable(), "a Lua bool hook must read updated object state");
        interaction->performAction(first, second);
        expect_true(first->getObjectProperty<CGameObject>("target") == second &&
                        second->getObjectProperty<CGameObject>("actor") == first,
                    "interaction dispatch must preserve both arguments and their order");
        expect_true(!interaction->configureEffect(effect) && effect->getBoolProperty("configured"),
                    "configureEffect must preserve side effects when returning false");
        interaction->setBoolProperty("allow", true);
        expect_true(interaction->configureEffect(effect), "configureEffect must also return Lua true");
        trigger->trigger(effect, event);
        expect_true(effect->getObjectProperty<CGameObject>("triggerCause") == first,
                    "trigger events must retain their native cause identity");
        const auto dispatchLifecycle = [&](const auto &object) {
            object->onEnter(event);
            object->onLeave(event);
            object->onTurn(event);
            object->onCreate(event);
            object->onDestroy(event);
            expect_true(object->getNumericProperty("calls") == 5,
                        "building and event wrappers must dispatch all five lifecycle hooks");
        };
        dispatchLifecycle(building);
        dispatchLifecycle(event_object);
        first->setObjectProperty("target", std::shared_ptr<CGameObject>());
        second->setObjectProperty("actor", std::shared_ptr<CGameObject>());
        game->getLuaHandler()->releaseState();
    }
    for (const auto &observer : observers) {
        expect_true(observer.expired(), "every supported wrapper must release its last native owner");
    }
    expect_true(CLuaOverrides::instances().size() == initial_entries,
                "all eight wrapper destructors must remove their override entries");
}

void testLuaCuratedObjectApiPreservesValuesAndIdentity() {
    auto game = std::make_shared<CGame>();
    vstd::register_any_type<std::shared_ptr<CCreature>, std::shared_ptr<CGameObject>>();
    register_base_game_object_factory(game);
    auto creature = std::make_shared<CCreature>();
    creature->getBaseStats()->setStamina(2);
    creature->setHp(1);
    game->setProperty<std::shared_ptr<CGameObject>>("probeCreature", creature);
    game->setProperty<std::shared_ptr<CGameObject>>("probeEvent",
                                                    std::make_shared<CGameEventCaused>("probe", creature));
    const char *plugin = R"lua(
function load(context)
    local object = context.game:createObject("CGameObject")
    object:setBoolProperty("enabled", true)
    object:setNumericProperty("amount", 17)
    object:setStringProperty("message", "Lua bridge")
    assert(object:getBoolProperty("enabled") == true and object.enabled == true)
    assert(object:getNumericProperty("amount") == 17 and object.amount == 17)
    assert(object:getStringProperty("message") == "Lua bridge" and object.message == "Lua bridge")
    object.enabled = false
    object.amount = 23
    object.message = "updated"
    object.peer = context.game.probeCreature
    assert(object.peer == context.game.probeEvent:getCause())
    assert(object.peer ~= object)
    assert(object.unknown == nil and object[false] == nil)
    assert(object:getType() == "CGameObject" and type(object:getName()) == "string")
    assert(object:getCause() == nil)
    local creature = object.peer
    creature:heal(2)
    object.afterHeal = creature.hp
    creature:hurt(1)
    object.afterHurt = creature.hp
    creature:healProc(100.0)
    object.afterPercent = creature.hp
    creature:setStringProperty("hp", "invalid")
    assert(creature.hp == object.afterPercent)
    object.randomValue = randint(7, 7)
    context.log("bridge", 17, true, false, nil, {})
    print("bridge log complete")
    context.game.apiReport = object
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/object_api.lua", plugin),
                "the curated object API must preserve typed values and native object identity");
    auto report = game->getObjectProperty<CGameObject>("apiReport");
    expect_true(report != nullptr, "the Lua-created report must remain accessible to native callers");
    if (report) {
        expect_true(!report->getBoolProperty("enabled") && report->getNumericProperty("amount") == 23 &&
                        report->getStringProperty("message") == "updated",
                    "dynamic writes must update the same native properties as explicit setters");
        expect_true(report->getObjectProperty<CGameObject>("peer") == creature,
                    "Lua object-property writes must preserve the original shared object");
        expect_true(report->getNumericProperty("afterHeal") == 3 && report->getNumericProperty("afterHurt") == 2 &&
                        report->getNumericProperty("afterPercent") == creature->getHpMax(),
                    "heal, hurt, and percentage healing must affect the native creature's health");
        expect_true(report->getNumericProperty("randomValue") == 7, "equal randint bounds must be deterministic");
    }
    game->getLuaHandler()->releaseState();
}

void testLuaInvalidApiCallsDoNotMutateObjectsOrPoisonTheState() {
    auto game = std::make_shared<CGame>();
    register_base_game_object_factory(game);
    game->getObjectHandler()->registerType(
        "LuaThrowingFactory", []() -> std::shared_ptr<CGameObject> { throw std::runtime_error("factory failure"); });
    const char *plugin = R"lua(
function load(context)
    local object = context.game:createObject("CGameObject")
    object.flag = true
    object.amount = 11
    object.message = "kept"
    object:setBoolProperty("flag", "invalid")
    object:setNumericProperty("amount", 1.5)
    object:setStringProperty("message", {})
    object:setBoolProperty(nil, true)
    object:setNumericProperty(nil, 2)
    object:setStringProperty(nil, "bad")
    object:setStringProperty("name", "unchanged")
    object:setBoolProperty("name", true)
    object:setNumericProperty("name", 42)
    object.name = true
    assert(object:getName() == "unchanged")
    object.getBoolProperty({}, "flag")
    object.setBoolProperty({}, "flag", false)
    object.getNumericProperty({}, "amount")
    object.setNumericProperty({}, "amount", 2)
    object.getStringProperty({}, "message")
    object.setStringProperty({}, "message", "bad")
    assert(object:getBoolProperty(nil) == nil)
    assert(object:getNumericProperty(nil) == nil)
    assert(object:getStringProperty(nil) == nil)
    assert(object:getBoolProperty("amount") == nil)
    assert(object:getNumericProperty("message") == nil)
    assert(object:getStringProperty("flag") == nil)
    assert(object.hasProperty({}, "flag") == false and object:hasProperty(nil) == false)
    assert(object.getType({}) == nil and object.getName({}) == nil)
    object:heal(3)
    object:hurt(2)
    object:healProc(10)
    object:getCause()
    assert(object:createObject("CGameObject") == nil)
    assert(context.game:createObject(nil) == nil)
    assert(context.game:createObject("LuaThrowingFactory") == nil)
    object.unsupportedTable = {}
    object.unsupportedFraction = 1.5
    object.unsupportedNil = nil
    assert(not object:hasProperty("unsupportedTable"))
    assert(not object:hasProperty("unsupportedFraction"))
    assert(not object:hasProperty("unsupportedNil"))
    assert(randint("bad", 3) == 0)
    assert(object.flag == true and object.amount == 11 and object.message == "kept")
    context.game.invalidApiSurvived = true
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/invalid_api.lua", plugin),
                "invalid Lua API arguments and native exceptions must be contained without aborting load");
    expect_true(game->getBoolProperty("invalidApiSurvived"),
                "the script must reach its final assertion after invalid calls and rejected writes");
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/recovery.lua", PROBE_TILE_PLUGIN),
                "a plugin loaded after contained API errors must still register usable hooks");
    auto tile = game->createObject<CTile>("LuaProbeTile");
    auto creature = std::make_shared<CCreature>();
    if (tile) {
        tile->onStep(creature);
    }
    expect_true(creature->getNumericProperty("luaTouched") == 1,
                "contained errors must not leave the Lua stack unusable for later dispatch");
    game->getLuaHandler()->releaseState();
}

void testLuaMissingAndFailedHooksUseDocumentedFallbacks() {
    auto game = std::make_shared<CGame>();
    const char *plugin = R"lua(
function load(context)
    for _, base in ipairs({"CTile", "CEffect", "CPotion", "CScroll", "CInteraction", "CTrigger",
                           "CBuilding", "CEvent"}) do
        context.registerType("LuaEmpty" .. base, {base = base})
    end
    context.registerType("LuaFailedBool", {
        base = "CInteraction", configureEffect = function(self, effect) error("bool failure") end,
    })
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/fallback_hooks.lua", plugin),
                "types may omit optional Lua hooks");
    auto tile = game->createObject<CTile>("LuaEmptyCTile");
    auto effect = game->createObject<CEffect>("LuaEmptyCEffect");
    auto potion = game->createObject<CPotion>("LuaEmptyCPotion");
    auto scroll = game->createObject<CScroll>("LuaEmptyCScroll");
    auto interaction = game->createObject<CInteraction>("LuaEmptyCInteraction");
    auto trigger = game->createObject<CTrigger>("LuaEmptyCTrigger");
    auto building = game->createObject<CBuilding>("LuaEmptyCBuilding");
    auto event_object = game->createObject<CEvent>("LuaEmptyCEvent");
    auto failed = game->createObject<CInteraction>("LuaFailedBool");
    expect_true(tile && effect && potion && scroll && interaction && trigger && building && event_object && failed,
                "empty and raising hook tables must still construct native objects");
    if (!(tile && effect && potion && scroll && interaction && trigger && building && event_object && failed)) {
        return;
    }
    auto creature = std::make_shared<CCreature>();
    auto event = std::make_shared<CGameEvent>();
    tile->onStep(creature);
    effect->onEffect();
    potion->onUse(event);
    interaction->performAction(creature, creature);
    trigger->trigger(creature, event);
    const auto dispatchLifecycle = [&](const auto &object) {
        object->onEnter(event);
        object->onLeave(event);
        object->onTurn(event);
        object->onCreate(event);
        object->onDestroy(event);
        expect_true(!object->hasProperty("calls"), "missing lifecycle hooks must retain native no-op behavior");
    };
    dispatchLifecycle(building);
    dispatchLifecycle(event_object);
    expect_true(!scroll->isDisposable(), "missing scroll bool hooks must use the native false default");
    expect_true(interaction->configureEffect(effect),
                "missing interaction bool hooks must use the native true default");
    expect_true(!failed->configureEffect(effect),
                "a contained bool-hook error must return false instead of the default");
    bool result = true;
    expect_true(!CLuaHandler::dispatchBool(creature.get(), "configureEffect", {}, result) && result,
                "objects without override entries must decline bool dispatch without changing the result");
    expect_true(!CLuaHandler::dispatch(creature.get(), "onEffect"),
                "objects without override entries must decline void dispatch");
    game->getLuaHandler()->releaseState();
    expect_true(failed->configureEffect(effect), "state release must restore native bool fallback on retained objects");
}

void testLuaRegistrationErrorsAndSandboxIsolation() {
    auto game = std::make_shared<CGame>();
    register_base_game_object_factory(game);
    expect_true(!game->getLuaHandler()->loadPlugin(nullptr, "plugins/no_game.lua", PROBE_TILE_PLUGIN),
                "a plugin cannot register types without a game");
    expect_true(!game->getLuaHandler()->loadPlugin(game, "plugins/top_error.lua", "error('top-level failure')"),
                "top-level chunk errors must be contained before load is invoked");
    const char *plugin = R"lua(
privateValue = "first plugin"
math.privateValue = "first plugin"
function load(context)
    assert(context.registerType("LuaMissingBase", {}) == false)
    assert(context.registerType(nil, {base = "CTile"}) == false)
    assert(context.registerConfigJson("missingJson") == false)
    assert(context.registerConfigJson(nil, "{}") == false)
    assert(context.registerConfigJson("brokenJson", "{") == false)
    assert(context.registerConfigJson("arrayJson", "[]") == false)
    assert(context.registerConfigJson("", "{}") == false)
    assert(context.registerType("", {base = "CTile"}) == false)
    assert(context.registerType("LuaUnknownHook", {base = "CTile", typoHook = function() end}) == true)
    context.game.registrationErrorsSurvived = true
end
)lua";
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/registration_errors.lua", plugin),
                "invalid registrations must return false while an unknown optional hook only warns");
    expect_true(game->getBoolProperty("registrationErrorsSurvived"),
                "registration errors must not abort the rest of the plugin");
    expect_true(game->getObjectHandler()->getType("LuaMissingBase") == nullptr,
                "a registration without a supported base must not leave a factory behind");
    expect_true(game->getLuaHandler()->loadPlugin(game, "plugins/isolated.lua", R"lua(
assert(privateValue == nil and math.privateValue == nil)
function load(context) context.game.sandboxIsolated = true end
)lua"),
                "each plugin must receive a fresh global environment and library table");
    expect_true(game->getBoolProperty("sandboxIsolated"), "sandbox mutations must stay isolated between plugins");
    game->getLuaHandler()->releaseState();
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_lua_plugin_registers_constructible_type();
    test_lua_hook_dispatch_and_property_bridge();
    test_lua_config_json_and_reflection_construction();
    test_lua_factory_objects_are_released();
    test_lua_sandbox_blocks_dangerous_globals();
    test_lua_rejects_bytecode_chunks();
    test_lua_load_contract_and_syntax_errors();
    test_lua_error_containment_and_bool_hooks();
    test_lua_release_state_makes_dispatch_a_safe_noop();
    test_lua_register_type_validation();
    test_lua_trusted_path_gate();
    testLuaDispatchesEverySupportedHookAndReleasesObjects();
    testLuaCuratedObjectApiPreservesValuesAndIdentity();
    testLuaInvalidApiCallsDoNotMutateObjectsOrPoisonTheState();
    testLuaMissingAndFailedHooksUseDocumentedFallbacks();
    testLuaRegistrationErrorsAndSandboxIsolation();

    return finish_tests();
}
