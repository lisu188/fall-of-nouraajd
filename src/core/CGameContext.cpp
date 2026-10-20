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
#include "core/CGameContext.h"
#include "core/CAsync.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CNavigation.h"
#include "core/CMap.h"
#include "core/CProvider.h"
#include "core/CSceneManager.h"
#include "core/CSlotConfig.h"
#include "gui/CGui.h"
#include "handler/CGuiHandler.h"
#include "handler/CObjectHandler.h"
#include "handler/CRngHandler.h"
#include "handler/CScriptHandler.h"
#include "object/CCreature.h"

#include <atomic>
#include <stdexcept>
#include <utility>

CGameContext::CGameContext(std::shared_ptr<CGame> game)
    : resourceMutex(game ? game->resourceMutex : std::make_shared<std::recursive_mutex>()), game(std::move(game)) {
    // Establish the loop thread at session creation, including sessions that only attach a GUI.
    vstd::event_loop<>::instance();
}

std::shared_ptr<CObjectHandler> CGameContext::getObjectHandler() {
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CObjectHandler");
    if (!objectHandler) {
        objectHandler = std::make_shared<CObjectHandler>();
    }
    return objectHandler;
}

std::shared_ptr<CGuiHandler> CGameContext::getGuiHandler() {
    auto owner = game.lock();
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CGuiHandler");
    if (!guiHandler) {
        if (!owner) {
            throw std::runtime_error("Cannot create CGuiHandler without an active CGame.");
        }
        guiHandler = std::make_shared<CGuiHandler>(owner);
    }
    return guiHandler;
}

std::shared_ptr<CScriptHandler> CGameContext::getScriptHandler() {
    {
        std::lock_guard lock(*resourceMutex);
        requireActiveService("CScriptHandler");
        if (scriptHandler) {
            return scriptHandler;
        }
    }
    auto created = std::make_shared<CScriptHandler>();
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CScriptHandler");
    if (!scriptHandler) {
        scriptHandler = std::move(created);
    }
    return scriptHandler;
}

std::shared_ptr<CRngHandler> CGameContext::getRngHandler() {
    {
        std::lock_guard lock(*resourceMutex);
        requireActiveService("CRngHandler");
        if (rngHandler) {
            return rngHandler;
        }
    }
    auto owner = game.lock();
    if (!owner) {
        throw std::runtime_error("Cannot create CRngHandler without an active CGame.");
    }
    auto created = std::make_shared<CRngHandler>(owner);
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CRngHandler");
    if (!rngHandler) {
        rngHandler = std::move(created);
    }
    return rngHandler;
}

std::shared_ptr<CSlotConfig> CGameContext::getSlotConfiguration() {
    {
        std::lock_guard lock(*resourceMutex);
        requireActiveService("CSlotConfig");
        if (slotConfiguration) {
            return slotConfiguration;
        }
    }
    auto owner = game.lock();
    if (!owner) {
        throw std::runtime_error("Cannot create CSlotConfig without an active CGame.");
    }
    auto created = owner->createObject<CSlotConfig>("slotConfiguration");
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CSlotConfig");
    if (!slotConfiguration) {
        slotConfiguration = std::move(created);
    }
    return slotConfiguration;
}

std::shared_ptr<CResourcesProvider> CGameContext::getResourcesProvider() {
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CResourcesProvider");
    if (!resourcesProvider) {
        resourcesProvider = std::make_shared<CResourcesProvider>();
    }
    return resourcesProvider;
}

std::shared_ptr<CConfigurationProvider> CGameContext::getConfigurationProvider() {
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CConfigurationProvider");
    if (!configurationProvider) {
        configurationProvider = std::make_shared<CConfigurationProvider>(getResourcesProvider());
    }
    return configurationProvider;
}

std::shared_ptr<CMapSessionStore> CGameContext::getMapSessionStore() {
    std::lock_guard lock(*resourceMutex);
    requireActiveService("CMapSessionStore");
    if (!mapSessionStore) {
        mapSessionStore = std::make_shared<CMapSessionStore>();
    }
    return mapSessionStore;
}

void CGameContext::addEventLoopConnection(vstd::event_loop<>::connection connection) {
    std::lock_guard lock(*resourceMutex);
    requireActiveService("event loop");
    eventLoopConnections.push_back(std::move(connection));
}

bool CGameContext::trackEffectOwner(const std::shared_ptr<CCreature> &creature) {
    std::lock_guard lock(*resourceMutex);
    if (isActive() && creature) {
        effectOwners[creature.get()] = creature;
        return true;
    }
    return false;
}

void CGameContext::untrackEffectOwner(const CCreature *creature) {
    std::lock_guard lock(*resourceMutex);
    effectOwners.erase(creature);
}

std::size_t CGameContext::getEffectOwnerCount() const {
    std::lock_guard lock(*resourceMutex);
    return effectOwners.size();
}

std::string CMapSessionStore::makeKey(const std::string &mapName, const std::string &instanceId) {
    // Length-prefix the map name so distinct (mapName, instanceId) pairs never collide.
    return std::to_string(mapName.size()) + ":" + mapName + ":" + instanceId;
}

void CMapSessionStore::put(const std::string &mapName, const std::string &instanceId,
                           const std::shared_ptr<CMap> &map) {
    if (!map) {
        return;
    }
    const auto key = makeKey(mapName, instanceId);
    sessions[key] = map;
    returnCoordinates.erase(key);
}

void CMapSessionStore::put(const std::shared_ptr<CMap> &map, const std::string &instanceId) {
    if (!map) {
        return;
    }
    put(map->getMapName(), instanceId, map);
}

std::shared_ptr<CMap> CMapSessionStore::get(const std::string &mapName, const std::string &instanceId) const {
    auto it = sessions.find(makeKey(mapName, instanceId));
    return it != sessions.end() ? it->second : nullptr;
}

void CMapSessionStore::setReturnCoords(const std::string &mapName, const std::string &instanceId, Coords coords) {
    const auto key = makeKey(mapName, instanceId);
    if (sessions.contains(key)) {
        returnCoordinates[key] = coords;
    }
}

std::optional<Coords> CMapSessionStore::getReturnCoords(const std::string &mapName,
                                                        const std::string &instanceId) const {
    auto it = returnCoordinates.find(makeKey(mapName, instanceId));
    return it != returnCoordinates.end() ? std::optional<Coords>(it->second) : std::nullopt;
}

bool CMapSessionStore::contains(const std::string &mapName, const std::string &instanceId) const {
    return sessions.find(makeKey(mapName, instanceId)) != sessions.end();
}

bool CMapSessionStore::evict(const std::string &mapName, const std::string &instanceId) {
    const auto key = makeKey(mapName, instanceId);
    returnCoordinates.erase(key);
    return sessions.erase(key) > 0;
}

void CMapSessionStore::clear() {
    sessions.clear();
    returnCoordinates.clear();
}

std::size_t CMapSessionStore::size() const { return sessions.size(); }

bool CGameContext::isActive() const { return active.load(std::memory_order_acquire); }

void CGameContext::shutdown() {
    auto owner = game.lock();
    shutdown(owner.get());
}

struct CGameContext::ShutdownState {
    std::shared_ptr<vstd::task_group> tasks;
    vstd::task_group finalizer;
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CSceneManager> sceneManager;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CGuiHandler> guiHandler;
    std::shared_ptr<CObjectHandler> objectHandler;
    std::shared_ptr<CScriptHandler> scriptHandler;
    std::shared_ptr<CRngHandler> rngHandler;
    std::shared_ptr<CResourcesProvider> resourcesProvider;
    std::shared_ptr<CConfigurationProvider> configurationProvider;
    std::shared_ptr<CMapSessionStore> mapSessionStore;
    std::shared_ptr<CNavigationService> navigationService;
    std::unordered_map<const CCreature *, std::weak_ptr<CCreature>> effectOwners;
    std::shared_ptr<const int> effectOwnerIdentity;
    std::shared_ptr<CSlotConfig> slotConfiguration;
    bool released = false;

    void release() {
        if (std::exchange(released, true)) {
            return;
        }
        std::optional<pybind11::gil_scoped_acquire> gil;
        if (Py_IsInitialized()) {
            gil.emplace();
        }
        if (sceneManager) {
            sceneManager->resetTransition();
        }
        if (gui) {
            gui->shutdown();
        }
        for (const auto &[identity, reference] : effectOwners) {
            if (auto creature = reference.lock()) {
                creature->releaseEffectReferences(effectOwnerIdentity);
            }
        }
        effectOwners.clear();
        gui.reset();
        sceneManager.reset();
        map.reset();
        if (scriptHandler) {
            scriptHandler->releaseState();
        }
        slotConfiguration.reset();
        if (mapSessionStore) {
            mapSessionStore->clear();
        }
        mapSessionStore.reset();
        configurationProvider.reset();
        resourcesProvider.reset();
        scriptHandler.reset();
        guiHandler.reset();
        rngHandler.reset();
        objectHandler.reset();
        if (navigationService) {
            navigationService->clearSessionCaches();
        }
        navigationService.reset();
    }
};

vstd::task<void> CGameContext::finishShutdownAsync(std::shared_ptr<ShutdownState> state) {
    co_await vstd::post(vstd::event_loop<>::instance());
    co_await vstd::until(vstd::event_loop<>::instance(), [state] { return state->tasks->finished(); });
    state->release();
}

void CGameContext::shutdown(CGame *owner) {
    std::shared_ptr<ShutdownState> state;
    std::vector<vstd::event_loop<>::connection> connections;
    {
        std::lock_guard resource_lock(*resourceMutex);
        if (!active.exchange(false, std::memory_order_acq_rel)) {
            return;
        }
        advanceTransitionGeneration();
        connections = std::move(eventLoopConnections);
        state = std::make_shared<ShutdownState>();
        shutdownState = state;
        state->tasks = tasks;
        if (owner) {
            if (owner->_gui) {
                owner->_gui->deactivate();
                state->gui = std::move(owner->_gui);
            }
            state->sceneManager = owner->sceneManager;
            state->map = std::move(owner->map);
            std::lock_guard lock(owner->navigationServiceMutex);
            state->navigationService = std::move(owner->navigationService);
        }
        state->effectOwners = std::move(effectOwners);
        state->effectOwnerIdentity = effectOwnerIdentity;
        effectOwners.clear();
        state->slotConfiguration = std::move(slotConfiguration);
        state->mapSessionStore = std::move(mapSessionStore);
        state->configurationProvider = std::move(configurationProvider);
        state->resourcesProvider = std::move(resourcesProvider);
        state->scriptHandler = std::move(scriptHandler);
        state->guiHandler = std::move(guiHandler);
        state->rngHandler = std::move(rngHandler);
        state->objectHandler = std::move(objectHandler);
    }
    connections.clear();
    const bool inside_task = tasks->ownsCurrentTask();
    tasks->requestStop();
    if (!inside_task && !state->gui && !state->sceneManager && tasks->finished()) {
        state->release();
        return;
    }
    auto completion =
        state->finalizer.spawn(finishShutdownAsync(state), vstd::loopScheduler(vstd::event_loop<>::instance()));
    if (!inside_task) {
        game_async::wait(completion, game_async::WaitMode::PostedWork);
    }
}

CGameContext::TransitionGeneration CGameContext::getTransitionGeneration() const {
    return transitionGeneration.load(std::memory_order_acquire);
}

CGameContext::TransitionGeneration CGameContext::captureTransitionGeneration() const {
    return getTransitionGeneration();
}

bool CGameContext::isTransitionGenerationCurrent(TransitionGeneration expectedGeneration) const {
    return isActive() && getTransitionGeneration() == expectedGeneration;
}

CGameContext::TransitionGeneration CGameContext::advanceTransitionGeneration() {
    return transitionGeneration.fetch_add(1, std::memory_order_acq_rel) + 1;
}

void CGameContext::requireActiveService(const char *serviceName) const {
    if (!isActive()) {
        throw std::runtime_error(std::string("Cannot access ") + serviceName + " after CGameContext shutdown.");
    }
}
