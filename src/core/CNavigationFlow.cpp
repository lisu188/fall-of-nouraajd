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
#include "core/CNavigationFlow.h"
#include "core/CNavigation.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <limits>
#include <memory_resource>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <vector>

namespace {
constexpr std::size_t MAX_FIELDS = 32;
constexpr std::size_t MAX_CELLS = 1'000'000;
constexpr std::size_t MAX_WORK_PER_START = 25'000;
constexpr std::uint32_t MAX_ROUTE_LENGTH = 100'000;
constexpr std::size_t NOT_QUEUED = std::numeric_limits<std::size_t>::max();
constexpr std::int64_t FLOW_INFINITE_COST = std::numeric_limits<std::int64_t>::max() / 4;

struct CellLimit {};
struct FlowStopped {};

struct Distance {
    std::int64_t cost = FLOW_INFINITE_COST;
    std::uint32_t hops = std::numeric_limits<std::uint32_t>::max();

    auto operator<=>(const Distance &) const = default;

    Distance preceding(std::int64_t movementCost) const {
        if (cost == FLOW_INFINITE_COST || cost > FLOW_INFINITE_COST - std::max<std::int64_t>(1, movementCost)) {
            return {};
        }
        return {cost + std::max<std::int64_t>(1, movementCost), hops + 1};
    }
};

struct FlowNode {
    Distance g;
    Distance rhs;
    Coords next;
    std::size_t heapIndex = NOT_QUEUED;
};

struct Counters {
    std::atomic<std::uint64_t> fieldsCreated = 0;
    std::atomic<std::uint64_t> fieldRebuilds = 0;
    std::atomic<std::uint64_t> incrementalRepairs = 0;
    std::atomic<std::uint64_t> expandedNodes = 0;
    std::atomic<std::uint64_t> cacheHits = 0;
    std::atomic<std::uint64_t> deferredRequests = 0;
    std::atomic<std::uint64_t> resourceLimits = 0;
};

template <typename Callback>
void forEachNeighbor(const CNavigationSnapshot &snapshot, Coords coords, bool reverse, Callback &&callback) {
    const auto neighbors = snapshot.neighbors(coords, reverse);
    for (std::size_t i = 0; i < neighbors.count; ++i) {
        if (neighbors.cardinal[i] != coords) {
            callback(neighbors.cardinal[i]);
        }
    }
    for (auto neighbor : neighbors.connectors) {
        if (neighbor != coords) {
            callback(neighbor);
        }
    }
}

struct FlowField {
    std::weak_ptr<CMap> map;
    std::weak_ptr<CMapObject> target;
    std::uint64_t lastUse = 0;
    std::mutex mutex;
    std::shared_ptr<CNavigationSnapshot> snapshot;
    Coords goal;
    bool initialized = false;
    std::pmr::unordered_map<Coords, FlowNode, CNavigationCoordsHash> nodes;
    std::pmr::vector<Coords> heap;

    explicit FlowField(std::pmr::memory_resource *resource) : nodes(resource), heap(resource) {}

    bool expired() const { return map.expired() || target.expired(); }

    void resetSearch() noexcept {
        // Allocation failure can interrupt propagation. Discard the entire search,
        // while the session ledger retains work already spent on this request.
        // clear() cannot allocate, unlike constructing an empty MSVC unordered_map.
        nodes.clear();
        heap.clear();
        snapshot.reset();
        initialized = false;
    }

    FlowNode &nodeAt(Coords coords) {
        auto found = nodes.find(coords);
        if (found != nodes.end()) {
            return found->second;
        }
        if (nodes.size() >= MAX_CELLS) {
            throw CellLimit{};
        }
        return nodes.try_emplace(coords).first->second;
    }

    Distance key(Coords coords) const {
        const auto &node = nodes.at(coords);
        return std::min(node.g, node.rhs);
    }

    bool before(Coords left, Coords right) const {
        const auto leftKey = key(left);
        const auto rightKey = key(right);
        return leftKey < rightKey || (leftKey == rightKey && left < right);
    }

    void swapHeap(std::size_t left, std::size_t right) {
        std::swap(heap[left], heap[right]);
        nodes.at(heap[left]).heapIndex = left;
        nodes.at(heap[right]).heapIndex = right;
    }

    void fixHeap(std::size_t index) {
        while (index > 0 && before(heap[index], heap[(index - 1) / 2])) {
            const auto parent = (index - 1) / 2;
            swapHeap(index, parent);
            index = parent;
        }
        while (index * 2 + 1 < heap.size()) {
            auto child = index * 2 + 1;
            if (child + 1 < heap.size() && before(heap[child + 1], heap[child])) {
                ++child;
            }
            if (!before(heap[child], heap[index])) {
                break;
            }
            swapHeap(index, child);
            index = child;
        }
    }

    void removeQueued(Coords coords) {
        auto &node = nodes.at(coords);
        const auto index = node.heapIndex;
        if (index == NOT_QUEUED) {
            return;
        }
        swapHeap(index, heap.size() - 1);
        heap.pop_back();
        node.heapIndex = NOT_QUEUED;
        if (index < heap.size()) {
            fixHeap(index);
        }
    }

    void refreshQueue(Coords coords) {
        auto &node = nodes.at(coords);
        if (node.g == node.rhs) {
            removeQueued(coords);
        } else if (node.heapIndex == NOT_QUEUED) {
            heap.push_back(coords);
            node.heapIndex = heap.size() - 1;
            fixHeap(node.heapIndex);
        } else {
            fixHeap(node.heapIndex);
        }
    }

    void updateVertex(Coords coords) {
        const bool passable = snapshot->canStep(coords);
        if (!passable && !nodes.contains(coords)) {
            return;
        }
        auto &node = nodeAt(coords);
        node.rhs = {};
        node.next = coords;
        if (passable && coords == goal) {
            // The fixed virtual source has g=0 and one zero-cost arc to goal.
            node.rhs = {0, 0};
        } else if (passable) {
            forEachNeighbor(*snapshot, coords, false, [&](Coords successor) {
                auto found = nodes.find(successor);
                if (found == nodes.end() || !snapshot->canStep(successor)) {
                    return;
                }
                const auto candidate = found->second.g.preceding(snapshot->stepCost(coords, successor));
                if (candidate < node.rhs) {
                    node.rhs = candidate;
                    node.next = successor;
                }
            });
        }
        refreshQueue(coords);
    }

    void updatePredecessors(Coords coords) {
        forEachNeighbor(*snapshot, coords, true, [&](Coords predecessor) { updateVertex(predecessor); });
    }

    void synchronize(const std::shared_ptr<CNavigationSnapshot> &current, Coords newGoal, Counters &counters) {
        if (!initialized) {
            snapshot = current;
            goal = newGoal;
            initialized = true;
            ++counters.fieldRebuilds;
            updateVertex(goal);
            return;
        }
        const auto oldGoal = goal;
        const auto oldEpoch = snapshot->epoch();
        if (oldEpoch != current->epoch()) {
            auto changes = current->changesSince(oldEpoch);
            if (!changes || changes->size() > MAX_WORK_PER_START) {
                resetSearch();
                synchronize(current, newGoal, counters);
                return;
            }
            snapshot = current;
            goal = newGoal;
            ++counters.incrementalRepairs;
            for (auto changed : *changes) {
                changed = current->normalize(changed);
                updateVertex(changed);
                // Costs belong to the destination of each original edge.
                updatePredecessors(changed);
            }
        } else {
            snapshot = current;
            goal = newGoal;
        }
        if (oldGoal != goal) {
            ++counters.incrementalRepairs;
            updateVertex(oldGoal);
            updateVertex(goal);
        }
    }

    CNavigationFlowResult solve(const std::shared_ptr<CNavigationSnapshot> &current, Coords start, Coords newGoal,
                                std::size_t allowance, std::size_t &work, Counters &counters) {
        if (!current->isCurrent()) {
            return {CNavigationFlowStatus::Cancelled, start, 0};
        }
        if (!current->persistentCacheable()) {
            resetSearch();
        }
        synchronize(current, newGoal, counters);
        auto &startNode = nodeAt(start);
        while (!heap.empty() && (key(heap.front()) < key(start) || startNode.g != startNode.rhs)) {
            if (work >= allowance) {
                if (!current->isCurrent()) {
                    resetSearch();
                    return {CNavigationFlowStatus::Cancelled, start, 0};
                }
                ++counters.deferredRequests;
                return {CNavigationFlowStatus::Deferred, start, 0};
            }
            if ((work % 256 == 0) && !current->isCurrent()) {
                resetSearch();
                return {CNavigationFlowStatus::Cancelled, start, 0};
            }
            ++work;
            ++counters.expandedNodes;
            const auto coords = heap.front();
            removeQueued(coords);
            auto &node = nodes.at(coords);
            if (node.g > node.rhs) {
                node.g = node.rhs;
                updatePredecessors(coords);
            } else {
                node.g = {};
                updateVertex(coords);
                updatePredecessors(coords);
            }
        }
        if (!current->isCurrent()) {
            resetSearch();
            return {CNavigationFlowStatus::Cancelled, start, 0};
        }
        if (startNode.g != startNode.rhs) {
            // A consistent queue cannot be empty while its start is inconsistent.
            // Never turn an unfinished state into a movement command.
            ++counters.deferredRequests;
            return {CNavigationFlowStatus::Deferred, start, 0};
        }
        if (startNode.g.cost == FLOW_INFINITE_COST) {
            return {CNavigationFlowStatus::Unreachable, start, 0};
        }
        if (startNode.g.hops > MAX_ROUTE_LENGTH) {
            ++counters.resourceLimits;
            return {CNavigationFlowStatus::ResourceLimit, start, 0};
        }
        return {CNavigationFlowStatus::Complete, startNode.next, startNode.g.cost};
    }
};
} // namespace

struct CNavigationFlow::Impl {
    struct WorkKey {
        const CMapObject *target = nullptr;
        Coords start;
        bool operator==(const WorkKey &) const = default;
    };
    struct WorkHash {
        std::size_t operator()(const WorkKey &key) const noexcept {
            return CNavigationCoordsHash{}(key.start) ^ (std::hash<const CMapObject *>{}(key.target) << 1);
        }
    };
    struct WorkCounter {
        std::weak_ptr<CMapObject> target;
        std::size_t charged = 0;
        explicit WorkCounter(const std::shared_ptr<CMapObject> &target) : target(target) {}
    };
    struct MapWork {
        std::weak_ptr<CMap> map;
        std::int64_t turn;
        std::pmr::unordered_map<WorkKey, std::shared_ptr<WorkCounter>, WorkHash> starts;
        MapWork(std::pmr::memory_resource *resource, const std::shared_ptr<CMap> &map, std::int64_t turn)
            : map(map), turn(turn), starts(resource) {}
    };
    struct WorkTicket {
        Impl *owner;
        std::shared_ptr<WorkCounter> counter;
        std::size_t allowance;
        std::size_t consumed = 0;
        WorkTicket(Impl *owner, std::shared_ptr<WorkCounter> counter, std::size_t allowance)
            : owner(owner), counter(std::move(counter)), allowance(allowance) {}
        WorkTicket(const WorkTicket &) = delete;
        WorkTicket &operator=(const WorkTicket &) = delete;
        ~WorkTicket() {
            std::lock_guard lock(owner->ledgerMutex);
            counter->charged -= allowance - consumed;
        }
    };

    explicit Impl(std::shared_ptr<CNavigationBudget> resource)
        : budget(std::move(resource)), workLedger(std::in_place, budget.get()) {}

    std::shared_ptr<CNavigationBudget> budget;
    mutable std::mutex mutex;
    std::mutex ledgerMutex;
    std::array<std::shared_ptr<FlowField>, MAX_FIELDS> fields;
    std::optional<std::pmr::unordered_map<const CMap *, MapWork>> workLedger;
    std::atomic_bool stopped = false;
    std::size_t ledgerEntries = 0;
    std::uint64_t clock = 0;
    Counters counters;

    WorkTicket grantWork(const std::shared_ptr<CMap> &map, const std::shared_ptr<CMapObject> &target, Coords start,
                         std::int64_t turn) {
        std::lock_guard lock(ledgerMutex);
        if (stopped.load(std::memory_order_acquire))
            throw FlowStopped{};
        auto &ledger = *workLedger;
        auto found = ledger.find(map.get());
        if (found != ledger.end() && (found->second.map.lock() != map || found->second.turn != turn)) {
            ledgerEntries -= found->second.starts.size();
            ledger.erase(found);
            found = ledger.end();
        }
        if (found == ledger.end()) {
            for (auto it = ledger.begin(); it != ledger.end();) {
                if (it->second.map.expired()) {
                    ledgerEntries -= it->second.starts.size();
                    it = ledger.erase(it);
                } else {
                    ++it;
                }
            }
            found = ledger.try_emplace(map.get(), budget.get(), map, turn).first;
        }
        auto &starts = found->second.starts;
        const WorkKey key{target.get(), start};
        auto entry = starts.find(key);
        if (entry != starts.end() && entry->second->target.lock() != target) {
            starts.erase(entry);
            --ledgerEntries;
            entry = starts.end();
        }
        if (entry == starts.end()) {
            if (ledgerEntries >= MAX_CELLS) {
                throw CellLimit{};
            }
            auto counter = std::allocate_shared<WorkCounter>(CNavigationAllocator<WorkCounter>(budget), target);
            entry = starts.emplace(key, std::move(counter)).first;
            ++ledgerEntries;
        }
        auto counter = entry->second;
        const auto allowance = MAX_WORK_PER_START - counter->charged;
        // Reserve before releasing the short ledger lock. Even cache clearing
        // during an active request cannot grant another field the same work.
        counter->charged += allowance;
        return WorkTicket(this, std::move(counter), allowance);
    }

    std::shared_ptr<FlowField> findField(const std::shared_ptr<CMap> &map, const std::shared_ptr<CMapObject> &target) {
        std::lock_guard lock(mutex);
        if (stopped.load(std::memory_order_acquire))
            return {};
        std::shared_ptr<FlowField> *slot = nullptr;
        for (auto &field : fields) {
            if (field && field->expired()) {
                field.reset();
            }
            if (field && field->map.lock() == map && field->target.lock() == target) {
                field->lastUse = ++clock;
                ++counters.cacheHits;
                return field;
            }
            if (!field) {
                slot = &field;
            }
        }
        if (!slot) {
            for (auto &field : fields) {
                if (field.use_count() == 1 && (!slot || field->lastUse < (*slot)->lastUse)) {
                    slot = &field;
                }
            }
        }
        if (!slot) {
            return {};
        }
        slot->reset();
        auto field = std::allocate_shared<FlowField>(CNavigationAllocator<FlowField>(budget), budget.get());
        field->map = map;
        field->target = target;
        field->lastUse = ++clock;
        *slot = field;
        ++counters.fieldsCreated;
        return field;
    }

    void evictUnpinned(const FlowField *keep = nullptr) {
        std::lock_guard lock(mutex);
        for (auto &field : fields) {
            if (field && field.get() != keep && field.use_count() == 1) {
                field.reset();
            }
        }
    }

    bool evictOldestUnused() {
        std::lock_guard lock(mutex);
        std::shared_ptr<FlowField> *oldest = nullptr;
        for (auto &field : fields) {
            if (field && field.use_count() == 1 && (!oldest || field->lastUse < (*oldest)->lastUse)) {
                oldest = &field;
            }
        }
        if (!oldest) {
            return false;
        }
        oldest->reset();
        return true;
    }
};

CNavigationFlow::CNavigationFlow(std::shared_ptr<CNavigationBudget> budget) : allocationBudget(std::move(budget)) {
    impl = std::allocate_shared<Impl>(CNavigationAllocator<Impl>(allocationBudget), allocationBudget);
}

CNavigationFlow::~CNavigationFlow() = default;

CNavigationFlowResult CNavigationFlow::nextStep(const std::shared_ptr<CNavigationSnapshot> &snapshot,
                                                const std::shared_ptr<CMap> &map,
                                                const std::shared_ptr<CMapObject> &target, Coords start, Coords goal,
                                                std::int64_t turn) {
    if (impl->stopped.load(std::memory_order_acquire) || !snapshot || !map || !target ||
        snapshot->budget() != allocationBudget ||
        snapshot->ownerIdentity() != reinterpret_cast<std::uintptr_t>(map.get()) || !snapshot->isCurrent()) {
        return {CNavigationFlowStatus::Cancelled, start, 0};
    }
    start = snapshot->normalize(start);
    goal = snapshot->normalize(goal);
    if (start == goal) {
        return {CNavigationFlowStatus::Complete, start, 0};
    }
    try {
        if (!snapshot->canStep(start) || !snapshot->canStep(goal)) {
            return {snapshot->isCurrent() && !impl->stopped.load(std::memory_order_acquire)
                        ? CNavigationFlowStatus::Unreachable
                        : CNavigationFlowStatus::Cancelled,
                    start, 0};
        }
    } catch (const std::bad_alloc &) {
        if (impl->stopped.load(std::memory_order_acquire) || !snapshot->isCurrent())
            return {CNavigationFlowStatus::Cancelled, start, 0};
        impl->evictUnpinned();
        ++impl->counters.resourceLimits;
        return {CNavigationFlowStatus::ResourceLimit, start, 0};
    } catch (const std::exception &) {
        if (impl->stopped.load(std::memory_order_acquire) || !snapshot->isCurrent())
            return {CNavigationFlowStatus::Cancelled, start, 0};
        throw;
    }

    std::shared_ptr<FlowField> field;
    try {
        field = impl->findField(map, target);
    } catch (const std::bad_alloc &) {
        if (impl->stopped.load(std::memory_order_acquire) || !snapshot->isCurrent())
            return {CNavigationFlowStatus::Cancelled, start, 0};
        impl->evictUnpinned();
        ++impl->counters.resourceLimits;
        return {CNavigationFlowStatus::ResourceLimit, start, 0};
    }
    if (!field) {
        if (impl->stopped.load(std::memory_order_acquire))
            return {CNavigationFlowStatus::Cancelled, start, 0};
        ++impl->counters.deferredRequests;
        return {CNavigationFlowStatus::Deferred, start, 0};
    }
    std::lock_guard lock(field->mutex);
    try {
        auto work = impl->grantWork(map, target, start, turn);
        auto result = field->solve(snapshot, start, goal, work.allowance, work.consumed, impl->counters);
        if (impl->stopped.load(std::memory_order_acquire))
            return {CNavigationFlowStatus::Cancelled, start, 0};
        return result;
    } catch (const std::bad_alloc &) {
        field->resetSearch();
        if (impl->stopped.load(std::memory_order_acquire) || !snapshot->isCurrent())
            return {CNavigationFlowStatus::Cancelled, start, 0};
        impl->evictUnpinned(field.get());
    } catch (const CellLimit &) {
        field->resetSearch();
    } catch (const FlowStopped &) {
        return {CNavigationFlowStatus::Cancelled, start, 0};
    } catch (const std::exception &) {
        if (impl->stopped.load(std::memory_order_acquire) || !snapshot->isCurrent()) {
            field->resetSearch();
            return {CNavigationFlowStatus::Cancelled, start, 0};
        }
        throw;
    }
    ++impl->counters.resourceLimits;
    return {CNavigationFlowStatus::ResourceLimit, start, 0};
}

void CNavigationFlow::clear() {
    std::lock_guard lock(impl->mutex);
    for (auto &field : impl->fields) {
        field.reset();
    }
}

void CNavigationFlow::shutdown() {
    impl->stopped.store(true, std::memory_order_release);
    clear();
    std::lock_guard lock(impl->ledgerMutex);
    impl->workLedger.reset();
    impl->ledgerEntries = 0;
}

bool CNavigationFlow::evictUnused() { return impl->evictOldestUnused(); }

std::size_t CNavigationFlow::cacheSize() const {
    std::lock_guard lock(impl->mutex);
    return static_cast<std::size_t>(std::count_if(impl->fields.begin(), impl->fields.end(),
                                                  [](const auto &field) { return field && !field->expired(); }));
}

CNavigationFlowStatistics CNavigationFlow::statistics() const {
    const auto &counters = impl->counters;
    return {counters.fieldsCreated.load(), counters.fieldRebuilds.load(), counters.incrementalRepairs.load(),
            counters.expandedNodes.load(), counters.cacheHits.load(),     counters.deferredRequests.load(),
            counters.resourceLimits.load()};
}
