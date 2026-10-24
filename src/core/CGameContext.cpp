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
#include <mutex>
#include <stdexcept>
#include <utility>

struct CSaveAdmissionState {
    enum class Exclusive { None, Snapshot, Restore };
    std::mutex mutex;
    std::size_t unsafeOwners = 0;
    Exclusive exclusive = Exclusive::None;
    bool quarantined = false;
    std::uint64_t quarantineRevision = 0;
};

namespace {
class SaveAdmissionLocks {
  public:
    SaveAdmissionLocks(const std::shared_ptr<CSaveAdmissionState> &first,
                       const std::shared_ptr<CSaveAdmissionState> &second)
        : firstLock(first->mutex, std::defer_lock) {
        if (second && second != first) {
            secondLock = std::unique_lock(second->mutex, std::defer_lock);
            std::lock(firstLock, secondLock);
        } else {
            firstLock.lock();
        }
    }

  private:
    std::unique_lock<std::mutex> firstLock;
    std::unique_lock<std::mutex> secondLock;
};

bool acceptsSnapshot(const std::shared_ptr<CSaveAdmissionState> &state) {
    return state->unsafeOwners == 0 && state->exclusive == CSaveAdmissionState::Exclusive::None && !state->quarantined;
}
} // namespace

std::shared_ptr<CSaveAdmissionState> CGameContext::makeSaveAdmissionState() {
    return std::make_shared<CSaveAdmissionState>();
}

CGameContext::UnsafeOperationLease::UnsafeOperationLease(std::shared_ptr<CSaveAdmissionState> state,
                                                         std::shared_ptr<CSaveAdmissionState> local,
                                                         std::shared_ptr<CMap> map, std::weak_ptr<CGame> game,
                                                         std::weak_ptr<CGameContext> context,
                                                         TransitionGeneration generation) noexcept
    : state(std::move(state)), local(std::move(local)), map(std::move(map)), game(std::move(game)),
      context(std::move(context)), generation(generation) {}

CGameContext::UnsafeOperationLease &
CGameContext::UnsafeOperationLease::operator=(UnsafeOperationLease &&other) noexcept {
    if (this != &other) {
        quarantine();
        state = std::move(other.state);
        local = std::move(other.local);
        map = std::move(other.map);
        game = std::move(other.game);
        context = std::move(other.context);
        generation = other.generation;
    }
    return *this;
}

CGameContext::UnsafeOperationLease::~UnsafeOperationLease() noexcept { quarantine(); }

bool CGameContext::UnsafeOperationLease::isCurrent() const {
    auto owner = game.lock();
    auto capturedContext = context.lock();
    return state && owner && capturedContext && owner->getContext() == capturedContext &&
           capturedContext->isTransitionGenerationCurrent(generation) && owner->getMap() == map &&
           map->getGame() == owner;
}

void CGameContext::UnsafeOperationLease::release(bool quarantineSave) noexcept {
    auto ownedState = std::move(state);
    auto ownedLocal = std::move(local);
    auto ownedMap = std::move(map);
    if (!ownedState) {
        return;
    }
    SaveAdmissionLocks lock(ownedState, ownedLocal);
    if (quarantineSave) {
        ownedState->quarantined = true;
        ++ownedState->quarantineRevision;
        ownedLocal->quarantined = true;
        ++ownedLocal->quarantineRevision;
    }
    --ownedState->unsafeOwners;
    --ownedLocal->unsafeOwners;
}

void CGameContext::UnsafeOperationLease::finish() noexcept { release(false); }
void CGameContext::UnsafeOperationLease::quarantine() noexcept { release(true); }

CGameContext::SaveSnapshotLease::SaveSnapshotLease(std::shared_ptr<CSaveAdmissionState> first,
                                                   std::shared_ptr<CSaveAdmissionState> second) noexcept
    : first(std::move(first)), second(std::move(second)) {}

CGameContext::SaveSnapshotLease &CGameContext::SaveSnapshotLease::operator=(SaveSnapshotLease &&other) noexcept {
    if (this != &other) {
        release();
        first = std::move(other.first);
        second = std::move(other.second);
    }
    return *this;
}

CGameContext::SaveSnapshotLease::~SaveSnapshotLease() noexcept { release(); }

void CGameContext::SaveSnapshotLease::release() noexcept {
    auto ownedFirst = std::move(first);
    auto ownedSecond = std::move(second);
    if (ownedFirst) {
        SaveAdmissionLocks lock(ownedFirst, ownedSecond);
        ownedFirst->exclusive = CSaveAdmissionState::Exclusive::None;
        if (ownedSecond) {
            ownedSecond->exclusive = CSaveAdmissionState::Exclusive::None;
        }
    }
}

std::optional<CGameContext::UnsafeOperationLease>
CGameContext::tryBeginUnsafeOperation(const std::shared_ptr<CMap> &map) {
    auto owner = game.lock();
    if (!owner || !isActive() || !map || owner->getContext().get() != this || owner->getMap() != map ||
        map->getGame() != owner) {
        return std::nullopt;
    }
    auto capturedContext = owner->getContext();
    const auto generation = captureTransitionGeneration();
    auto local = map->saveAdmissionState;
    {
        SaveAdmissionLocks lock(saveAdmission, local);
        if (saveAdmission->exclusive != CSaveAdmissionState::Exclusive::None || saveAdmission->quarantined ||
            local->exclusive != CSaveAdmissionState::Exclusive::None || local->quarantined) {
            return std::nullopt;
        }
        ++saveAdmission->unsafeOwners;
        ++local->unsafeOwners;
    }
    UnsafeOperationLease lease(saveAdmission, local, map, owner, capturedContext, generation);
    if (!lease.isCurrent()) {
        lease.finish();
        return std::nullopt;
    }
    return lease;
}

std::optional<CGameContext::SaveSnapshotLease> CGameContext::tryBeginMapSnapshot(const std::shared_ptr<CMap> &map) {
    auto owner = map->getGame();
    auto capturedContext = owner ? owner->getContext() : nullptr;
    auto local = map->saveAdmissionState;
    auto session = capturedContext ? capturedContext->saveAdmission : local;
    SaveAdmissionLocks lock(session, local);
    if ((capturedContext && !capturedContext->isActive()) || !acceptsSnapshot(session) ||
        (local != session && !acceptsSnapshot(local))) {
        return std::nullopt;
    }
    session->exclusive = CSaveAdmissionState::Exclusive::Snapshot;
    if (local != session) {
        local->exclusive = CSaveAdmissionState::Exclusive::Snapshot;
    }
    return SaveSnapshotLease(session, local != session ? local : nullptr);
}

CGameContext::VerifiedRestoreLease::VerifiedRestoreLease(std::shared_ptr<CSaveAdmissionState> state,
                                                         std::weak_ptr<CGameContext> context,
                                                         TransitionGeneration generation, std::uint64_t revision,
                                                         std::shared_ptr<CMap> previousMap) noexcept
    : state(std::move(state)), context(std::move(context)), generation(generation), revision(revision),
      previousMap(std::move(previousMap)) {}

CGameContext::VerifiedRestoreLease::~VerifiedRestoreLease() noexcept {
    if (state) {
        std::lock_guard lock(state->mutex);
        state->exclusive = CSaveAdmissionState::Exclusive::None;
    }
}

bool CGameContext::VerifiedRestoreLease::commit(const std::shared_ptr<CMap> &installedMap) {
    auto capturedContext = context.lock();
    return state && capturedContext &&
           capturedContext->completeVerifiedRestore(state, generation, revision, previousMap, installedMap);
}

std::optional<CGameContext::VerifiedRestoreLease> CGameContext::tryBeginVerifiedRestore() {
    auto owner = game.lock();
    if (!owner || !isActive()) {
        return std::nullopt;
    }
    auto capturedContext = owner->getContext();
    auto previousMap = owner->getMap();
    const auto generation = captureTransitionGeneration();
    std::lock_guard lock(saveAdmission->mutex);
    if (saveAdmission->unsafeOwners != 0 || saveAdmission->exclusive != CSaveAdmissionState::Exclusive::None) {
        return std::nullopt;
    }
    saveAdmission->exclusive = CSaveAdmissionState::Exclusive::Restore;
    return VerifiedRestoreLease(saveAdmission, capturedContext, generation, saveAdmission->quarantineRevision,
                                std::move(previousMap));
}

bool CGameContext::completeVerifiedRestore(const std::shared_ptr<CSaveAdmissionState> &state,
                                           TransitionGeneration generation, std::uint64_t revision,
                                           const std::shared_ptr<CMap> &previousMap,
                                           const std::shared_ptr<CMap> &installedMap) {
    auto owner = game.lock();
    if (!owner || !installedMap || installedMap == previousMap) {
        return false;
    }
    const auto local = installedMap->saveAdmissionState;
    std::scoped_lock lock(*resourceMutex, state->mutex, local->mutex);
    if (owner->context.get() != this || owner->map != installedMap || installedMap->getGame() != owner ||
        !isTransitionGenerationCurrent(generation) || state != saveAdmission || state->unsafeOwners != 0 ||
        state->exclusive != CSaveAdmissionState::Exclusive::Restore || state->quarantineRevision != revision ||
        !acceptsSnapshot(local)) {
        return false;
    }
    state->quarantined = false;
    return true;
}

CGameContext::CGameContext(std::shared_ptr<CGame> game)
    : resourceMutex(game ? game->resourceMutex : std::make_shared<std::recursive_mutex>()),
      saveAdmission(makeSaveAdmissionState()), game(std::move(game)) {
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
