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
#include "core/CNavigation.h"
#include "core/CNavigationFlow.h"
#include "core/CNavigationSearch.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "handler/CObjectHandler.h"
#include "object/CTile.h"

#include <algorithm>
#include <cmath>

namespace {
constexpr std::int64_t NAVIGATION_INFINITE_COST = std::numeric_limits<std::int64_t>::max() / 4;
constexpr std::size_t JOURNAL_CAPACITY = 1024;
std::mutex navigationRegistryMutex;
std::vector<std::weak_ptr<CNavigationService>> navigationRegistry;

int chunkAxis(int value) {
    const auto wide = static_cast<std::int64_t>(value);
    return static_cast<int>(wide >= 0 ? wide / 32 : (wide - 31) / 32);
}
Coords chunkKey(Coords coords) { return Coords(chunkAxis(coords.x), chunkAxis(coords.y), coords.z); }

int wrapAxis(int value, int maximum, bool wrapped) {
    if (!wrapped || maximum < 0)
        return value;
    const auto size = static_cast<std::int64_t>(maximum) + 1;
    auto remainder = static_cast<std::int64_t>(value) % size;
    return static_cast<int>(remainder < 0 ? remainder + size : remainder);
}
} // namespace

CNavigationBudget::CNavigationBudget(std::size_t limit) : maximum(limit) {}
bool CNavigationBudget::tryReserve(std::size_t bytes) {
    auto current = allocated.load(std::memory_order_relaxed);
    do {
        if (bytes > maximum || current > maximum - bytes)
            return false;
    } while (!allocated.compare_exchange_weak(current, current + bytes, std::memory_order_acq_rel));
    auto observed = maximumAllocated.load(std::memory_order_relaxed);
    while (observed < current + bytes &&
           !maximumAllocated.compare_exchange_weak(observed, current + bytes, std::memory_order_relaxed)) {
    }
    return true;
}
void CNavigationBudget::release(std::size_t bytes) { allocated.fetch_sub(bytes, std::memory_order_acq_rel); }
std::size_t CNavigationBudget::used() const { return allocated.load(std::memory_order_relaxed); }
std::size_t CNavigationBudget::peak() const { return maximumAllocated.load(std::memory_order_relaxed); }
std::size_t CNavigationBudget::limit() const { return maximum; }
void *CNavigationBudget::do_allocate(std::size_t bytes, std::size_t alignment) {
    if (!tryReserve(bytes))
        throw std::bad_alloc();
    try {
        return std::pmr::new_delete_resource()->allocate(bytes, alignment);
    } catch (...) {
        release(bytes);
        throw;
    }
}
void CNavigationBudget::do_deallocate(void *pointer, std::size_t bytes, std::size_t alignment) {
    std::pmr::new_delete_resource()->deallocate(pointer, bytes, alignment);
    release(bytes);
}
bool CNavigationBudget::do_is_equal(const std::pmr::memory_resource &other) const noexcept { return this == &other; }

struct CNavigationSnapshot::Data {
    struct Level {
        int x = -1;
        int y = -1;
        bool wrapX = false;
        bool wrapY = false;
        std::optional<CNavigationCell> normal;
        std::optional<CNavigationCell> outside;
    };
    struct Chunk {
        std::array<CNavigationCell, 1024> cells;
    };
    std::shared_ptr<CNavigationBudget> budget;
    std::weak_ptr<CMap> map;
    std::weak_ptr<CNavigationService> service;
    std::uint64_t epoch = 0;
    bool finite = false;
    bool cacheable = true;
    std::pmr::map<int, Level> levels;
    std::pmr::unordered_map<Coords, std::pmr::vector<Coords>, CNavigationCoordsHash> outgoing;
    std::pmr::unordered_map<Coords, std::pmr::vector<Coords>, CNavigationCoordsHash> incoming;
    std::pmr::unordered_map<Coords, std::pmr::unordered_map<Coords, int, CNavigationCoordsHash>, CNavigationCoordsHash>
        connectorCosts;
    std::pmr::vector<Coords> endpoints;
    std::pmr::vector<std::int64_t> relaxed;
    mutable std::mutex chunksMutex;
    mutable std::pmr::unordered_map<Coords, std::shared_ptr<const Chunk>, CNavigationCoordsHash> chunks;
    mutable std::mutex heuristicMutex;
    mutable std::optional<Coords> heuristicGoal;
    mutable std::array<std::int64_t, 64> goalDistances{};
    Data(std::shared_ptr<CNavigationBudget> budget)
        : budget(std::move(budget)), levels(this->budget.get()), outgoing(this->budget.get()),
          incoming(this->budget.get()), connectorCosts(this->budget.get()), endpoints(this->budget.get()),
          relaxed(this->budget.get()), chunks(this->budget.get()) {}
};

CNavigationSnapshot::CNavigationSnapshot(std::shared_ptr<CNavigationBudget> budget, std::shared_ptr<CMap> map,
                                         std::weak_ptr<CNavigationService> service) {
    if (!budget->tryReserve(sizeof(Data)))
        throw std::bad_alloc();
    try {
        data = std::make_unique<Data>(budget);
        data->map = map;
        data->service = std::move(service);
        std::lock_guard mapLock(map->getNavigationMutex());
        data->epoch = map->getRoutingEpoch();
        data->finite = map->navigationDomainCanonical && !map->xBounds.empty();
        auto game = map->getGame();
        auto scalar = [&](const std::string &type) -> std::optional<CNavigationCell> {
            if (!game)
                return std::nullopt;
            if (auto value = game->getObjectHandler()->getStaticTileNavigation(type))
                return CNavigationCell{value->first, value->second};
            return std::nullopt;
        };
        for (const auto &[z, x] : map->xBounds) {
            Data::Level level;
            level.x = x;
            level.y = map->yBounds.contains(z) ? map->yBounds.at(z) : -1;
            level.wrapX = map->wrapsX(z);
            level.wrapY = map->wrapsY(z);
            const auto normal = map->defaultTiles.contains(z) && !map->defaultTiles.at(z).empty()
                                    ? map->defaultTiles.at(z)
                                    : "GrassTile";
            const auto outside = map->outOfBoundsTiles.contains(z) && !map->outOfBoundsTiles.at(z).empty()
                                     ? map->outOfBoundsTiles.at(z)
                                     : "MountainTile";
            level.normal = scalar(normal);
            level.outside = scalar(outside);
            if (!game) {
                level.normal = CNavigationCell{true, 1};
                level.outside = CNavigationCell{false, 1};
            }
            if (level.x < 0 || level.y < 0 || level.x > INT_MAX - 32 || level.y > INT_MAX - 32 || !level.outside ||
                level.outside->walkable)
                data->finite = false;
            if (!level.normal || !level.outside)
                data->cacheable = false;
            data->levels.emplace(z, level);
        }
        if (map->navigationTileExtentOverflow)
            data->finite = false;
        for (std::size_t i = 0; i < map->navigationTileExtentCount; ++i) {
            const auto &entry = map->navigationTileExtents[i];
            const auto &extent = entry.extent;
            auto level = data->levels.find(entry.level);
            if (level == data->levels.end() || extent[0] < 0 || extent[2] < 0 || extent[1] > level->second.x ||
                extent[3] > level->second.y)
                data->finite = false;
        }
        auto add = [&](auto &index, Coords from, Coords to) {
            const auto adjacent = neighbors(from);
            if (std::find(adjacent.cardinal.begin(), adjacent.cardinal.begin() + adjacent.count, to) !=
                adjacent.cardinal.begin() + adjacent.count)
                return;
            auto [it, inserted] = index.try_emplace(from);
            auto &destinations = it->second;
            if (std::ranges::find(destinations, to) == destinations.end())
                destinations.push_back(to);
        };
        auto recordCost = [&](Coords from, Coords to, int cost) {
            const auto adjacent = neighbors(from);
            if (std::find(adjacent.cardinal.begin(), adjacent.cardinal.begin() + adjacent.count, to) !=
                adjacent.cardinal.begin() + adjacent.count)
                return;
            auto [source, inserted] = data->connectorCosts.try_emplace(from);
            auto [destination, added] = source->second.try_emplace(to, std::max(1, cost));
            if (!added)
                destination->second = std::min(destination->second, std::max(1, cost));
        };
        for (const auto &edge : map->navigationEdges) {
            if (!edge.enabled)
                continue;
            auto source = normalize(edge.source);
            auto target = normalize(edge.target);
            if (edge.source == source) {
                add(data->outgoing, source, target);
                add(data->incoming, target, source);
                recordCost(source, target, edge.movementCost);
            }
            if (edge.bidirectional && edge.target == target) {
                add(data->outgoing, target, source);
                add(data->incoming, source, target);
                recordCost(target, source, edge.movementCost);
            }
            if (edge.source != source || edge.target != target)
                data->finite = false;
            for (auto endpoint : {source, target}) {
                auto level = data->levels.find(endpoint.z);
                if (level == data->levels.end() || endpoint.x < 0 || endpoint.y < 0 || endpoint.x > level->second.x ||
                    endpoint.y > level->second.y)
                    data->finite = false;
                if (std::ranges::find(data->endpoints, endpoint) == data->endpoints.end())
                    data->endpoints.push_back(endpoint);
            }
        }
        // Custom or unbounded fallback factories are consulted anew, never frozen into persistent chunks.
        if (!data->cacheable)
            data->finite = false;
        const auto count = data->endpoints.size();
        if (data->finite && count <= 64) {
            data->relaxed.resize(count * count, NAVIGATION_INFINITE_COST);
            for (std::size_t i = 0; i < count; ++i) {
                for (std::size_t j = 0; j < count; ++j)
                    data->relaxed[i * count + j] = walkingLowerBound(data->endpoints[i], data->endpoints[j]);
                auto edges = data->outgoing.find(data->endpoints[i]);
                if (edges != data->outgoing.end())
                    for (auto destination : edges->second) {
                        auto j = std::ranges::find(data->endpoints, destination) - data->endpoints.begin();
                        const auto fee = data->connectorCosts.at(data->endpoints[i]).at(destination);
                        data->relaxed[i * count + j] = std::min<std::int64_t>(data->relaxed[i * count + j], fee);
                    }
            }
            for (std::size_t k = 0; k < count; ++k)
                for (std::size_t i = 0; i < count; ++i)
                    for (std::size_t j = 0; j < count; ++j)
                        data->relaxed[i * count + j] = std::min(
                            data->relaxed[i * count + j], data->relaxed[i * count + k] + data->relaxed[k * count + j]);
        }
    } catch (...) {
        data.reset();
        budget->release(sizeof(Data));
        throw;
    }
}
CNavigationSnapshot::~CNavigationSnapshot() {
    auto resource = data->budget;
    data.reset();
    resource->release(sizeof(Data));
}
Coords CNavigationSnapshot::normalize(Coords coords) const {
    const auto level = data->levels.find(coords.z);
    if (level != data->levels.end()) {
        coords.x = wrapAxis(coords.x, level->second.x, level->second.wrapX);
        coords.y = wrapAxis(coords.y, level->second.y, level->second.wrapY);
    }
    return coords;
}
CNavigationCell CNavigationSnapshot::cell(Coords coords) const {
    coords = normalize(coords);
    auto map = data->map.lock();
    if (!map)
        return {};
    std::optional<CNavigationCell> fallback;
    auto level = data->levels.find(coords.z);
    if (level != data->levels.end()) {
        const auto &value = level->second;
        const bool outside =
            value.x >= 0 && value.y >= 0 && (coords.x < 0 || coords.y < 0 || coords.x > value.x || coords.y > value.y);
        fallback = outside ? value.outside : value.normal;
        if (outside && data->finite)
            return value.outside.value_or(CNavigationCell{});
    }
    if (!data->cacheable || level == data->levels.end()) {
        if (!isCurrent())
            return {};
        const auto result = map->lookupNavigationCell(coords, fallback);
        return isCurrent() ? result : CNavigationCell{};
    }
    std::lock_guard mapLock(map->getNavigationMutex());
    if (!isCurrent())
        return {};
    const auto key = chunkKey(coords);
    const auto index = (coords.y - key.y * 32) * 32 + coords.x - key.x * 32;
    {
        std::lock_guard chunkLock(data->chunksMutex);
        auto found = data->chunks.find(key);
        if (found != data->chunks.end())
            return found->second->cells[index];
    }
    auto chunk = std::allocate_shared<Data::Chunk>(CNavigationAllocator<Data::Chunk>(data->budget));
    for (int y = 0; y < 32; ++y)
        for (int x = 0; x < 32; ++x) {
            const Coords candidate(key.x * 32 + x, key.y * 32 + y, key.z);
            const auto &value = level->second;
            const bool outside = value.x >= 0 && value.y >= 0 &&
                                 (candidate.x < 0 || candidate.y < 0 || candidate.x > value.x || candidate.y > value.y);
            chunk->cells[y * 32 + x] = map->lookupNavigationCell(candidate, outside ? value.outside : value.normal);
        }
    if (!isCurrent())
        return {};
    std::lock_guard chunkLock(data->chunksMutex);
    auto found = data->chunks.emplace(key, std::move(chunk)).first;
    return found->second->cells[index];
}
bool CNavigationSnapshot::canStep(Coords coords) const { return cell(coords).walkable; }
int CNavigationSnapshot::movementCost(Coords coords) const { return cell(coords).cost; }
std::int64_t CNavigationSnapshot::stepCost(Coords from, Coords to) const {
    return stepCost(from, to, movementCost(to));
}
std::int64_t CNavigationSnapshot::stepCost(Coords from, Coords to, int terrainCost) const {
    from = normalize(from);
    to = normalize(to);
    terrainCost = std::max(1, terrainCost);
    const auto source = data->connectorCosts.find(from);
    if (source == data->connectorCosts.end())
        return terrainCost;
    const auto destination = source->second.find(to);
    if (destination == source->second.end())
        return terrainCost;
    return static_cast<std::int64_t>(terrainCost) + destination->second - 1;
}
CNavigationNeighbors CNavigationSnapshot::neighbors(Coords coords, bool reverse) const {
    coords = normalize(coords);
    CNavigationNeighbors result;
    for (auto delta : {EAST, WEST, SOUTH, NORTH}) {
        auto x = static_cast<std::int64_t>(coords.x) + delta.x;
        auto y = static_cast<std::int64_t>(coords.y) + delta.y;
        auto level = data->levels.find(coords.z);
        if (level != data->levels.end()) {
            const auto &value = level->second;
            if (value.wrapX && value.x >= 0) {
                const auto size = static_cast<std::int64_t>(value.x) + 1;
                x = (x % size + size) % size;
            }
            if (value.wrapY && value.y >= 0) {
                const auto size = static_cast<std::int64_t>(value.y) + 1;
                y = (y % size + size) % size;
            }
        }
        if (x < INT_MIN || x > INT_MAX || y < INT_MIN || y > INT_MAX)
            continue;
        auto next = normalize(Coords(static_cast<int>(x), static_cast<int>(y), coords.z));
        if (std::find(result.cardinal.begin(), result.cardinal.begin() + result.count, next) ==
            result.cardinal.begin() + result.count)
            result.cardinal[result.count++] = next;
    }
    const auto &index = reverse ? data->incoming : data->outgoing;
    auto found = index.find(coords);
    if (found != index.end())
        result.connectors = found->second;
    return result;
}
std::int64_t CNavigationSnapshot::walkingLowerBound(Coords from, Coords to) const {
    if (from.z != to.z)
        return NAVIGATION_INFINITE_COST;
    from = normalize(from);
    to = normalize(to);
    auto dx = std::abs(static_cast<std::int64_t>(from.x) - to.x);
    auto dy = std::abs(static_cast<std::int64_t>(from.y) - to.y);
    auto level = data->levels.find(from.z);
    if (level == data->levels.end())
        return NAVIGATION_INFINITE_COST;
    if (level->second.wrapX && level->second.x >= 0)
        dx = std::min(dx, static_cast<std::int64_t>(level->second.x) + 1 - dx);
    if (level->second.wrapY && level->second.y >= 0)
        dy = std::min(dy, static_cast<std::int64_t>(level->second.y) + 1 - dy);
    return dx + dy;
}
double CNavigationSnapshot::heuristic(Coords from, Coords goal) const {
    if (!data->finite || data->endpoints.size() > 64)
        return 0;
    auto best = walkingLowerBound(from, goal);
    const auto count = data->endpoints.size();
    if (count) {
        std::lock_guard lock(data->heuristicMutex);
        if (!data->heuristicGoal || *data->heuristicGoal != goal) {
            for (std::size_t i = 0; i < count; ++i) {
                auto distance = NAVIGATION_INFINITE_COST;
                for (std::size_t j = 0; j < count; ++j)
                    distance =
                        std::min(distance, data->relaxed[i * count + j] + walkingLowerBound(data->endpoints[j], goal));
                data->goalDistances[i] = distance;
            }
            data->heuristicGoal = goal;
        }
        for (std::size_t i = 0; i < count; ++i)
            best = std::min(best, walkingLowerBound(from, data->endpoints[i]) + data->goalDistances[i]);
    }
    return best >= NAVIGATION_INFINITE_COST ? 0 : static_cast<double>(best);
}
bool CNavigationSnapshot::isCurrent() const {
    auto map = data->map.lock();
    try {
        return map && map->getRoutingEpoch() == data->epoch;
    } catch (const std::exception &) {
        return false;
    }
}
bool CNavigationSnapshot::isFinite() const { return data->finite; }
bool CNavigationSnapshot::isFiniteFor(Coords start, Coords goal) const {
    return data->finite && data->levels.contains(start.z) && data->levels.contains(goal.z);
}
bool CNavigationSnapshot::persistentCacheable() const { return data->cacheable; }
std::uint64_t CNavigationSnapshot::epoch() const { return data->epoch; }
std::uintptr_t CNavigationSnapshot::ownerIdentity() const {
    return reinterpret_cast<std::uintptr_t>(data->map.lock().get());
}
std::shared_ptr<CNavigationBudget> CNavigationSnapshot::budget() const { return data->budget; }
std::optional<std::pmr::vector<Coords>> CNavigationSnapshot::changesSince(std::uint64_t oldEpoch) const {
    auto map = data->map.lock();
    auto service = data->service.lock();
    return map && service ? service->changesSince(map, oldEpoch, data->epoch) : std::nullopt;
}
std::size_t CNavigationSnapshot::chunkCount() const {
    std::lock_guard lock(data->chunksMutex);
    return data->chunks.size();
}
void CNavigationSnapshot::clearChunks() {
    std::lock_guard lock(data->chunksMutex);
    data->chunks.clear();
}
void CNavigationSnapshot::reuseChunks(const CNavigationSnapshot &old, std::span<const Coords> dirty) {
    if (!data->cacheable || !old.data->cacheable)
        return;
    std::scoped_lock lock(data->chunksMutex, old.data->chunksMutex);
    for (const auto &[key, chunk] : old.data->chunks) {
        if (std::ranges::none_of(dirty, [&](Coords coords) { return chunkKey(normalize(coords)) == key; }))
            data->chunks.emplace(key, chunk);
    }
}

struct CNavigationService::Data {
    struct Change {
        std::uint64_t epoch = 0;
        std::optional<Coords> coords;
    };
    struct MapState {
        std::weak_ptr<CMap> map;
        std::shared_ptr<CNavigationSnapshot> snapshot;
        std::array<Change, JOURNAL_CAPACITY> changes;
        std::size_t count = 0;
        std::size_t next = 0;
    };
    struct WorkspaceSlot {
        std::unique_ptr<CNavigationSearchWorkspace> workspace;
        bool inUse = false;
    };
    std::shared_ptr<CNavigationBudget> budget;
    CNavigationFlow flow;
    mutable std::recursive_mutex mutex;
    std::pmr::vector<std::shared_ptr<MapState>> maps;
    std::array<WorkspaceSlot, 4> workspaces;
    std::atomic_size_t searches{0};
    bool registered = false;
    Data(std::shared_ptr<CNavigationBudget> budget)
        : budget(std::move(budget)), flow(this->budget), maps(this->budget.get()) {}
};
CNavigationService::CNavigationService(std::size_t limit) {
    auto budget = std::make_shared<CNavigationBudget>(limit);
    if (!budget->tryReserve(sizeof(Data)))
        throw std::bad_alloc();
    try {
        data = std::make_unique<Data>(budget);
    } catch (...) {
        budget->release(sizeof(Data));
        throw;
    }
}
CNavigationService::~CNavigationService() {
    auto budget = data->budget;
    data.reset();
    budget->release(sizeof(Data));
}
std::shared_ptr<CNavigationService> CNavigationService::forMap(const std::shared_ptr<CMap> &map) {
    return map ? map->getNavigationService() : nullptr;
}
std::shared_ptr<CNavigationBudget> CNavigationService::budget() const { return data->budget; }
std::size_t CNavigationService::searchCount() const { return data->searches.load(std::memory_order_relaxed); }
CNavigationFlowStatistics CNavigationService::flowStatistics() const { return data->flow.statistics(); }
void CNavigationService::trimCaches() {
    while (data->flow.evictUnused()) {
    }
    std::lock_guard lock(data->mutex);
    for (auto &slot : data->workspaces)
        if (!slot.inUse)
            slot.workspace.reset();
    for (auto &state : data->maps)
        if (state->snapshot)
            state->snapshot->clearChunks();
}
void CNavigationService::clearSessionCaches() {
    data->flow.shutdown();
    trimCaches();
    std::lock_guard lock(data->mutex);
    data->maps.clear();
}
std::shared_ptr<CNavigationSnapshot> CNavigationService::snapshot(const std::shared_ptr<CMap> &map) {
    if (!map)
        return nullptr;
    auto active = [&] {
        auto game = map->getGame();
        return !game || game->getContext()->isActive();
    };
    if (!active())
        return nullptr;
    try {
        std::lock_guard mapLock(map->getNavigationMutex());
        const auto epoch = map->getRoutingEpoch();
        std::lock_guard lock(data->mutex);
        if (!data->registered) {
            std::lock_guard registryLock(navigationRegistryMutex);
            navigationRegistry.erase(std::remove_if(navigationRegistry.begin(), navigationRegistry.end(),
                                                    [](const auto &entry) { return entry.expired(); }),
                                     navigationRegistry.end());
            navigationRegistry.emplace_back(shared_from_this());
            data->registered = true;
        }
        std::erase_if(data->maps, [](const auto &state) { return state->map.expired(); });
        auto found = std::ranges::find_if(data->maps, [&](const auto &state) { return state->map.lock() == map; });
        if (found == data->maps.end()) {
            auto state = std::allocate_shared<Data::MapState>(CNavigationAllocator<Data::MapState>(data->budget));
            state->map = map;
            data->maps.push_back(state);
            found = data->maps.end() - 1;
        }
        auto &state = **found;
        if (state.snapshot && state.snapshot->epoch() == epoch)
            return state.snapshot;
        auto next = std::allocate_shared<CNavigationSnapshot>(CNavigationAllocator<CNavigationSnapshot>(data->budget),
                                                              data->budget, map, weak_from_this());
        if (state.snapshot) {
            if (auto changes = changesSince(map, state.snapshot->epoch(), epoch))
                next->reuseChunks(*state.snapshot, *changes);
        }
        state.snapshot = std::move(next);
        return state.snapshot;
    } catch (const std::exception &) {
        if (!active())
            return nullptr;
        throw;
    }
}

void CNavigationService::recordChange(const std::shared_ptr<CMap> &map, std::uint64_t epoch,
                                      std::optional<Coords> coords) {
    std::lock_guard lock(data->mutex);
    auto found = std::ranges::find_if(data->maps, [&](const auto &state) { return state->map.lock() == map; });
    if (found == data->maps.end())
        return;
    auto &state = **found;
    state.changes[state.next] = {epoch, coords};
    state.next = (state.next + 1) % JOURNAL_CAPACITY;
    state.count = std::min(state.count + 1, JOURNAL_CAPACITY);
}
std::optional<std::pmr::vector<Coords>> CNavigationService::changesSince(const std::shared_ptr<CMap> &map,
                                                                         std::uint64_t oldEpoch,
                                                                         std::uint64_t newEpoch) const {
    std::lock_guard lock(data->mutex);
    if (oldEpoch == newEpoch)
        return std::pmr::vector<Coords>(data->budget.get());
    auto found = std::ranges::find_if(data->maps, [&](const auto &state) { return state->map.lock() == map; });
    if (found == data->maps.end() || oldEpoch > newEpoch)
        return std::nullopt;
    const auto &state = **found;
    auto oldest = (state.next + JOURNAL_CAPACITY - state.count) % JOURNAL_CAPACITY;
    if (!state.count || state.changes[oldest].epoch > oldEpoch + 1)
        return std::nullopt;
    std::pmr::vector<Coords> result(data->budget.get());
    for (std::size_t i = 0; i < state.count; ++i) {
        const auto &change = state.changes[(oldest + i) % JOURNAL_CAPACITY];
        if (change.epoch <= oldEpoch || change.epoch > newEpoch)
            continue;
        if (!change.coords)
            return std::nullopt;
        if (std::ranges::find(result, *change.coords) == result.end())
            result.push_back(*change.coords);
    }
    return result;
}
CNavigationSearchResult CNavigationService::findPathResult(const std::shared_ptr<CMap> &map, Coords start,
                                                           Coords goal) {
    auto failure = [&](CNavigationSearchStatus status) {
        CNavigationSearchResult result(data->budget);
        result.status = status;
        result.firstStep = start;
        return result;
    };
    for (int attempt = 0; attempt < 2; ++attempt) {
        Data::WorkspaceSlot *slot = nullptr;
        try {
            auto graph = snapshot(map);
            if (!graph)
                return failure(map ? CNavigationSearchStatus::Cancelled : CNavigationSearchStatus::InvalidInput);
            {
                std::lock_guard lock(data->mutex);
                for (auto &candidate : data->workspaces)
                    if (!candidate.inUse) {
                        slot = &candidate;
                        slot->inUse = true;
                        break;
                    }
            }
            if (!slot)
                return failure(CNavigationSearchStatus::Deferred);
            struct Release {
                Data *data;
                Data::WorkspaceSlot *slot;
                ~Release() {
                    std::lock_guard lock(data->mutex);
                    slot->inUse = false;
                }
            } release{data.get(), slot};
            if (!slot->workspace)
                slot->workspace = std::make_unique<CNavigationSearchWorkspace>();
            data->searches.fetch_add(1, std::memory_order_relaxed);
            auto result = CNavigationSearch::findPath(graph, start, goal, slot->workspace.get());
            if (result.status == CNavigationSearchStatus::ResourceLimit && result.allocationDenied)
                throw std::bad_alloc();
            if (!graph->isCurrent())
                return failure(CNavigationSearchStatus::Cancelled);
            return result;
        } catch (const std::bad_alloc &) {
            if (attempt == 0)
                trimCaches();
        }
    }
    return failure(CNavigationSearchStatus::ResourceLimit);
}
std::vector<Coords> CNavigationService::findPath(const std::shared_ptr<CMap> &map, Coords start, Coords goal) {
    auto result = findPathResult(map, start, goal);
    if (result.status != CNavigationSearchStatus::Found)
        return {start};
    const auto bytes = result.path.size() * sizeof(Coords);
    if (!data->budget->tryReserve(bytes))
        return {start};
    struct CopyRelease {
        CNavigationBudget *budget;
        std::size_t bytes;
        ~CopyRelease() { budget->release(bytes); }
    } copyRelease{data->budget.get(), bytes};
    try {
        return {result.path.begin(), result.path.end()};
    } catch (const std::bad_alloc &) {
        return {start};
    }
}
CNavigationFlowResult CNavigationService::nextStep(const std::shared_ptr<CMap> &map,
                                                   const std::shared_ptr<CMapObject> &target, Coords start, Coords goal,
                                                   std::int64_t turn) {
    std::shared_ptr<CNavigationSnapshot> graph;
    for (int attempt = 0; attempt < 2; ++attempt) {
        try {
            graph = snapshot(map);
            break;
        } catch (const std::bad_alloc &) {
            if (attempt == 1)
                return {CNavigationFlowStatus::ResourceLimit, start, 0};
            trimCaches();
        }
    }
    return data->flow.nextStep(graph, map, target, start, goal, turn);
}
std::size_t CNavigationService::flowCacheSize() {
    std::lock_guard lock(navigationRegistryMutex);
    std::size_t count = 0;
    for (const auto &weak : navigationRegistry)
        if (auto service = weak.lock())
            count += service->data->flow.cacheSize();
    return count;
}
void CNavigationService::clearFlows() {
    std::lock_guard lock(navigationRegistryMutex);
    for (const auto &weak : navigationRegistry)
        if (auto service = weak.lock())
            service->data->flow.clear();
}
