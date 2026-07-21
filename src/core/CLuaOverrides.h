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

#include <memory>
#include <unordered_map>

class CGameObject;
class CLuaHandler;

// Lua analogue of CPythonOverrides: maps engine objects created by Lua-registered factories to
// the hook table that scripts their behavior. Entries hold the owning handler weakly so objects
// that outlive the per-game lua_State (map session stores, teardown ordering) dispatch as
// "no override" instead of touching a closed state.
namespace CLuaOverrides {

struct Entry {
    std::weak_ptr<CLuaHandler> handler;
    int hooksRef; // luaL_ref of the registered type's hook table in LUA_REGISTRYINDEX
    std::shared_ptr<CGameObject> self;
};

inline std::unordered_map<const CGameObject *, Entry> &instances() {
    // Intentionally leaked, mirroring CPythonOverrides::instances(): entries may be consulted
    // during static teardown; the expired weak_ptr guard makes that a safe no-op.
    static auto *registry = new std::unordered_map<const CGameObject *, Entry>();
    return *registry;
}

inline void retain(const std::shared_ptr<CGameObject> &object, std::weak_ptr<CLuaHandler> handler, int hooksRef) {
    if (!object) {
        return;
    }
    instances()[object.get()] = Entry{std::move(handler), hooksRef, object};
}

inline Entry *find(const CGameObject *object) {
    auto it = instances().find(object);
    return it == instances().end() ? nullptr : &it->second;
}

inline void release(const CGameObject *object) { instances().erase(object); }

} // namespace CLuaOverrides
