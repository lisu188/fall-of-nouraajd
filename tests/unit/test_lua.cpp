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
#include "handler/CLuaHandler.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CObject.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <memory>
#include <string>

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

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_lua_plugin_registers_constructible_type();
    test_lua_hook_dispatch_and_property_bridge();
    test_lua_config_json_and_reflection_construction();
    test_lua_sandbox_blocks_dangerous_globals();
    test_lua_rejects_bytecode_chunks();
    test_lua_load_contract_and_syntax_errors();
    test_lua_error_containment_and_bool_hooks();
    test_lua_release_state_makes_dispatch_a_safe_noop();
    test_lua_register_type_validation();
    test_lua_trusted_path_gate();

    return finish_tests();
}
