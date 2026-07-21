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
#include "core/CTypes.h"

class CGame;

// The single host surface every plugin runtime registers through. Native plugins receive it
// via the CPluginHostV2 handshake (see plugin/CPluginAbi.h), the in-engine CPlugin subclasses
// via CPlugin::load, and scripted runtimes (Python, Lua) through their language adapters.
//
// registerType<T, Bases...> intentionally performs the same double registration the engine has
// always relied on: the process-global CTypes tables (builders, serializers, casts) plus the
// per-game CObjectHandler factory that makes the type constructible from JSON in the game that
// is currently loading. The per-game half matters even for the first game of a process, because
// CGameLoader::initObjectHandler copies CTypes::builders() before plugins load.
class GAME_CORE_EXPORT CPluginRegistrar {
  public:
    explicit CPluginRegistrar(std::shared_ptr<CGame> game);

    void log(const std::string &message) const;

    bool registerConfigJson(const std::string &id, const std::string &jsonText) const;

    bool registerFactory(const std::string &name, std::function<std::shared_ptr<CGameObject>()> factory) const;

    template <fn::MetaRegisteredGameObject T, fn::GameObjectDerived... Bases> bool registerType() const {
        CTypes::register_type<T, Bases...>();
        return registerFactory(T::static_meta()->name(), []() { return std::make_shared<T>(); });
    }

    // Trusted escape hatch for in-tree plugins that need engine services beyond registration.
    const std::shared_ptr<CGame> &game() const { return _game; }

  private:
    std::shared_ptr<CGame> _game;
};
