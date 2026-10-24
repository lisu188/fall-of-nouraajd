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
#include <optional>
#include <string>
#include <unordered_map>

#include "core/CGlobal.h"
#include "core/CUtil.h"

class CGame;
class CGameLoader;
struct CSaveAdmissionState;
class CCreature;
class CGuiHandler;
class CConfigurationProvider;
class CMap;
class CObjectHandler;
class CResourcesProvider;
class CRngHandler;
class CScriptHandler;
class CSlotConfig;

// Context-owned cache of loaded maps that should outlive a single transition. Sessions are keyed by
// map name plus an optional instance id so multiple live copies of the same map can be retained. The
// store also remembers the coordinate from which a retained session was left so reuse can return the
// player to that session without replaying destination entry initialization.
class CMapSessionStore {
  public:
    static std::string makeKey(const std::string &mapName, const std::string &instanceId = "");

    void put(const std::string &mapName, const std::string &instanceId, const std::shared_ptr<CMap> &map);

    void put(const std::shared_ptr<CMap> &map, const std::string &instanceId = "");

    std::shared_ptr<CMap> get(const std::string &mapName, const std::string &instanceId = "") const;

    void setReturnCoords(const std::string &mapName, const std::string &instanceId, Coords coords);

    std::optional<Coords> getReturnCoords(const std::string &mapName, const std::string &instanceId = "") const;

    bool contains(const std::string &mapName, const std::string &instanceId = "") const;

    bool evict(const std::string &mapName, const std::string &instanceId = "");

    void clear();

    std::size_t size() const;

  private:
    std::unordered_map<std::string, std::shared_ptr<CMap>> sessions;
    std::unordered_map<std::string, Coords> returnCoordinates;
};

class CGameContext {
    friend class CGame;
    friend class CCreature;

  public:
    using TransitionGeneration = std::uint64_t;

    class UnsafeOperationLease {
      public:
        UnsafeOperationLease(UnsafeOperationLease &&) noexcept = default;
        UnsafeOperationLease &operator=(UnsafeOperationLease &&other) noexcept;
        UnsafeOperationLease(const UnsafeOperationLease &) = delete;
        UnsafeOperationLease &operator=(const UnsafeOperationLease &) = delete;
        ~UnsafeOperationLease() noexcept;
        bool isCurrent() const;
        void finish() noexcept;
        void quarantine() noexcept;

      private:
        friend class CGameContext;
        UnsafeOperationLease(std::shared_ptr<CSaveAdmissionState> state, std::shared_ptr<CSaveAdmissionState> local,
                             std::shared_ptr<CMap> map, std::weak_ptr<CGame> game, std::weak_ptr<CGameContext> context,
                             TransitionGeneration generation) noexcept;
        void release(bool quarantine) noexcept;
        std::shared_ptr<CSaveAdmissionState> state;
        std::shared_ptr<CSaveAdmissionState> local;
        std::shared_ptr<CMap> map;
        std::weak_ptr<CGame> game;
        std::weak_ptr<CGameContext> context;
        TransitionGeneration generation;
    };

    class SaveSnapshotLease {
      public:
        SaveSnapshotLease(SaveSnapshotLease &&) noexcept = default;
        SaveSnapshotLease &operator=(SaveSnapshotLease &&other) noexcept;
        SaveSnapshotLease(const SaveSnapshotLease &) = delete;
        SaveSnapshotLease &operator=(const SaveSnapshotLease &) = delete;
        ~SaveSnapshotLease() noexcept;

      private:
        friend class CGameContext;
        SaveSnapshotLease(std::shared_ptr<CSaveAdmissionState> first,
                          std::shared_ptr<CSaveAdmissionState> second) noexcept;
        void release() noexcept;
        std::shared_ptr<CSaveAdmissionState> first;
        std::shared_ptr<CSaveAdmissionState> second;
    };

    explicit CGameContext(std::shared_ptr<CGame> game);

    std::shared_ptr<CObjectHandler> getObjectHandler();

    std::shared_ptr<CGuiHandler> getGuiHandler();

    std::shared_ptr<CScriptHandler> getScriptHandler();

    std::shared_ptr<CRngHandler> getRngHandler();

    std::shared_ptr<CSlotConfig> getSlotConfiguration();

    std::shared_ptr<CResourcesProvider> getResourcesProvider();

    std::shared_ptr<CConfigurationProvider> getConfigurationProvider();

    std::shared_ptr<CMapSessionStore> getMapSessionStore();

    void addEventLoopConnection(vstd::event_loop<>::connection connection);

    bool trackEffectOwner(const std::shared_ptr<CCreature> &creature);

    void untrackEffectOwner(const CCreature *creature);

    std::size_t getEffectOwnerCount() const;

    bool isActive() const;

    template <typename T> vstd::task_handle<T> spawnTask(vstd::task<T> task) {
        requireActiveService("task group");
        return tasks->spawn(std::move(task), vstd::loopScheduler(vstd::event_loop<>::instance()));
    }

    void shutdown();

    TransitionGeneration getTransitionGeneration() const;

    TransitionGeneration captureTransitionGeneration() const;

    bool isTransitionGenerationCurrent(TransitionGeneration expectedGeneration) const;

    TransitionGeneration advanceTransitionGeneration();

  private:
    friend class CMap;
    friend class CGameLoader;
    class VerifiedRestoreLease {
      public:
        VerifiedRestoreLease(VerifiedRestoreLease &&) noexcept = default;
        VerifiedRestoreLease(const VerifiedRestoreLease &) = delete;
        VerifiedRestoreLease &operator=(const VerifiedRestoreLease &) = delete;
        ~VerifiedRestoreLease() noexcept;

      private:
        friend class CGameContext;
        friend class CGameLoader;
        VerifiedRestoreLease(std::shared_ptr<CSaveAdmissionState> state, std::weak_ptr<CGameContext> context,
                             TransitionGeneration generation, std::uint64_t revision,
                             std::shared_ptr<CMap> previousMap) noexcept;
        bool commit(const std::shared_ptr<CMap> &installedMap);
        std::shared_ptr<CSaveAdmissionState> state;
        std::weak_ptr<CGameContext> context;
        TransitionGeneration generation;
        std::uint64_t revision;
        std::shared_ptr<CMap> previousMap;
    };

    static std::shared_ptr<CSaveAdmissionState> makeSaveAdmissionState();
    static std::optional<SaveSnapshotLease> tryBeginMapSnapshot(const std::shared_ptr<CMap> &map);
    std::optional<UnsafeOperationLease> tryBeginUnsafeOperation(const std::shared_ptr<CMap> &map);
    std::optional<VerifiedRestoreLease> tryBeginVerifiedRestore();
    bool completeVerifiedRestore(const std::shared_ptr<CSaveAdmissionState> &state, TransitionGeneration generation,
                                 std::uint64_t revision, const std::shared_ptr<CMap> &previousMap,
                                 const std::shared_ptr<CMap> &installedMap);

    struct ShutdownState;
    static vstd::task<void> finishShutdownAsync(std::shared_ptr<ShutdownState> state);

    void shutdown(CGame *owner);

    void requireActiveService(const char *serviceName) const;

    std::shared_ptr<std::recursive_mutex> resourceMutex;
    std::shared_ptr<CSaveAdmissionState> saveAdmission;
    std::weak_ptr<CGame> game;
    std::shared_ptr<CGuiHandler> guiHandler;
    std::shared_ptr<CObjectHandler> objectHandler;
    std::shared_ptr<CScriptHandler> scriptHandler;
    std::shared_ptr<CRngHandler> rngHandler;
    std::shared_ptr<CResourcesProvider> resourcesProvider;
    std::shared_ptr<CConfigurationProvider> configurationProvider;
    std::shared_ptr<CMapSessionStore> mapSessionStore;
    std::vector<vstd::event_loop<>::connection> eventLoopConnections;
    std::unordered_map<const CCreature *, std::weak_ptr<CCreature>> effectOwners;
    const std::shared_ptr<const int> effectOwnerIdentity = std::make_shared<const int>(0);
    std::shared_ptr<CSlotConfig> slotConfiguration;
    std::atomic<bool> active = true;
    std::atomic<TransitionGeneration> transitionGeneration = 0;
    std::shared_ptr<vstd::task_group> tasks = std::make_shared<vstd::task_group>();
    std::shared_ptr<ShutdownState> shutdownState;
};
