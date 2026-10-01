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

#include "core/CUtil.h"

#include <array>
#include <atomic>
#include <memory_resource>
#include <mutex>
#include <span>

class CMap;
class CMapObject;
class CNavigationService;
class CNavigationSearchWorkspace;
struct CNavigationFlowResult;
struct CNavigationFlowStatistics;
struct CNavigationSearchResult;

struct CNavigationCoordsHash {
    std::size_t operator()(const Coords &coords) const noexcept {
        auto mix = [](std::uint64_t value) {
            value ^= value >> 30;
            value *= 0xbf58476d1ce4e5b9ULL;
            value ^= value >> 27;
            value *= 0x94d049bb133111ebULL;
            return value ^ (value >> 31);
        };
        auto x = mix(static_cast<std::uint32_t>(coords.x));
        auto y = mix(static_cast<std::uint32_t>(coords.y) + 0x9e3779b97f4a7c15ULL);
        auto z = mix(static_cast<std::uint32_t>(coords.z) + 0x3c6ef372fe94f82aULL);
        return static_cast<std::size_t>(mix(x ^ y ^ z));
    }
};

class CNavigationBudget : public std::pmr::memory_resource {
  public:
    static constexpr std::size_t DEFAULT_LIMIT = 128 * 1024 * 1024;
    explicit CNavigationBudget(std::size_t limit = DEFAULT_LIMIT);
    bool tryReserve(std::size_t bytes);
    void release(std::size_t bytes);
    std::size_t used() const;
    std::size_t peak() const;
    std::size_t limit() const;

  private:
    std::size_t maximum;
    std::atomic_size_t allocated{0};
    std::atomic_size_t maximumAllocated{0};
    void *do_allocate(std::size_t bytes, std::size_t alignment) override;
    void do_deallocate(void *pointer, std::size_t bytes, std::size_t alignment) override;
    bool do_is_equal(const std::pmr::memory_resource &other) const noexcept override;
};

// The allocator keeps the resource alive through shared_ptr control-block destruction.
template <class T> struct CNavigationAllocator {
    using value_type = T;
    std::shared_ptr<CNavigationBudget> resource;
    explicit CNavigationAllocator(std::shared_ptr<CNavigationBudget> resource) : resource(std::move(resource)) {}
    template <class U> CNavigationAllocator(const CNavigationAllocator<U> &other) : resource(other.resource) {}
    T *allocate(std::size_t count) {
        if (count > std::numeric_limits<std::size_t>::max() / sizeof(T))
            throw std::bad_alloc();
        return static_cast<T *>(resource->allocate(count * sizeof(T), alignof(T)));
    }
    void deallocate(T *pointer, std::size_t count) { resource->deallocate(pointer, count * sizeof(T), alignof(T)); }
    template <class U> bool operator==(const CNavigationAllocator<U> &other) const {
        return resource == other.resource;
    }
};

struct CNavigationCell {
    bool walkable = false;
    int cost = 1;
};

struct CNavigationNeighbors {
    std::array<Coords, 4> cardinal{};
    std::size_t count = 0;
    std::span<const Coords> connectors;
};

class CNavigationSnapshot {
  public:
    CNavigationSnapshot(std::shared_ptr<CNavigationBudget> budget, std::shared_ptr<CMap> map,
                        std::weak_ptr<CNavigationService> service);
    ~CNavigationSnapshot();
    bool canStep(Coords coords) const;
    int movementCost(Coords coords) const;
    Coords normalize(Coords coords) const;
    CNavigationNeighbors neighbors(Coords coords, bool reverse = false) const;
    double heuristic(Coords from, Coords goal) const;
    bool isCurrent() const;
    bool isFinite() const;
    bool isFiniteFor(Coords start, Coords goal) const;
    bool persistentCacheable() const;
    std::uint64_t epoch() const;
    std::uintptr_t ownerIdentity() const;
    std::shared_ptr<CNavigationBudget> budget() const;
    std::optional<std::pmr::vector<Coords>> changesSince(std::uint64_t oldEpoch) const;
    std::size_t chunkCount() const;
    void clearChunks();
    void reuseChunks(const CNavigationSnapshot &old, std::span<const Coords> dirty);

  private:
    struct Data;
    std::unique_ptr<Data> data;
    CNavigationCell cell(Coords coords) const;
    std::int64_t walkingLowerBound(Coords from, Coords to) const;
};

class CNavigationService : public std::enable_shared_from_this<CNavigationService> {
  public:
    explicit CNavigationService(std::size_t limit = CNavigationBudget::DEFAULT_LIMIT);
    ~CNavigationService();
    static std::shared_ptr<CNavigationService> forMap(const std::shared_ptr<CMap> &map);
    std::shared_ptr<CNavigationBudget> budget() const;
    std::shared_ptr<CNavigationSnapshot> snapshot(const std::shared_ptr<CMap> &map);
    std::vector<Coords> findPath(const std::shared_ptr<CMap> &map, Coords start, Coords goal);
    CNavigationSearchResult findPathResult(const std::shared_ptr<CMap> &map, Coords start, Coords goal);
    std::size_t searchCount() const;
    CNavigationFlowStatistics flowStatistics() const;
    void trimCaches();
    void clearSessionCaches();
    CNavigationFlowResult nextStep(const std::shared_ptr<CMap> &map, const std::shared_ptr<CMapObject> &target,
                                   Coords start, Coords goal, std::int64_t turn);
    void recordChange(const std::shared_ptr<CMap> &map, std::uint64_t epoch, std::optional<Coords> coords);
    std::optional<std::pmr::vector<Coords>> changesSince(const std::shared_ptr<CMap> &map, std::uint64_t oldEpoch,
                                                         std::uint64_t newEpoch) const;
    static std::size_t flowCacheSize();
    static void clearFlows();

  private:
    struct Data;
    std::unique_ptr<Data> data;
};
