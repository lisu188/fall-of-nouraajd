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

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>

#include "core/CGlobal.h"

class CGame;
class CGuiHandler;
class CConfigurationProvider;
class CLuaHandler;
class CMap;
class CObjectHandler;
class CResourcesProvider;
class CRngHandler;
class CScriptHandler;
class CSlotConfig;

// Context-owned cache of loaded maps that should outlive a single transition. Sessions are keyed by
// map name plus an optional instance id so multiple live copies of the same map can be retained. The
// store only retains and hands back maps; it does not change transition semantics on its own.
class CMapSessionStore {
  public:
    static std::string makeKey(const std::string &mapName, const std::string &instanceId = "");

    void put(const std::string &mapName, const std::string &instanceId, const std::shared_ptr<CMap> &map);

    void put(const std::shared_ptr<CMap> &map, const std::string &instanceId = "");

    std::shared_ptr<CMap> get(const std::string &mapName, const std::string &instanceId = "") const;

    bool contains(const std::string &mapName, const std::string &instanceId = "") const;

    bool evict(const std::string &mapName, const std::string &instanceId = "");

    void clear();

    std::size_t size() const;

  private:
    std::unordered_map<std::string, std::shared_ptr<CMap>> sessions;
};

class CGameContext {
    friend class CGame;

  public:
    using TransitionGeneration = std::uint64_t;

    explicit CGameContext(std::shared_ptr<CGame> game);

    std::shared_ptr<CObjectHandler> getObjectHandler();

    std::shared_ptr<CGuiHandler> getGuiHandler();

    std::shared_ptr<CScriptHandler> getScriptHandler();

    std::shared_ptr<CLuaHandler> getLuaHandler();

    std::shared_ptr<CRngHandler> getRngHandler();

    std::shared_ptr<CSlotConfig> getSlotConfiguration();

    std::shared_ptr<CResourcesProvider> getResourcesProvider();

    std::shared_ptr<CConfigurationProvider> getConfigurationProvider();

    std::shared_ptr<CMapSessionStore> getMapSessionStore();

    bool isActive() const;

    void shutdown();

    TransitionGeneration getTransitionGeneration() const;

    TransitionGeneration captureTransitionGeneration() const;

    bool isTransitionGenerationCurrent(TransitionGeneration expectedGeneration) const;

    TransitionGeneration advanceTransitionGeneration();

  private:
    void shutdown(CGame *owner);

    void requireActiveService(const char *serviceName) const;

    std::weak_ptr<CGame> game;
    std::shared_ptr<CGuiHandler> guiHandler;
    std::shared_ptr<CObjectHandler> objectHandler;
    std::shared_ptr<CScriptHandler> scriptHandler;
    std::shared_ptr<CLuaHandler> luaHandler;
    std::shared_ptr<CRngHandler> rngHandler;
    std::shared_ptr<CResourcesProvider> resourcesProvider;
    std::shared_ptr<CConfigurationProvider> configurationProvider;
    std::shared_ptr<CMapSessionStore> mapSessionStore;
    vstd::lazy<CSlotConfig> slotConfiguration;
    std::atomic<bool> active = true;
    std::atomic<TransitionGeneration> transitionGeneration = 0;
};
