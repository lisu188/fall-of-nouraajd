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
#pragma once

#include "core/CExport.h"
#include <memory>
#include <string>
#include <vector>

class CGame;
class CGameObject;

struct lua_State;

// Per-game Lua plugin runtime, owned by CGameContext beside CScriptHandler. Loads sandboxed
// plugins from res/plugins/*.lua (see build_lua_sandbox_env in CLuaHandler.cpp for the exact
// environment) and dispatches engine virtuals to registered hook tables via CLuaWrapper<T>.
// The Lua C API is confined to CLuaHandler.cpp; this header stays C-header free.
class GAME_CORE_EXPORT CLuaHandler : public std::enable_shared_from_this<CLuaHandler> {
  public:
    CLuaHandler() = default;

    ~CLuaHandler();

    CLuaHandler(const CLuaHandler &) = delete;
    CLuaHandler &operator=(const CLuaHandler &) = delete;

    // Closes the lua_State. Objects retained past this point dispatch as "no override".
    void releaseState();

    // Executes a plugin chunk in a fresh sandbox environment and invokes its load(context).
    bool loadPlugin(const std::shared_ptr<CGame> &game, const std::string &path, const std::string &code);

    // Engine-to-Lua dispatch used by CLuaWrapper<T>. Returns true when a Lua hook handled the
    // call — including a hook that errored; Lua errors log and are contained, mirroring the
    // PY_SAFE contract — and false when the caller should fall back to the base implementation.
    static bool dispatch(const CGameObject *object, const char *hook,
                         const std::vector<std::shared_ptr<CGameObject>> &arguments = {});

    // Variant for bool-returning hooks; on a contained Lua error `result` is false.
    static bool dispatchBool(const CGameObject *object, const char *hook,
                             const std::vector<std::shared_ptr<CGameObject>> &arguments, bool &result);

  private:
    bool ensureState();

    lua_State *luaState = nullptr;
};
