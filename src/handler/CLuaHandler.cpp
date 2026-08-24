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
#include "handler/CLuaHandler.h"
#include "core/CGame.h"
#include "core/CLuaOverrides.h"
#include "core/CLuaWrapper.h"
#include "handler/CEventHandler.h"
#include "object/CCreature.h"
#include "plugin/CPluginRegistrar.h"

extern "C" {
#include <lauxlib.h>
#include <lua.h>
#include <lualib.h>
}

#include <array>

// Implementation discipline: no lua_CFunction in this file ever raises a Lua error (no
// luaL_error / lua_error / luaL_check*). Lua errors longjmp past C++ destructors, so every
// engine call is wrapped in try/catch and failures log a warning and return nil instead.
// The only longjmp boundaries are the lua_pcall sites, which contain plugin errors.
namespace {

constexpr const char *GAME_OBJECT_METATABLE = "fon.CGameObject";
constexpr const char *LUA_HOST_METATABLE = "fon.LuaHost";

// Both references are weak on purpose. This userdata lives inside the lua_State that the game's
// own CGameContext owns, so a strong CGame here closes an ownership cycle
// (CGame -> CGameContext -> CLuaHandler -> lua_State -> userdata -> CGame) that no destructor can
// break: the state is only closed by the explicit CGameContext::shutdown, so simply dropping the
// last reference to a game would leak its entire object graph (measured at ~2.4 MB per loadGame).
struct LuaHostContext {
    std::weak_ptr<CGame> game;
    std::weak_ptr<CLuaHandler> handler;
};

enum class LuaBaseKind { Tile, Effect, Potion, Scroll, Interaction, Trigger, Building, Event };

struct LuaBaseInfo {
    const char *name;
    LuaBaseKind kind;
    const char *const *hooks; // null-terminated
};

constexpr const char *LUA_TILE_HOOKS[] = {"onStep", nullptr};
constexpr const char *LUA_EFFECT_HOOKS[] = {"onEffect", nullptr};
constexpr const char *LUA_POTION_HOOKS[] = {"onUse", nullptr};
constexpr const char *LUA_SCROLL_HOOKS[] = {"onUse", "isDisposable", nullptr};
constexpr const char *LUA_INTERACTION_HOOKS[] = {"performAction", "configureEffect", nullptr};
constexpr const char *LUA_TRIGGER_HOOKS[] = {"trigger", nullptr};
constexpr const char *LUA_LIFECYCLE_HOOKS[] = {"onEnter", "onLeave", "onTurn", "onCreate", "onDestroy", nullptr};

constexpr LuaBaseInfo LUA_BASES[] = {
    {"CTile", LuaBaseKind::Tile, LUA_TILE_HOOKS},
    {"CEffect", LuaBaseKind::Effect, LUA_EFFECT_HOOKS},
    {"CPotion", LuaBaseKind::Potion, LUA_POTION_HOOKS},
    {"CScroll", LuaBaseKind::Scroll, LUA_SCROLL_HOOKS},
    {"CInteraction", LuaBaseKind::Interaction, LUA_INTERACTION_HOOKS},
    {"CTrigger", LuaBaseKind::Trigger, LUA_TRIGGER_HOOKS},
    {"CBuilding", LuaBaseKind::Building, LUA_LIFECYCLE_HOOKS},
    {"CEvent", LuaBaseKind::Event, LUA_LIFECYCLE_HOOKS},
};

const LuaBaseInfo *find_lua_base(const char *name) {
    if (name == nullptr) {
        return nullptr;
    }
    for (const auto &base : LUA_BASES) {
        if (std::string(base.name) == name) {
            return &base;
        }
    }
    return nullptr;
}

std::shared_ptr<CGameObject> *test_game_object(lua_State *L, int index) {
    return static_cast<std::shared_ptr<CGameObject> *>(luaL_testudata(L, index, GAME_OBJECT_METATABLE));
}

std::shared_ptr<CGameObject> to_game_object(lua_State *L, int index) {
    auto *pointer = test_game_object(L, index);
    return pointer == nullptr ? nullptr : *pointer;
}

void push_game_object(lua_State *L, const std::shared_ptr<CGameObject> &object) {
    if (!object) {
        lua_pushnil(L);
        return;
    }
    void *storage = lua_newuserdatauv(L, sizeof(std::shared_ptr<CGameObject>), 0);
    new (storage) std::shared_ptr<CGameObject>(object);
    luaL_setmetatable(L, GAME_OBJECT_METATABLE);
}

int lua_object_gc(lua_State *L) {
    auto *pointer = test_game_object(L, 1);
    if (pointer != nullptr) {
        pointer->~shared_ptr();
    }
    return 0;
}

int lua_object_eq(lua_State *L) {
    auto first = to_game_object(L, 1);
    auto second = to_game_object(L, 2);
    lua_pushboolean(L, first.get() == second.get());
    return 1;
}

int lua_object_get_bool_property(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    if (!self || name == nullptr) {
        lua_pushnil(L);
        return 1;
    }
    try {
        lua_pushboolean(L, self->getBoolProperty(name));
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        lua_pushnil(L);
    }
    return 1;
}

int lua_object_set_bool_property(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    if (!self || name == nullptr || !lua_isboolean(L, 3)) {
        vstd::logger::warning("Lua plugin called setBoolProperty with invalid arguments");
        return 0;
    }
    try {
        self->setBoolProperty(name, lua_toboolean(L, 3) != 0);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
    }
    return 0;
}

int lua_object_get_numeric_property(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    if (!self || name == nullptr) {
        lua_pushnil(L);
        return 1;
    }
    try {
        lua_pushinteger(L, self->getNumericProperty(name));
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        lua_pushnil(L);
    }
    return 1;
}

int lua_object_set_numeric_property(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    if (!self || name == nullptr || !lua_isinteger(L, 3)) {
        vstd::logger::warning("Lua plugin called setNumericProperty with invalid arguments");
        return 0;
    }
    try {
        self->setNumericProperty(name, static_cast<int>(lua_tointeger(L, 3)));
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
    }
    return 0;
}

int lua_object_get_string_property(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    if (!self || name == nullptr) {
        lua_pushnil(L);
        return 1;
    }
    try {
        lua_pushstring(L, self->getStringProperty(name).c_str());
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        lua_pushnil(L);
    }
    return 1;
}

int lua_object_set_string_property(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    const char *value = lua_tostring(L, 3);
    if (!self || name == nullptr || value == nullptr) {
        vstd::logger::warning("Lua plugin called setStringProperty with invalid arguments");
        return 0;
    }
    try {
        self->setStringProperty(name, value);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
    }
    return 0;
}

int lua_object_has_property(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    bool has = false;
    if (self && name != nullptr) {
        try {
            has = self->hasProperty(name);
        } catch (const std::exception &exception) {
            vstd::logger::warning("Lua plugin engine error:", exception.what());
        }
    }
    lua_pushboolean(L, has);
    return 1;
}

int lua_object_get_type(lua_State *L) {
    auto self = to_game_object(L, 1);
    if (!self) {
        lua_pushnil(L);
        return 1;
    }
    try {
        lua_pushstring(L, self->getType().c_str());
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        lua_pushnil(L);
    }
    return 1;
}

int lua_object_get_name(lua_State *L) {
    auto self = to_game_object(L, 1);
    if (!self) {
        lua_pushnil(L);
        return 1;
    }
    try {
        lua_pushstring(L, self->getName().c_str());
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        lua_pushnil(L);
    }
    return 1;
}

int lua_creature_heal(lua_State *L) {
    auto creature = std::dynamic_pointer_cast<CCreature>(to_game_object(L, 1));
    if (!creature || !lua_isinteger(L, 2)) {
        vstd::logger::warning("Lua plugin called heal on a non-creature or without an integer amount");
        return 0;
    }
    try {
        creature->heal(static_cast<int>(lua_tointeger(L, 2)));
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
    }
    return 0;
}

int lua_creature_hurt(lua_State *L) {
    auto creature = std::dynamic_pointer_cast<CCreature>(to_game_object(L, 1));
    if (!creature || !lua_isinteger(L, 2)) {
        vstd::logger::warning("Lua plugin called hurt on a non-creature or without an integer amount");
        return 0;
    }
    try {
        creature->hurt(static_cast<int>(lua_tointeger(L, 2)));
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
    }
    return 0;
}

int lua_creature_heal_proc(lua_State *L) {
    auto creature = std::dynamic_pointer_cast<CCreature>(to_game_object(L, 1));
    if (!creature || !lua_isnumber(L, 2)) {
        vstd::logger::warning("Lua plugin called healProc on a non-creature or without a number");
        return 0;
    }
    try {
        creature->healProc(static_cast<float>(lua_tonumber(L, 2)));
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
    }
    return 0;
}

int lua_event_get_cause(lua_State *L) {
    auto event = std::dynamic_pointer_cast<CGameEventCaused>(to_game_object(L, 1));
    if (!event) {
        lua_pushnil(L);
        return 1;
    }
    try {
        push_game_object(L, event->getCause());
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        lua_pushnil(L);
    }
    return 1;
}

int lua_game_create_object(lua_State *L) {
    auto game = std::dynamic_pointer_cast<CGame>(to_game_object(L, 1));
    const char *name = lua_tostring(L, 2);
    if (!game || name == nullptr) {
        vstd::logger::warning("Lua plugin called createObject without a game or type name");
        lua_pushnil(L);
        return 1;
    }
    try {
        push_game_object(L, game->createObject<CGameObject>(name));
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        lua_pushnil(L);
    }
    return 1;
}

// __index: curated methods first, then the dynamic-property bridge (bool/numeric/string/object
// attempts, mirroring game_object_getattr in CModule.cpp); unknown names read as nil.
int lua_object_index(lua_State *L) {
    if (lua_type(L, 2) == LUA_TSTRING) {
        lua_pushvalue(L, 2);
        lua_rawget(L, lua_upvalueindex(1));
        if (!lua_isnil(L, -1)) {
            return 1;
        }
        lua_pop(L, 1);
        auto self = to_game_object(L, 1);
        const char *name = lua_tostring(L, 2);
        if (self && name != nullptr) {
            bool has = false;
            try {
                has = self->hasProperty(name);
            } catch (const std::exception &) {
            }
            if (has) {
                try {
                    lua_pushboolean(L, self->getBoolProperty(name));
                    return 1;
                } catch (const std::exception &) {
                }
                try {
                    lua_pushinteger(L, self->getNumericProperty(name));
                    return 1;
                } catch (const std::exception &) {
                }
                try {
                    lua_pushstring(L, self->getStringProperty(name).c_str());
                    return 1;
                } catch (const std::exception &) {
                }
                try {
                    push_game_object(L, self->getObjectProperty<CGameObject>(name));
                    return 1;
                } catch (const std::exception &) {
                }
            }
        }
    }
    lua_pushnil(L);
    return 1;
}

// __newindex: property writes land in vstd dynamic properties (and therefore serialize with
// saves), mirroring game_object_setattr in CModule.cpp.
int lua_object_newindex(lua_State *L) {
    auto self = to_game_object(L, 1);
    const char *name = lua_tostring(L, 2);
    if (!self || name == nullptr) {
        vstd::logger::warning("Lua plugin attempted a property write on a non-object");
        return 0;
    }
    try {
        switch (lua_type(L, 3)) {
        case LUA_TBOOLEAN:
            self->setBoolProperty(name, lua_toboolean(L, 3) != 0);
            return 0;
        case LUA_TNUMBER:
            if (lua_isinteger(L, 3)) {
                self->setNumericProperty(name, static_cast<int>(lua_tointeger(L, 3)));
                return 0;
            }
            break;
        case LUA_TSTRING:
            self->setStringProperty(name, lua_tostring(L, 3));
            return 0;
        case LUA_TUSERDATA:
            if (auto value = to_game_object(L, 3)) {
                self->setObjectProperty(name, value);
                return 0;
            }
            break;
        default:
            break;
        }
    } catch (const std::exception &exception) {
        vstd::logger::warning("Lua plugin engine error:", exception.what());
        return 0;
    }
    vstd::logger::warning("Unsupported Lua property value type for:", name);
    return 0;
}

int lua_plugin_log(lua_State *L) {
    std::string message;
    const int top = lua_gettop(L);
    for (int index = 1; index <= top; ++index) {
        if (index > 1) {
            message += " ";
        }
        const int type = lua_type(L, index);
        if (type == LUA_TSTRING || type == LUA_TNUMBER) {
            message += lua_tostring(L, index);
        } else if (type == LUA_TBOOLEAN) {
            message += lua_toboolean(L, index) != 0 ? "true" : "false";
        } else {
            message += lua_typename(L, type);
        }
    }
    vstd::logger::info("Lua plugin:", message);
    return 0;
}

int lua_randint(lua_State *L) {
    if (!lua_isinteger(L, 1) || !lua_isinteger(L, 2)) {
        vstd::logger::warning("Lua plugin called randint without integer bounds");
        lua_pushinteger(L, 0);
        return 1;
    }
    lua_pushinteger(L, vstd::rand(static_cast<int>(lua_tointeger(L, 1)), static_cast<int>(lua_tointeger(L, 2))));
    return 1;
}

int lua_host_gc(lua_State *L) {
    auto *host = static_cast<LuaHostContext *>(luaL_testudata(L, 1, LUA_HOST_METATABLE));
    if (host != nullptr) {
        host->~LuaHostContext();
    }
    return 0;
}

LuaHostContext *test_lua_host(lua_State *L, int index) {
    return static_cast<LuaHostContext *>(luaL_testudata(L, index, LUA_HOST_METATABLE));
}

std::function<std::shared_ptr<CGameObject>()> make_lua_factory(std::weak_ptr<CLuaHandler> handler, LuaBaseKind kind,
                                                               int hooksRef) {
    return [handler = std::move(handler), kind, hooksRef]() -> std::shared_ptr<CGameObject> {
        std::shared_ptr<CGameObject> object;
        switch (kind) {
        case LuaBaseKind::Tile:
            object = std::make_shared<CLuaWrapper<CTile>>();
            break;
        case LuaBaseKind::Effect:
            object = std::make_shared<CLuaWrapper<CEffect>>();
            break;
        case LuaBaseKind::Potion:
            object = std::make_shared<CLuaWrapper<CPotion>>();
            break;
        case LuaBaseKind::Scroll:
            object = std::make_shared<CLuaWrapper<CScroll>>();
            break;
        case LuaBaseKind::Interaction:
            object = std::make_shared<CLuaWrapper<CInteraction>>();
            break;
        case LuaBaseKind::Trigger:
            object = std::make_shared<CLuaWrapper<CTrigger>>();
            break;
        case LuaBaseKind::Building:
            object = std::make_shared<CLuaWrapper<CBuilding>>();
            break;
        case LuaBaseKind::Event:
            object = std::make_shared<CLuaWrapper<CEvent>>();
            break;
        }
        CLuaOverrides::retain(object, handler, hooksRef);
        return object;
    };
}

// context.registerType(name, {base = "CTile", onStep = function(self, creature) ... end})
int lua_context_register_type(lua_State *L) {
    auto *host = test_lua_host(L, lua_upvalueindex(1));
    const char *name = lua_tostring(L, 1);
    auto game = host == nullptr ? nullptr : host->game.lock();
    if (!game || name == nullptr || !lua_istable(L, 2)) {
        vstd::logger::warning("Lua plugin called registerType without a name and spec table");
        lua_pushboolean(L, false);
        return 1;
    }

    lua_getfield(L, 2, "base");
    const auto *base = find_lua_base(lua_tostring(L, -1));
    lua_pop(L, 1);
    if (base == nullptr) {
        vstd::logger::warning("Lua plugin registerType has an unknown or missing base:", name);
        lua_pushboolean(L, false);
        return 1;
    }

    lua_pushnil(L);
    while (lua_next(L, 2) != 0) {
        if (lua_type(L, -2) == LUA_TSTRING) {
            const std::string key = lua_tostring(L, -2);
            bool known = key == "base";
            for (const char *const *hook = base->hooks; *hook != nullptr; ++hook) {
                known = known || key == *hook;
            }
            if (!known) {
                vstd::logger::warning("Lua plugin type", name, "declares an unknown hook:", key);
            }
        }
        lua_pop(L, 1);
    }

    lua_pushvalue(L, 2);
    const int hooksRef = luaL_ref(L, LUA_REGISTRYINDEX);
    CPluginRegistrar registrar(game);
    const bool registered = registrar.registerFactory(name, make_lua_factory(host->handler, base->kind, hooksRef));
    lua_pushboolean(L, registered);
    return 1;
}

int lua_context_register_config_json(lua_State *L) {
    auto *host = test_lua_host(L, lua_upvalueindex(1));
    const char *id = lua_tostring(L, 1);
    const char *jsonText = lua_tostring(L, 2);
    auto game = host == nullptr ? nullptr : host->game.lock();
    if (!game || id == nullptr || jsonText == nullptr) {
        vstd::logger::warning("Lua plugin called registerConfigJson without an id and json text");
        lua_pushboolean(L, false);
        return 1;
    }
    CPluginRegistrar registrar(game);
    lua_pushboolean(L, registrar.registerConfigJson(id, jsonText));
    return 1;
}

void create_game_object_metatable(lua_State *L) {
    if (luaL_newmetatable(L, GAME_OBJECT_METATABLE) == 0) {
        lua_pop(L, 1);
        return;
    }
    lua_pushcfunction(L, lua_object_gc);
    lua_setfield(L, -2, "__gc");
    lua_pushcfunction(L, lua_object_eq);
    lua_setfield(L, -2, "__eq");
    lua_pushboolean(L, false);
    lua_setfield(L, -2, "__metatable");

    lua_createtable(L, 0, 16);
    const luaL_Reg methods[] = {{"getBoolProperty", lua_object_get_bool_property},
                                {"setBoolProperty", lua_object_set_bool_property},
                                {"getNumericProperty", lua_object_get_numeric_property},
                                {"setNumericProperty", lua_object_set_numeric_property},
                                {"getStringProperty", lua_object_get_string_property},
                                {"setStringProperty", lua_object_set_string_property},
                                {"hasProperty", lua_object_has_property},
                                {"getType", lua_object_get_type},
                                {"getName", lua_object_get_name},
                                {"heal", lua_creature_heal},
                                {"hurt", lua_creature_hurt},
                                {"healProc", lua_creature_heal_proc},
                                {"getCause", lua_event_get_cause},
                                {"createObject", lua_game_create_object},
                                {nullptr, nullptr}};
    luaL_setfuncs(L, methods, 0);
    lua_pushcclosure(L, lua_object_index, 1);
    lua_setfield(L, -2, "__index");
    lua_pushcfunction(L, lua_object_newindex);
    lua_setfield(L, -2, "__newindex");
    lua_pop(L, 1);

    if (luaL_newmetatable(L, LUA_HOST_METATABLE) != 0) {
        lua_pushcfunction(L, lua_host_gc);
        lua_setfield(L, -2, "__gc");
        lua_pushboolean(L, false);
        lua_setfield(L, -2, "__metatable");
    }
    lua_pop(L, 1);
}

void copy_allowlisted_library(lua_State *L, int envIndex, const char *libraryName,
                              std::initializer_list<const char *> excluded) {
    lua_getglobal(L, libraryName);
    if (!lua_istable(L, -1)) {
        lua_pop(L, 1);
        return;
    }
    lua_createtable(L, 0, 0);
    lua_pushnil(L);
    while (lua_next(L, -3) != 0) {
        bool skip = false;
        if (lua_type(L, -2) == LUA_TSTRING) {
            const std::string key = lua_tostring(L, -2);
            for (const char *name : excluded) {
                skip = skip || key == name;
            }
        }
        if (skip) {
            lua_pop(L, 1);
            continue;
        }
        lua_pushvalue(L, -2);
        lua_insert(L, -2);
        lua_settable(L, -4);
    }
    lua_setfield(L, envIndex, libraryName);
    lua_pop(L, 1);
}

// The sandboxed environment every plugin chunk runs in (defense-in-depth; the path allow-list
// in CLoader.cpp is the trust boundary). Deliberately absent: os, io, package, require, load,
// loadstring, dofile, loadfile, debug, coroutine, collectgarbage, getmetatable, setmetatable,
// rawget, rawset, rawequal, rawlen and _G itself.
void build_lua_sandbox_env(lua_State *L) {
    lua_createtable(L, 0, 16);
    const int envIndex = lua_gettop(L);
    for (const char *name :
         {"pairs", "ipairs", "next", "select", "type", "tostring", "tonumber", "error", "assert", "pcall", "xpcall"}) {
        lua_getglobal(L, name);
        lua_setfield(L, envIndex, name);
    }
    lua_pushcfunction(L, lua_plugin_log);
    lua_setfield(L, envIndex, "print");
    lua_pushcfunction(L, lua_randint);
    lua_setfield(L, envIndex, "randint");
    copy_allowlisted_library(L, envIndex, "math", {"randomseed"});
    copy_allowlisted_library(L, envIndex, "string", {"dump"});
    copy_allowlisted_library(L, envIndex, "table", {});
}

void push_context_table(lua_State *L, const std::shared_ptr<CGame> &game, std::weak_ptr<CLuaHandler> handler) {
    lua_createtable(L, 0, 4);
    void *storage = lua_newuserdatauv(L, sizeof(LuaHostContext), 0);
    new (storage) LuaHostContext{game, std::move(handler)};
    luaL_setmetatable(L, LUA_HOST_METATABLE);

    lua_pushvalue(L, -1);
    lua_pushcclosure(L, lua_context_register_type, 1);
    lua_setfield(L, -3, "registerType");
    lua_pushvalue(L, -1);
    lua_pushcclosure(L, lua_context_register_config_json, 1);
    lua_setfield(L, -3, "registerConfigJson");
    lua_pop(L, 1);

    lua_pushcfunction(L, lua_plugin_log);
    lua_setfield(L, -2, "log");
    // context.game is a normal CGameObject userdata, i.e. a strong reference to the game. The
    // table is scoped to the load(context) call and becomes collectable as soon as it returns.
    push_game_object(L, game);
    lua_setfield(L, -2, "game");
}

} // namespace

CLuaHandler::~CLuaHandler() { releaseState(); }

void CLuaHandler::releaseState() {
    if (luaState != nullptr) {
        lua_close(luaState);
        luaState = nullptr;
    }
}

bool CLuaHandler::ensureState() {
    if (luaState != nullptr) {
        return true;
    }
    luaState = luaL_newstate();
    if (luaState == nullptr) {
        vstd::logger::warning("Failed to create Lua state for plugins");
        return false;
    }
    // Only these four libraries are ever opened — io, os, package, debug and coroutine stay
    // closed — and plugins only see the allow-listed copies from build_lua_sandbox_env.
    luaL_requiref(luaState, LUA_GNAME, luaopen_base, 1);
    lua_pop(luaState, 1);
    luaL_requiref(luaState, LUA_MATHLIBNAME, luaopen_math, 1);
    lua_pop(luaState, 1);
    luaL_requiref(luaState, LUA_STRLIBNAME, luaopen_string, 1);
    lua_pop(luaState, 1);
    luaL_requiref(luaState, LUA_TABLIBNAME, luaopen_table, 1);
    lua_pop(luaState, 1);
    // Remove bytecode serialization even from the string-method metatable reachable via
    // ("literal"):method syntax.
    lua_getglobal(luaState, "string");
    lua_pushnil(luaState);
    lua_setfield(luaState, -2, "dump");
    lua_pop(luaState, 1);
    create_game_object_metatable(luaState);
    return true;
}

bool CLuaHandler::loadPlugin(const std::shared_ptr<CGame> &game, const std::string &path, const std::string &code) {
    if (!game || !ensureState()) {
        return false;
    }
    lua_State *L = luaState;
    const std::string chunkName = "@" + path;
    // Mode "t": text chunks only — precompiled Lua bytecode is rejected outright.
    if (luaL_loadbufferx(L, code.c_str(), code.size(), chunkName.c_str(), "t") != LUA_OK) {
        vstd::logger::warning("Failed to load Lua plugin:", path, lua_tostring(L, -1));
        lua_pop(L, 1);
        return false;
    }

    build_lua_sandbox_env(L);
    const int envIndex = lua_gettop(L);
    lua_pushvalue(L, envIndex);
    lua_setupvalue(L, -3, 1); // replace the chunk's _ENV with the sandbox

    lua_pushvalue(L, -2); // the chunk
    if (lua_pcall(L, 0, 0, 0) != LUA_OK) {
        vstd::logger::warning("Failed to load Lua plugin:", path, lua_tostring(L, -1));
        lua_pop(L, 3);
        return false;
    }

    lua_getfield(L, envIndex, "load");
    if (!lua_isfunction(L, -1)) {
        vstd::logger::warning("Lua plugin does not define a load function:", path);
        lua_pop(L, 3);
        return false;
    }
    push_context_table(L, game, weak_from_this());
    if (lua_pcall(L, 1, 0, 0) != LUA_OK) {
        vstd::logger::warning("Failed to load Lua plugin:", path, lua_tostring(L, -1));
        lua_pop(L, 3);
        return false;
    }
    lua_pop(L, 2); // sandbox env + chunk copy
    return true;
}

bool CLuaHandler::dispatch(const CGameObject *object, const char *hook,
                           const std::vector<std::shared_ptr<CGameObject>> &arguments) {
    auto *entry = CLuaOverrides::find(object);
    if (entry == nullptr) {
        // Every CLuaWrapper instance is retained at construction, so a missing entry means the
        // object was produced outside its factory and falls back to base behavior.
        vstd::logger::debug("Lua dispatch has no override entry for hook:", hook);
        return false;
    }
    auto handler = entry->handler.lock();
    if (!handler || handler->luaState == nullptr) {
        vstd::logger::debug("Lua dispatch skipped for hook after state release:", hook);
        return false;
    }
    lua_State *L = handler->luaState;
    lua_rawgeti(L, LUA_REGISTRYINDEX, entry->hooksRef);
    if (!lua_istable(L, -1)) {
        lua_pop(L, 1);
        return false;
    }
    lua_getfield(L, -1, hook);
    if (!lua_isfunction(L, -1)) {
        lua_pop(L, 2);
        return false;
    }
    push_game_object(L, entry->self);
    for (const auto &argument : arguments) {
        push_game_object(L, argument);
    }
    if (lua_pcall(L, static_cast<int>(arguments.size()) + 1, 0, 0) != LUA_OK) {
        vstd::logger::warning("Lua plugin error in hook:", hook, lua_tostring(L, -1));
        lua_pop(L, 1);
    }
    lua_pop(L, 1);
    return true;
}

bool CLuaHandler::dispatchBool(const CGameObject *object, const char *hook,
                               const std::vector<std::shared_ptr<CGameObject>> &arguments, bool &result) {
    auto *entry = CLuaOverrides::find(object);
    if (entry == nullptr) {
        return false;
    }
    auto handler = entry->handler.lock();
    if (!handler || handler->luaState == nullptr) {
        return false;
    }
    lua_State *L = handler->luaState;
    lua_rawgeti(L, LUA_REGISTRYINDEX, entry->hooksRef);
    if (!lua_istable(L, -1)) {
        lua_pop(L, 1);
        return false;
    }
    lua_getfield(L, -1, hook);
    if (!lua_isfunction(L, -1)) {
        lua_pop(L, 2);
        return false;
    }
    push_game_object(L, entry->self);
    for (const auto &argument : arguments) {
        push_game_object(L, argument);
    }
    if (lua_pcall(L, static_cast<int>(arguments.size()) + 1, 1, 0) != LUA_OK) {
        vstd::logger::warning("Lua plugin error in hook:", hook, lua_tostring(L, -1));
        lua_pop(L, 2);
        result = false;
        return true;
    }
    result = lua_toboolean(L, -1) != 0;
    lua_pop(L, 2);
    return true;
}
