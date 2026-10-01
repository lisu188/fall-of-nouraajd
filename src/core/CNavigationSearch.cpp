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
#include "core/CNavigationSearch.h"
#include "core/CNavigation.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <mutex>
#include <unordered_map>

namespace {
using Index = std::uint32_t;
using Cost = std::int64_t;
constexpr Index NO_INDEX = std::numeric_limits<Index>::max();
constexpr Cost SEARCH_INFINITE_COST = std::numeric_limits<Cost>::max();
constexpr int CHUNK_SIDE = 32;
constexpr Index CHUNK_CELLS = CHUNK_SIDE * CHUNK_SIDE;

struct SearchFailure {
    CNavigationSearchStatus status;
};

struct Node {
    Cost cost = SEARCH_INFINITE_COST;
    Cost priority = SEARCH_INFINITE_COST;
    Coords coords;
    Index parent = NO_INDEX;
    Index firstStep = NO_INDEX;
    Index heapPosition = NO_INDEX;
    Index order = 0;
    Index generation = 0;
    Index hops = 0;
    unsigned char passability = 0; // unknown, blocked, passable
};

Cost checkedAdd(Cost first, Cost second) {
    if (second < 0 || first > SEARCH_INFINITE_COST - 1 - second)
        throw SearchFailure{CNavigationSearchStatus::ResourceLimit};
    return first + second;
}

Cost heuristicCost(double value) {
    if (!std::isfinite(value) || value >= static_cast<double>(SEARCH_INFINITE_COST))
        throw SearchFailure{CNavigationSearchStatus::InvalidInput};
    return value <= 0 ? 0 : static_cast<Cost>(std::floor(value));
}

void checkRecordLimit(std::size_t count, const CNavigationSearchLimits &limits) {
    if (count >= limits.maxRecords || count >= NO_INDEX)
        throw SearchFailure{CNavigationSearchStatus::ResourceLimit};
}

class SparseRecords {
  public:
    explicit SparseRecords(std::pmr::memory_resource *resource) : indices(resource), nodes(resource) {}
    Node &at(Index index) { return nodes[index]; }
    Index get(Coords coords, CNavigationSearchResult &result, const CNavigationSearchLimits &limits) {
        const auto found = indices.find(coords);
        if (found != indices.end())
            return found->second;
        checkRecordLimit(result.statistics.records, limits);
        const auto index = static_cast<Index>(nodes.size());
        Node node;
        node.coords = coords;
        node.order = index;
        nodes.push_back(node);
        indices.emplace(coords, index);
        ++result.statistics.records;
        return index;
    }

  private:
    std::pmr::unordered_map<Coords, Index, CNavigationCoordsHash> indices;
    std::pmr::vector<Node> nodes;
};

class ChunkRecords {
    using Chunk = std::array<Node, CHUNK_CELLS>;

  public:
    explicit ChunkRecords(std::pmr::memory_resource *resource)
        : resource(resource), indices(resource), chunks(resource) {}
    ~ChunkRecords() {
        for (auto chunk : chunks) {
            std::destroy_at(chunk);
            resource->deallocate(chunk, sizeof(Chunk), alignof(Chunk));
        }
    }
    void begin() {
        if (++generation == 0) {
            for (auto chunk : chunks)
                for (auto &node : *chunk)
                    node.generation = 0;
            generation = 1;
        }
    }
    Node &at(Index index) { return (*chunks[index / CHUNK_CELLS])[index % CHUNK_CELLS]; }
    Index get(Coords coords, CNavigationSearchResult &result, const CNavigationSearchLimits &limits) {
        const auto chunkAxis = [](int value) {
            const auto wide = static_cast<std::int64_t>(value);
            return static_cast<int>(wide >= 0 ? wide / CHUNK_SIDE : (wide - CHUNK_SIDE + 1) / CHUNK_SIDE);
        };
        const Coords key(chunkAxis(coords.x), chunkAxis(coords.y), coords.z);
        auto found = indices.find(key);
        Index chunkIndex;
        if (found == indices.end()) {
            checkRecordLimit(result.statistics.records, limits);
            if (chunks.size() >= NO_INDEX / CHUNK_CELLS)
                throw SearchFailure{CNavigationSearchStatus::ResourceLimit};
            auto chunk = static_cast<Chunk *>(resource->allocate(sizeof(Chunk), alignof(Chunk)));
            std::construct_at(chunk);
            chunkIndex = static_cast<Index>(chunks.size());
            try {
                chunks.push_back(chunk);
                indices.emplace(key, chunkIndex);
            } catch (...) {
                if (chunks.size() > chunkIndex)
                    chunks.pop_back();
                std::destroy_at(chunk);
                resource->deallocate(chunk, sizeof(Chunk), alignof(Chunk));
                throw;
            }
            ++result.statistics.chunkAllocations;
        } else {
            chunkIndex = found->second;
        }
        const auto localX =
            static_cast<Index>(static_cast<std::int64_t>(coords.x) - static_cast<std::int64_t>(key.x) * CHUNK_SIDE);
        const auto localY =
            static_cast<Index>(static_cast<std::int64_t>(coords.y) - static_cast<std::int64_t>(key.y) * CHUNK_SIDE);
        const auto index = chunkIndex * CHUNK_CELLS + localY * CHUNK_SIDE + localX;
        auto &node = at(index);
        if (node.generation != generation) {
            checkRecordLimit(result.statistics.records, limits);
            node = Node{};
            node.coords = coords;
            node.generation = generation;
            node.order = static_cast<Index>(result.statistics.records++);
        }
        return index;
    }

  private:
    std::pmr::memory_resource *resource;
    std::pmr::unordered_map<Coords, Index, CNavigationCoordsHash> indices;
    std::pmr::vector<Chunk *> chunks;
    Index generation = 0;
};

template <typename Records> class IndexedHeap {
  public:
    IndexedHeap(Records &records, std::pmr::vector<Index> &entries, CNavigationSearchStatistics &statistics)
        : records(records), entries(entries), statistics(statistics) {
        entries.clear();
    }
    bool empty() const { return entries.empty(); }
    void update(Index index) {
        auto position = records.at(index).heapPosition;
        if (position == NO_INDEX) {
            position = static_cast<Index>(entries.size());
            entries.push_back(index);
            records.at(index).heapPosition = position;
            ++statistics.pushes;
            statistics.peakFrontier = std::max(statistics.peakFrontier, entries.size());
        } else {
            ++statistics.decreaseKeys;
        }
        while (position > 0) {
            const auto parent = (position - 1) / 4;
            if (!before(entries[position], entries[parent]))
                break;
            exchange(position, parent);
            position = parent;
        }
        sink(position);
    }
    Index pop() {
        const auto result = entries.front();
        exchange(0, static_cast<Index>(entries.size() - 1));
        entries.pop_back();
        records.at(result).heapPosition = NO_INDEX;
        ++statistics.pops;
        sink(0);
        return result;
    }

  private:
    void sink(Index position) {
        while (static_cast<std::size_t>(position) * 4 + 1 < entries.size()) {
            const auto firstChild = position * 4 + 1;
            auto best = firstChild;
            for (Index child = firstChild + 1; child < firstChild + 4 && child < entries.size(); ++child)
                if (before(entries[child], entries[best]))
                    best = child;
            if (!before(entries[best], entries[position]))
                break;
            exchange(position, best);
            position = best;
        }
    }
    bool before(Index first, Index second) {
        const auto &a = records.at(first);
        const auto &b = records.at(second);
        if (a.priority != b.priority)
            return a.priority < b.priority;
        if (a.cost != b.cost)
            return a.cost > b.cost;
        return a.order < b.order;
    }
    void exchange(Index first, Index second) {
        std::swap(entries[first], entries[second]);
        records.at(entries[first]).heapPosition = first;
        records.at(entries[second]).heapPosition = second;
    }
    Records &records;
    std::pmr::vector<Index> &entries;
    CNavigationSearchStatistics &statistics;
};

struct GenericGraph {
    const CPathFinder::CanStep &passable;
    const CPathFinder::Waypoint &waypoint;
    const CPathFinder::Neighbors &neighbors;
    const CPathFinder::Distance &distance;
    const CPathFinder::StepCost &stepCost;
    bool current() const { return true; }
    bool canStep(Coords coords) const { return passable(coords); }
    double heuristic(Coords from, Coords goal) const { return distance(from, goal); }
    int cost(Coords from, Coords to) const { return std::max(1, stepCost(from, to)); }
    template <typename Visitor> void visit(Coords coords, Visitor visitor) const {
        for (auto neighbor : neighbors(coords))
            visitor(neighbor);
        if (auto next = waypoint(coords))
            visitor(*next);
    }
};

struct MapGraph {
    const CNavigationSnapshot &snapshot;
    bool current() const { return snapshot.isCurrent(); }
    bool canStep(Coords coords) const { return snapshot.canStep(coords); }
    double heuristic(Coords from, Coords goal) const { return snapshot.heuristic(from, goal); }
    int cost(Coords, Coords to) const { return std::max(1, snapshot.movementCost(to)); }
    template <typename Visitor> void visit(Coords coords, Visitor visitor) const {
        const auto neighbors = snapshot.neighbors(coords);
        for (std::size_t i = 0; i < neighbors.count; ++i)
            visitor(neighbors.cardinal[i]);
        for (auto next : neighbors.connectors)
            visitor(next);
    }
};

template <typename Records, typename Graph>
void search(Records &records, std::pmr::vector<Index> &entries, const Graph &graph, Coords start, Coords goal,
            bool fullPath, CNavigationSearchLimits limits, CNavigationSearchResult &result) {
    result.firstStep = start;
    if (!graph.current())
        throw SearchFailure{CNavigationSearchStatus::Cancelled};
    if (start == goal) {
        if (fullPath)
            result.path.push_back(start);
        result.status = CNavigationSearchStatus::Found;
        return;
    }
    auto passable = [&](Index index) {
        auto &node = records.at(index);
        if (node.passability == 0) {
            ++result.statistics.passabilityCalls;
            node.passability = graph.canStep(node.coords) ? 2 : 1;
        }
        return node.passability == 2;
    };
    const auto goalIndex = records.get(goal, result, limits);
    if (!passable(goalIndex))
        return;
    const auto startIndex = records.get(start, result, limits);
    ++result.statistics.heuristicCalls;
    auto &initial = records.at(startIndex);
    initial.cost = 0;
    initial.priority = heuristicCost(graph.heuristic(start, goal));
    initial.firstStep = startIndex;
    IndexedHeap heap(records, entries, result.statistics);
    heap.update(startIndex);
    while (!heap.empty()) {
        if (!graph.current())
            throw SearchFailure{CNavigationSearchStatus::Cancelled};
        const auto currentIndex = heap.pop();
        // Copy before sparse storage grows during neighbor discovery.
        const auto current = records.at(currentIndex);
        if (currentIndex == goalIndex) {
            if (current.hops > limits.maxPathLength)
                throw SearchFailure{CNavigationSearchStatus::ResourceLimit};
            result.cost = current.cost;
            result.firstStep = records.at(current.firstStep).coords;
            if (fullPath) {
                auto index = currentIndex;
                while (index != startIndex) {
                    if (index == NO_INDEX || result.path.size() >= limits.maxPathLength)
                        throw SearchFailure{CNavigationSearchStatus::ResourceLimit};
                    result.path.push_back(records.at(index).coords);
                    index = records.at(index).parent;
                }
                std::reverse(result.path.begin(), result.path.end());
            }
            if (!graph.current())
                throw SearchFailure{CNavigationSearchStatus::Cancelled};
            result.status = CNavigationSearchStatus::Found;
            return;
        }
        if (result.statistics.expansions >= limits.maxExpansions)
            throw SearchFailure{CNavigationSearchStatus::ResourceLimit};
        ++result.statistics.expansions;
        ++result.statistics.neighborCalls;
        graph.visit(current.coords, [&](Coords next) {
            const auto nextIndex = records.get(next, result, limits);
            if (!passable(nextIndex))
                return;
            ++result.statistics.costCalls;
            const Cost nextCost = checkedAdd(current.cost, graph.cost(current.coords, next));
            auto &node = records.at(nextIndex);
            if (nextCost >= node.cost)
                return;
            ++result.statistics.heuristicCalls;
            const auto priority = checkedAdd(nextCost, heuristicCost(graph.heuristic(next, goal)));
            if (node.cost != SEARCH_INFINITE_COST && node.heapPosition == NO_INDEX)
                ++result.statistics.reopened;
            node.cost = nextCost;
            node.priority = priority;
            node.parent = currentIndex;
            node.firstStep = currentIndex == startIndex ? nextIndex : current.firstStep;
            if (current.hops == NO_INDEX)
                throw SearchFailure{CNavigationSearchStatus::ResourceLimit};
            node.hops = current.hops + 1;
            heap.update(nextIndex);
        });
    }
    if (!graph.current())
        throw SearchFailure{CNavigationSearchStatus::Cancelled};
}

template <typename Action> void runBounded(CNavigationSearchResult &result, Action action) {
    try {
        action();
    } catch (const SearchFailure &failure) {
        result.status = failure.status;
        result.path.clear();
        result.cost = 0;
    } catch (const std::bad_alloc &) {
        result.status = CNavigationSearchStatus::ResourceLimit;
        result.allocationDenied = true;
        result.path.clear();
        result.cost = 0;
    }
}

CNavigationSearchResult genericSearch(Coords start, Coords goal, const CPathFinder::CanStep &canStep,
                                      const CPathFinder::Waypoint &waypoint, const CPathFinder::Neighbors &neighbors,
                                      const CPathFinder::Distance &distance, const CPathFinder::StepCost &stepCost,
                                      std::shared_ptr<CNavigationBudget> budget, CNavigationSearchLimits limits,
                                      bool fullPath) {
    if (!budget)
        budget = CNavigationSearch::standaloneBudget();
    CNavigationSearchResult result(budget);
    result.firstStep = start;
    if (!canStep || !waypoint || !neighbors || !distance || !stepCost) {
        result.status = CNavigationSearchStatus::InvalidInput;
        return result;
    }
    runBounded(result, [&]() {
        SparseRecords records(budget.get());
        std::pmr::vector<Index> frontier(budget.get());
        const GenericGraph graph{canStep, waypoint, neighbors, distance, stepCost};
        search(records, frontier, graph, start, goal, fullPath, limits, result);
    });
    if (result.status != CNavigationSearchStatus::Found)
        result.firstStep = start;
    return result;
}
} // namespace

struct CNavigationSearchWorkspace::Impl {
    std::mutex mutex;
    std::shared_ptr<CNavigationBudget> budget;
    std::unique_ptr<ChunkRecords> records;
    std::unique_ptr<std::pmr::vector<Index>> frontier;
    std::uintptr_t owner = 0;
    bool metadataReserved = false;
    static constexpr std::size_t metadataBytes() {
        return sizeof(Impl) + sizeof(ChunkRecords) + sizeof(std::pmr::vector<Index>);
    }

    ~Impl() {
        frontier.reset();
        records.reset();
        if (metadataReserved)
            budget->release(metadataBytes());
    }

    void prepare(const std::shared_ptr<CNavigationSnapshot> &snapshot) {
        if (budget != snapshot->budget() || owner != snapshot->ownerIdentity()) {
            frontier.reset();
            records.reset();
            if (metadataReserved)
                budget->release(metadataBytes());
            metadataReserved = false;
            budget = snapshot->budget();
            owner = snapshot->ownerIdentity();
        }
        if (!metadataReserved) {
            if (!budget->tryReserve(metadataBytes()))
                throw std::bad_alloc();
            metadataReserved = true;
        }
        if (!records)
            records = std::make_unique<ChunkRecords>(budget.get());
        if (!frontier)
            frontier = std::make_unique<std::pmr::vector<Index>>(budget.get());
        records->begin();
    }
};

CNavigationSearchResult::CNavigationSearchResult(std::shared_ptr<CNavigationBudget> budget)
    : allocationBudget(std::move(budget)), path(allocationBudget.get()) {}

CNavigationSearchWorkspace::CNavigationSearchWorkspace() : impl(std::make_unique<Impl>()) {}
CNavigationSearchWorkspace::~CNavigationSearchWorkspace() = default;

std::shared_ptr<CNavigationBudget> CNavigationSearch::standaloneBudget() {
    static auto budget = std::make_shared<CNavigationBudget>();
    return budget;
}

namespace {
CNavigationSearchResult mapSearch(const std::shared_ptr<CNavigationSnapshot> &snapshot, Coords start, Coords goal,
                                  CNavigationSearchWorkspace::Impl &workspace, CNavigationSearchLimits limits,
                                  bool fullPath) {
    CNavigationSearchResult result(snapshot ? snapshot->budget() : CNavigationSearch::standaloneBudget());
    result.firstStep = start;
    if (!snapshot) {
        result.status = CNavigationSearchStatus::InvalidInput;
        return result;
    }
    std::unique_lock lock(workspace.mutex, std::try_to_lock);
    if (!lock.owns_lock()) {
        result.status = CNavigationSearchStatus::Deferred;
        return result;
    }
    start = snapshot->normalize(start);
    goal = snapshot->normalize(goal);
    result.firstStep = start;
    try {
        runBounded(result, [&]() {
            const MapGraph graph{*snapshot};
            if (snapshot->isFiniteFor(start, goal)) {
                workspace.prepare(snapshot);
                search(*workspace.records, *workspace.frontier, graph, start, goal, fullPath, limits, result);
            } else {
                SparseRecords records(snapshot->budget().get());
                std::pmr::vector<Index> frontier(snapshot->budget().get());
                search(records, frontier, graph, start, goal, fullPath, limits, result);
            }
        });
    } catch (const std::exception &) {
        if (snapshot->isCurrent())
            throw;
        result.status = CNavigationSearchStatus::Cancelled;
        result.path.clear();
        result.cost = 0;
    }
    if (result.status != CNavigationSearchStatus::Found)
        result.firstStep = start;
    return result;
}
} // namespace

CNavigationSearchResult CNavigationSearch::findPath(const std::shared_ptr<CNavigationSnapshot> &snapshot, Coords start,
                                                    Coords goal, CNavigationSearchWorkspace *workspace,
                                                    CNavigationSearchLimits limits) {
    if (workspace)
        return mapSearch(snapshot, start, goal, *workspace->impl, limits, true);
    CNavigationSearchWorkspace temporary;
    return mapSearch(snapshot, start, goal, *temporary.impl, limits, true);
}

CNavigationSearchResult CNavigationSearch::findNextStep(const std::shared_ptr<CNavigationSnapshot> &snapshot,
                                                        Coords start, Coords goal,
                                                        CNavigationSearchWorkspace *workspace,
                                                        CNavigationSearchLimits limits) {
    if (workspace)
        return mapSearch(snapshot, start, goal, *workspace->impl, limits, false);
    CNavigationSearchWorkspace temporary;
    return mapSearch(snapshot, start, goal, *temporary.impl, limits, false);
}

CNavigationSearchResult
CNavigationSearch::findGenericPath(Coords start, Coords goal, const CPathFinder::CanStep &canStep,
                                   const CPathFinder::Waypoint &waypoint, const CPathFinder::Neighbors &neighbors,
                                   const CPathFinder::Distance &distance, const CPathFinder::StepCost &stepCost,
                                   std::shared_ptr<CNavigationBudget> budget, CNavigationSearchLimits limits) {
    return genericSearch(start, goal, canStep, waypoint, neighbors, distance, stepCost, std::move(budget), limits,
                         true);
}

CNavigationSearchResult
CNavigationSearch::findGenericNextStep(Coords start, Coords goal, const CPathFinder::CanStep &canStep,
                                       const CPathFinder::Waypoint &waypoint, const CPathFinder::Neighbors &neighbors,
                                       const CPathFinder::Distance &distance, const CPathFinder::StepCost &stepCost,
                                       std::shared_ptr<CNavigationBudget> budget, CNavigationSearchLimits limits) {
    return genericSearch(start, goal, canStep, waypoint, neighbors, distance, stepCost, std::move(budget), limits,
                         false);
}
