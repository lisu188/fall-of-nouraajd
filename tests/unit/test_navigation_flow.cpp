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
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CNavigationFlow.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CMapObject.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <future>
#include <limits>
#include <map>
#include <queue>
#include <thread>
#include <vector>

namespace {
constexpr auto NO_ROUTE = std::numeric_limits<std::int64_t>::max();

struct Fixture {
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CMapObject> target = std::make_shared<CMapObject>();
    std::shared_ptr<CNavigationService> service;
    std::unique_ptr<CNavigationFlow> flow;

    Fixture(int width, int height, Coords goal) {
        // A map without a game has the engine's finite, unit-cost fallback terrain.
        // This also exercises sparse snapshots without constructing thousands of tiles.
        map->setXBounds({{0, width - 1}});
        map->setYBounds({{0, height - 1}});
        target->setName("flowGoal");
        target->setCoords(goal);
        map->addObject(target);
        service = map->getNavigationService();
        flow = std::make_unique<CNavigationFlow>(service->budget());
    }

    CNavigationFlowResult step(Coords start, std::int64_t turn = 0) {
        return flow->nextStep(service->snapshot(map), map, target, start, target->getCoords(), turn);
    }

    std::shared_ptr<CTile> tile(Coords coords, int cost = 1, bool walkable = true) {
        auto tile = std::make_shared<CTile>();
        tile->setCanStep(walkable);
        tile->setMovementCost(cost);
        map->addTile(tile, coords.x, coords.y, coords.z);
        return tile;
    }
};

struct DynamicFixture : Fixture {
    struct Terrain {
        int cost = 1;
        bool walkable = true;
        std::atomic_size_t calls = 0;
        std::function<void()> onRead;
    };

    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<Terrain> terrain = std::make_shared<Terrain>();

    DynamicFixture(int width, int height, Coords goal) : Fixture(width, height, goal) {
        game->setMap(map);
        map->setGame(game);
        auto handler = game->getObjectHandler();
        handler->registerType("mutableFlowFloor", [terrain = terrain]() {
            ++terrain->calls;
            auto on_read = terrain->onRead;
            if (on_read)
                on_read();
            auto tile = std::make_shared<CTile>();
            tile->setCanStep(terrain->walkable);
            tile->setMovementCost(terrain->cost);
            return tile;
        });
        handler->registerConfig("mutableFlowFloor", std::make_shared<json>(json{{"class", "mutableFlowFloor"}}));
        map->setDefaultTiles({{0, "mutableFlowFloor"}});
        service = map->getNavigationService();
        flow = std::make_unique<CNavigationFlow>(service->budget());
    }

    ~DynamicFixture() { game->getContext()->shutdown(); }
};

class NavigationHookProbe : public CMapObject, public CMoveable {
  public:
    void onCreate(std::shared_ptr<CGameEvent>) override { queryNavigation(true); }
    void onDestroy(std::shared_ptr<CGameEvent>) override { queryNavigation(false); }
    void beforeMove() override { queryNavigation(true); }
    void afterMove() override { queryNavigation(true); }

    void finishQueries() {
        for (auto &query : queries) {
            query.worker.join();
            expect_true(query.completedInsideHook,
                        "a gameplay hook must allow worker navigation to finish before the hook returns");
            try {
                expect_true(query.result.get(), "hook navigation must observe committed object and coordinate indexes");
            } catch (...) {
                expect_true(false, "hook navigation query must not throw");
            }
        }
        queries.clear();
    }

    std::size_t pendingQueries() const { return queries.size(); }

  private:
    struct Query {
        std::future<bool> result;
        std::thread worker;
        bool completedInsideHook;
    };
    std::vector<Query> queries;

    void queryNavigation(bool registered) {
        auto map = getMap();
        auto self = ptr<CMapObject>();
        const auto coords = getCoords();
        std::packaged_task<bool()> work([map, self, coords, registered]() {
            if (!map) {
                return false;
            }
            const auto by_name = map->getObjectByName(self->getName()) == self;
            const auto at_coords = map->getObjectsAtCoords(coords).contains(self);
            auto path = map->getNavigationService()->findPath(map, ZERO, Coords(7, 1, 0));
            return by_name == registered && at_coords == registered && !path.empty() && path.back() == Coords(7, 1, 0);
        });
        auto result = work.get_future();
        std::thread worker(std::move(work));
        const bool completed = result.wait_for(std::chrono::seconds(2)) == std::future_status::ready;
        // Join only after the outer engine operation returns. The unfixed lock
        // scope times out here, then releases its lock instead of hanging the test.
        queries.push_back({std::move(result), std::move(worker), completed});
    }
};

void testGameplayHooksAllowReentrantWorkerNavigation() {
    Fixture fixture(8, 3, Coords(7, 1, 0));
    auto probe = std::make_shared<NavigationHookProbe>();
    probe->setName("navigationHookProbe");
    probe->setCoords(Coords(2, 1, 0));
    fixture.map->addObject(probe);
    expect_true(probe->pendingQueries() == 1, "adding the probe must exercise onCreate navigation");
    probe->finishQueries();
    probe->moveTo(Coords(3, 1, 0));
    expect_true(probe->pendingQueries() == 2, "movement must exercise both beforeMove and afterMove navigation");
    probe->finishQueries();
    probe->relocateWithoutMoveHooks(Coords(4, 1, 0));
    expect_true(probe->pendingQueries() == 0 && fixture.map->getObjectsAtCoords(Coords(4, 1, 0)).contains(probe),
                "hook-free relocation must update the coordinate index without invoking hooks");
    fixture.map->removeObject(probe);
    expect_true(probe->pendingQueries() == 1, "removal must exercise onDestroy navigation");
    probe->finishQueries();
    expect_true(!probe->getMap(), "normal removal must clear map ownership after onDestroy returns");
    fixture.map->addObject(probe, Coords(5, 1, 0));
    expect_true(probe->pendingQueries() == 3,
                "adding at coordinates must allow navigation in onCreate and both movement hooks");
    probe->finishQueries();
    expect_true(fixture.map->getObjectsAtCoords(Coords(5, 1, 0)).contains(probe),
                "adding at coordinates must commit the final spatial index");
    fixture.map->removeObject(probe);
    probe->finishQueries();
}

void testNativeMovementWaitsForPythonBeforeLockingTheMap() {
    class WorkerMover : public CMapObject, public CMoveable {
      public:
        void beforeMove() override {}
        void afterMove() override {}
    };
    Fixture fixture(8, 3, Coords(7, 1, 0));
    auto game = std::make_shared<CGame>();
    game->setMap(fixture.map);
    fixture.map->setGame(game);
    game->getObjectHandler()->registerType("workerFloor", []() {
        auto tile = std::make_shared<CTile>();
        tile->setCanStep(true);
        return tile;
    });
    fixture.map->setDefaultTiles({{0, "workerFloor"}});
    auto mover = std::make_shared<WorkerMover>();
    mover->setName("workerMover");
    mover->setCoords(Coords(2, 1, 0));
    fixture.map->addObject(mover);
    auto added = std::make_shared<CMapObject>();
    added->setName("workerAddedObject");
    std::atomic_size_t started = 0;
    std::vector<std::future<void>> results;
    std::vector<std::thread> workers;
    auto launch = [&](auto action) {
        std::packaged_task<void()> work([&started, action]() {
            started.fetch_add(1, std::memory_order_release);
            action();
        });
        results.push_back(work.get_future());
        workers.emplace_back(std::move(work));
    };
    launch([mover]() { mover->moveTo(Coords(3, 1, 0)); });
    launch([&fixture, added]() { fixture.map->addObject(added); });
    launch([&fixture]() { fixture.map->removeObject(fixture.target); });
    while (started.load(std::memory_order_acquire) != workers.size())
        std::this_thread::yield();

    // Keep the interpreter's GIL while workers reach a Python-capable entry point.
    // Probe with try_lock so the old inverse ordering fails instead of deadlocking.
    bool map_remained_available = true;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (std::chrono::steady_clock::now() < deadline) {
        std::unique_lock lock(fixture.map->getNavigationMutex(), std::try_to_lock);
        if (!lock.owns_lock()) {
            map_remained_available = false;
            break;
        }
        lock.unlock();
        std::this_thread::yield();
    }
    {
        pybind11::gil_scoped_release release;
        for (auto &worker : workers)
            worker.join();
    }
    for (auto &result : results) {
        try {
            result.get();
        } catch (...) {
            expect_true(false, "native movement and lifecycle workers must not throw");
        }
    }
    expect_true(map_remained_available, "a worker awaiting Python must not retain the map navigation mutex");
    expect_true(mover->getCoords() == Coords(3, 1, 0) && fixture.map->getObjectByName(added->getName()) == added &&
                    !fixture.map->getObjectByName(fixture.target->getName()),
                "native movement and lifecycle workers must complete after the GIL is released");
}

std::int64_t authoredStepCost(const std::shared_ptr<CMap> &map, Coords from, Coords to) {
    from = map->normalizeCoords(from);
    to = map->normalizeCoords(to);
    const std::int64_t terrain = map->lookupMovementCost(to);
    const auto adjacent = map->getAdjacentCoords(from);
    if (std::ranges::find(adjacent, to) != adjacent.end())
        return terrain;
    auto best = NO_ROUTE;
    for (const auto &edge : map->getNavigationEdges()) {
        if (!edge.enabled)
            continue;
        const auto source = map->normalizeCoords(edge.source);
        const auto target = map->normalizeCoords(edge.target);
        if ((source == from && target == to) || (edge.bidirectional && target == from && source == to))
            best = std::min(best, terrain + std::max(1, edge.movementCost) - 1);
    }
    return best;
}

std::int64_t oracle(const std::shared_ptr<CMap> &map, Coords start, Coords goal) {
    using Entry = std::pair<std::int64_t, Coords>;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
    std::map<Coords, std::int64_t> distance;
    start = map->normalizeCoords(start);
    goal = map->normalizeCoords(goal);
    if (!map->canStep(start) || !map->canStep(goal)) {
        return NO_ROUTE;
    }
    distance[start] = 0;
    queue.emplace(0, start);
    while (!queue.empty()) {
        const auto [cost, coords] = queue.top();
        queue.pop();
        if (distance.at(coords) != cost) {
            continue;
        }
        if (coords == goal) {
            return cost;
        }
        for (auto next : map->getNavigationNeighbors(coords)) {
            if (!map->canStep(next)) {
                continue;
            }
            const auto step_cost = authoredStepCost(map, coords, next);
            if (step_cost == NO_ROUTE || cost > NO_ROUTE - step_cost)
                continue;
            const auto candidate = cost + step_cost;
            auto found = distance.find(next);
            if (found == distance.end() || candidate < found->second) {
                distance[next] = candidate;
                queue.emplace(candidate, next);
            }
        }
    }
    return NO_ROUTE;
}

void expectExact(Fixture &fixture, Coords start, std::int64_t turn = 0) {
    const auto expected = oracle(fixture.map, start, fixture.target->getCoords());
    const auto result = fixture.step(start, turn);
    if (expected == NO_ROUTE) {
        expect_true(result.status == CNavigationFlowStatus::Unreachable,
                    "exhausted finite flow must agree with independent Dijkstra on unreachability");
        expect_true(result.step == start, "unreachable result must not propose a movement");
        return;
    }
    expect_true(result.status == CNavigationFlowStatus::Complete, "small finite flow must settle the requested start");
    expect_true(result.cost == expected, "repaired flow cost must equal independent Dijkstra");
    if (start == fixture.target->getCoords()) {
        expect_true(result.step == start, "arrival must preserve the current coordinate");
        return;
    }
    const auto neighbors = fixture.map->getNavigationNeighbors(start);
    expect_true(std::ranges::find(neighbors, result.step) != neighbors.end(), "flow step must use a legal graph edge");
    const auto remaining = oracle(fixture.map, result.step, fixture.target->getCoords());
    const auto first_cost = authoredStepCost(fixture.map, start, result.step);
    expect_true(remaining != NO_ROUTE && first_cost != NO_ROUTE && remaining <= NO_ROUTE - first_cost &&
                    first_cost + remaining == expected,
                "flow first step must belong to a minimum-cost route");
}

void testWarmFieldsSurviveCommittedSteppableMoves() {
    Fixture fixture(24, 3, Coords(23, 1, 0));
    auto actor = std::make_shared<CMapObject>();
    actor->setName("movingSteppableActor");
    actor->setCoords(Coords(0, 1, 0));
    fixture.map->addObject(actor);
    auto result = fixture.step(actor->getCoords());
    expect_true(result.status == CNavigationFlowStatus::Complete, "cold pursuit must find the corridor route");
    const auto warmed = fixture.flow->statistics();
    const auto public_revision = fixture.map->getNavigationRevision();
    for (int turn = 1; turn <= 6; ++turn) {
        actor->moveTo(result.step);
        fixture.map->setTurn(turn);
        result = fixture.step(actor->getCoords(), turn);
        expect_true(result.status == CNavigationFlowStatus::Complete, "warm pursuit must progress on later turns");
    }
    const auto later = fixture.flow->statistics();
    expect_true(fixture.map->getNavigationRevision() == public_revision + 6,
                "public movement revision must retain one notification per committed move");
    expect_true(later.fieldRebuilds == warmed.fieldRebuilds, "steppable moves must not rebuild a warmed field");
    expect_true(later.expandedNodes == warmed.expandedNodes, "settled warm starts must require zero extra expansions");
    expect_true(fixture.flow->cacheSize() == 1, "later turns must retain one target field");
    std::cout << "Flow steady turns: expansions=" << later.expandedNodes - warmed.expandedNodes << "/0\n";
}

void testMovingGoalAndDirectTerrainChangesRepairTheField() {
    Fixture fixture(8, 4, Coords(7, 1, 0));
    auto changed = fixture.tile(Coords(1, 1, 0));
    const Coords start(0, 1, 0);
    expectExact(fixture, start);
    const auto initial = fixture.flow->statistics();
    fixture.target->moveTo(Coords(7, 3, 0));
    expectExact(fixture, start, 1);
    fixture.target->moveTo(Coords(6, 1, 0));
    expectExact(fixture, start, 2);
    changed->setMovementCost(30);
    expectExact(fixture, start, 3);
    expect_true(fixture.step(start, 3).step != Coords(1, 1, 0),
                "increased destination cost must change the first step");
    changed->setMovementCost(1);
    expectExact(fixture, start, 4);
    changed->setCanStep(false);
    expectExact(fixture, start, 5);
    changed->setCanStep(true);
    expectExact(fixture, start, 6);
    const auto repaired = fixture.flow->statistics();
    expect_true(repaired.fieldRebuilds == initial.fieldRebuilds, "cell edits and goal motion must repair, not rebuild");
    expect_true(repaired.incrementalRepairs >= initial.incrementalRepairs + 6,
                "every goal and direct terrain mutation must reach incremental repair");
}

void testBlockingObjectsAndBlockedGoalsInvalidateTheirCells() {
    Fixture fixture(7, 3, Coords(6, 1, 0));
    const Coords start(0, 1, 0);
    auto blocker = std::make_shared<CMapObject>();
    blocker->setName("flowBlocker");
    blocker->setCoords(Coords(1, 0, 0));
    blocker->setCanStep(false);
    fixture.map->addObject(blocker);
    expectExact(fixture, start);
    blocker->moveTo(Coords(1, 1, 0));
    expectExact(fixture, start, 1);
    expect_true(fixture.step(start, 1).step != blocker->getCoords(), "moved blocker must not remain in the route");
    blocker->setCanStep(true);
    expectExact(fixture, start, 2);
    fixture.target->setCanStep(false);
    expectExact(fixture, start, 3);
    fixture.target->setCanStep(true);
    expectExact(fixture, start, 4);
}

void testDirectedConnectorCostsAndTopologyRebuilds() {
    Fixture fixture(5, 2, Coords(4, 0, 1));
    fixture.map->setXBounds({{0, 4}, {1, 4}});
    fixture.map->setYBounds({{0, 1}, {1, 1}});
    auto arrival = fixture.tile(Coords(1, 0, 1));
    CNavigationEdge edge;
    edge.source = Coords(1, 0, 0);
    edge.target = Coords(1, 0, 1);
    edge.movementCost = 999;
    fixture.map->registerNavigationEdge(edge);
    const Coords start(0, 0, 0);
    expectExact(fixture, start);
    expect_true(fixture.step(start).cost == 1003, "directed flow must include the authored connector fee");
    arrival->setMovementCost(17);
    expectExact(fixture, start, 1);
    expect_true(fixture.step(start, 1).cost == 1019,
                "destination-cost repair must preserve the incoming directed connector fee");
    const auto before_remove = fixture.flow->statistics();
    fixture.map->removeNavigationEdge(edge.source, edge.target);
    expectExact(fixture, start, 2);
    expect_true(fixture.flow->statistics().fieldRebuilds == before_remove.fieldRebuilds + 1,
                "connector removal must rebuild the retained target field");
    expect_true(fixture.flow->cacheSize() == 1, "topology rebuild must not retain an obsolete field generation");
}

void testSeededRepairsMatchDijkstraOnWrappedWeightedTerrain() {
    Fixture fixture(8, 6, Coords(7, 5, 0));
    fixture.map->setWrapX({{0, 1}});
    std::vector<std::shared_ptr<CTile>> tiles;
    for (int y = 0; y < 6; ++y) {
        for (int x = 0; x < 8; ++x) {
            tiles.push_back(fixture.tile(Coords(x, y, 0), 1 + (x * 3 + y * 5) % 9));
        }
    }
    std::uint32_t seed = 0x31415926;
    auto next = [&]() { return seed = seed * 1664525U + 1013904223U; };
    for (int turn = 0; turn < 64; ++turn) {
        const auto index = next() % tiles.size();
        tiles[index]->setMovementCost(1 + static_cast<int>(next() % 30));
        tiles[index]->setCanStep(next() % 5 != 0);
        fixture.target->moveTo(Coords(static_cast<int>(next() % 8), static_cast<int>(next() % 6), 0));
        const Coords start(static_cast<int>(next() % 8), static_cast<int>(next() % 6), 0);
        if (start != fixture.target->getCoords()) {
            expectExact(fixture, start, turn);
        }
    }
}

void testWorkLimitDefersAndResumesWithoutProvisionalSteps() {
    Fixture fixture(30'001, 1, Coords(30'000, 0, 0));
    const Coords start(0, 0, 0);
    const auto first = fixture.step(start, 10);
    expect_true(first.status == CNavigationFlowStatus::Deferred && first.step == start,
                "25k work exhaustion must defer without returning a tentative next step");
    const auto bounded = fixture.flow->statistics();
    expect_true(bounded.expandedNodes == 25'000, "first distinct start request must stop at exactly 25k expansions");
    const auto repeated = fixture.step(start, 10);
    expect_true(repeated.status == CNavigationFlowStatus::Deferred, "same-turn repeated start must remain deferred");
    expect_true(fixture.flow->statistics().expandedNodes == bounded.expandedNodes,
                "same-turn repeated start must not receive a second work allowance");
    const auto resumed = fixture.step(start, 11);
    expect_true(resumed.status == CNavigationFlowStatus::Complete && resumed.step == Coords(1, 0, 0),
                "next turn must resume the existing frontier and obtain the exact step");
    expect_true(resumed.cost == 30'000, "resumed pursuit must retain the exact corridor cost");
    expect_true(fixture.flow->statistics().fieldRebuilds == 1, "deferred continuation must not restart the search");
    std::cout << "Flow deferred work: first=" << bounded.expandedNodes
              << "/25000 total=" << fixture.flow->statistics().expandedNodes << "/30001\n";
}

void testEvictionCannotRenewSameTurnWork() {
    Fixture fixture(30'001, 1, Coords(30'000, 0, 0));
    const Coords start(0, 0, 0);
    expect_true(fixture.step(start, 20).status == CNavigationFlowStatus::Deferred,
                "eviction fixture must exhaust the first turn's work allowance");
    const auto before = fixture.flow->statistics().expandedNodes;
    expect_true(fixture.flow->evictUnused(), "deferred field must be available for LRU eviction");
    expect_true(fixture.step(start, 20).status == CNavigationFlowStatus::Deferred,
                "evicting a field must not grant a fresh same-turn allowance");
    expect_true(fixture.flow->statistics().expandedNodes == before,
                "session work accounting must survive destruction of the field");
    expect_true(fixture.step(start, 21).status == CNavigationFlowStatus::Deferred,
                "the next turn must begin a fresh bounded search after eviction");
    expect_true(fixture.flow->statistics().expandedNodes == before + 25'000,
                "a new turn must replenish exactly one 25k allowance");
    expect_true(fixture.step(start, 22).status == CNavigationFlowStatus::Complete,
                "the retained frontier must finish after the following allowance");
}

void testMissingJournalHistoryRebuildsWithoutKeepingOldSteps() {
    Fixture fixture(6, 2, Coords(5, 0, 0));
    auto changed = fixture.tile(Coords(1, 0, 0));
    expectExact(fixture, ZERO);
    const auto old = fixture.service->snapshot(fixture.map);
    const auto before = fixture.flow->statistics();
    // Exceed the bounded 1024-entry journal without querying the field.
    for (int i = 0; i < 1'100; ++i) {
        changed->setMovementCost(2 + i % 2);
    }
    changed->setCanStep(false);
    const auto current = fixture.service->snapshot(fixture.map);
    expect_true(!current->changesSince(old->epoch()), "fixture must discard changes older than journal capacity");
    expectExact(fixture, ZERO, 1);
    expect_true(fixture.flow->statistics().fieldRebuilds == before.fieldRebuilds + 1,
                "missing journal history must rebuild before returning another exact step");
}

void testRouteLengthLimitIsNotReportedAsUnreachable() {
    Fixture fixture(100'002, 1, Coords(100'001, 0, 0));
    CNavigationFlowResult result;
    for (int turn = 0; turn < 5; ++turn) {
        result = fixture.step(ZERO, turn);
        if (turn < 4) {
            expect_true(result.status == CNavigationFlowStatus::Deferred,
                        "long exact route must preserve bounded resumable work");
        }
    }
    expect_true(result.status == CNavigationFlowStatus::ResourceLimit && result.step == ZERO,
                "a minimum route beyond 100k steps must report the route limit, not unreachability");
    expect_true(fixture.service->budget()->peak() <= fixture.service->budget()->limit(),
                "long pursuit continuation must remain inside the session memory cap");
}

void testEntryLimitEvictsLeastRecentlyUsedTargetIdentity() {
    Fixture fixture(5, 1, Coords(4, 0, 0));
    const auto snapshot = fixture.service->snapshot(fixture.map);
    std::vector<std::shared_ptr<CMapObject>> targets;
    for (int i = 0; i < 40; ++i) {
        auto target = std::make_shared<CMapObject>();
        target->setCoords(Coords(4, 0, 0));
        targets.push_back(target);
        const auto result = fixture.flow->nextStep(snapshot, fixture.map, target, ZERO, target->getCoords(), 0);
        expect_true(result.status == CNavigationFlowStatus::Complete,
                    "each distinct target must receive an exact route");
        expect_true(fixture.flow->cacheSize() <= 32, "session pursuit cache must never exceed 32 fields");
    }
    const auto before = fixture.flow->statistics().fieldsCreated;
    fixture.flow->nextStep(snapshot, fixture.map, targets.back(), ZERO, targets.back()->getCoords(), 1);
    expect_true(fixture.flow->statistics().fieldsCreated == before, "recent target should remain cached");
    fixture.flow->nextStep(snapshot, fixture.map, targets.front(), ZERO, targets.front()->getCoords(), 1);
    expect_true(fixture.flow->statistics().fieldsCreated == before + 1, "oldest target should have been evicted");
    expect_true(fixture.flow->evictUnused() && fixture.flow->cacheSize() == 31,
                "memory-pressure eviction must release one unpinned LRU field");
    fixture.flow->clear();
    expect_true(fixture.flow->cacheSize() == 0, "explicit clear must remove every retained field");
    expect_true(!fixture.flow->evictUnused(), "empty field cache must report that no further eviction is possible");
}

void testSessionMemoryPressureIsExplicitAndRecoverable() {
    Fixture fixture(32, 32, Coords(31, 31, 0));
    auto snapshot = fixture.service->snapshot(fixture.map);
    auto budget = fixture.service->budget();
    expect_true(budget->limit() == 128 * 1024 * 1024, "default session navigation budget must be 128 MiB");
    const auto reserved = budget->limit() - budget->used();
    expect_true(budget->tryReserve(reserved), "test must reserve the remaining shared session budget");
    const auto result =
        fixture.flow->nextStep(snapshot, fixture.map, fixture.target, ZERO, fixture.target->getCoords(), 0);
    expect_true(result.status == CNavigationFlowStatus::ResourceLimit && result.step == ZERO,
                "full session budget must report resource pressure rather than an unreachable route");
    expect_true(budget->used() <= budget->limit() && budget->peak() <= budget->limit(),
                "pursuit allocation must never exceed the session byte ceiling");
    budget->release(reserved);
    // Populate scalar chunks, then leave enough room to begin a field but not
    // enough to settle this grid. A failed propagation must be discarded safely.
    expect_true(snapshot->canStep(ZERO), "pressure fixture start must be passable");
    const auto partial_reservation = budget->limit() - budget->used() - 32 * 1024;
    expect_true(budget->tryReserve(partial_reservation), "test must reserve partial-search memory pressure");
    const auto partial =
        fixture.flow->nextStep(snapshot, fixture.map, fixture.target, ZERO, fixture.target->getCoords(), 0);
    expect_true(partial.status == CNavigationFlowStatus::ResourceLimit && partial.step == ZERO,
                "mid-repair allocation failure must never expose a partial movement result");
    expect_true(fixture.flow->statistics().expandedNodes > 0,
                "memory-pressure fixture must interrupt real repair work");
    budget->release(partial_reservation);
    const auto recovered = fixture.step(ZERO, 1);
    expect_true(recovered.status == CNavigationFlowStatus::Complete && recovered.cost == 62,
                "pursuit must make progress once memory pressure is released");
}

void testShutdownClearsOnlyTheOwningGamesNavigationCaches() {
    auto make_session = []() {
        auto game = std::make_shared<CGame>();
        auto map = std::make_shared<CMap>();
        game->setMap(map);
        map->setGame(game);
        map->setXBounds({{0, 7}});
        map->setYBounds({{0, 0}});
        for (int x = 0; x < 8; ++x) {
            auto tile = std::make_shared<CTile>();
            tile->setCanStep(true);
            tile->setMovementCost(1);
            map->addTile(tile, x, 0, 0);
        }
        auto target = std::make_shared<CMapObject>();
        target->setName("sessionGoal");
        target->setCoords(Coords(7, 0, 0));
        map->addObject(target);
        return game;
    };
    const auto cached_before = CNavigationService::flowCacheSize();
    auto first_game = make_session();
    auto second_game = make_session();
    auto first_map = first_game->getMap();
    auto second_map = second_game->getMap();
    auto first_target = first_map->getObjectByName("sessionGoal");
    auto second_target = second_map->getObjectByName("sessionGoal");
    auto first_service = first_map->getNavigationService();
    auto second_service = second_map->getNavigationService();
    expect_true(first_service != second_service, "independent games must own independent navigation services");
    const auto first = first_service->nextStep(first_map, first_target, ZERO, first_target->getCoords(), 0);
    const auto second = second_service->nextStep(second_map, second_target, ZERO, second_target->getCoords(), 0);
    expect_true(first.status == CNavigationFlowStatus::Complete && second.status == CNavigationFlowStatus::Complete &&
                    first.step == Coords(1, 0, 0) && second.step == Coords(1, 0, 0) && first.cost == 7 &&
                    second.cost == 7,
                "both active games must populate an exact pursuit field");
    expect_true(CNavigationService::flowCacheSize() == cached_before + 2,
                "both active game services must retain their own pursuit field");
    const auto warm = second_service->flowStatistics();
    first_game->getContext()->shutdown();
    expect_true(!first_game->getContext()->isActive() && second_game->getContext()->isActive(),
                "explicit shutdown must leave the independently owned game active");
    expect_true(CNavigationService::flowCacheSize() == cached_before + 1,
                "shutdown must clear only its own field even while callers retain its service and map");
    const auto continued =
        second_service->nextStep(second_map, second_target, Coords(1, 0, 0), second_target->getCoords(), 1);
    const auto reused = second_service->flowStatistics();
    expect_true(continued.status == CNavigationFlowStatus::Complete && continued.step == Coords(2, 0, 0) &&
                    continued.cost == 6,
                "the surviving game must continue along its exact minimum-cost route");
    expect_true(reused.fieldsCreated == warm.fieldsCreated && reused.fieldRebuilds == warm.fieldRebuilds &&
                    reused.expandedNodes == warm.expandedNodes && reused.cacheHits == warm.cacheHits + 1,
                "another game's shutdown must preserve the warm field without rebuilding or expanding it");
    expect_true(CNavigationService::flowCacheSize() == cached_before + 1,
                "the surviving game must reuse its single cached pursuit field");
}

void testTerminalShutdownReleasesTheLedgerWithLiveOwners() {
    Fixture fixture(8, 1, Coords(7, 0, 0));
    auto snapshot = fixture.service->snapshot(fixture.map);
    expect_true(snapshot->canStep(ZERO), "ledger fixture must populate its shared scalar chunk first");
    const auto baseline = fixture.service->budget()->used();
    std::vector<std::shared_ptr<CMapObject>> targets;
    for (int i = 0; i < 128; ++i) {
        auto target = std::make_shared<CMapObject>();
        target->setCoords(Coords(7, 0, 0));
        targets.push_back(target);
        const auto result = fixture.flow->nextStep(snapshot, fixture.map, target, ZERO, target->getCoords(), 0);
        expect_true(result.status == CNavigationFlowStatus::Complete, "ledger fixture must charge distinct requests");
    }
    fixture.flow->clear();
    expect_true(fixture.service->budget()->used() > baseline,
                "ordinary cache clear must retain the same-turn work ledger");
    fixture.flow->shutdown();
    expect_true(fixture.service->budget()->used() <= baseline,
                "terminal shutdown must release ledger nodes and buckets while service and map owners remain alive");
    const auto stopped = fixture.flow->nextStep(snapshot, fixture.map, targets.front(), ZERO, Coords(7, 0, 0), 1);
    expect_true(stopped.status == CNavigationFlowStatus::Cancelled && fixture.flow->cacheSize() == 0,
                "a terminally stopped flow must not recreate fields or its work ledger");
}

void testInFlightShutdownCancelsControllerAndDirectFlow() {
    for (int mode = 0; mode < 3; ++mode) {
        auto game = std::make_shared<CGame>();
        auto map = std::make_shared<CMap>();
        game->setMap(map);
        map->setGame(game);
        map->setXBounds({{0, 7}});
        map->setYBounds({{0, 0}});
        struct FactoryGate {
            std::promise<void> entered;
            std::promise<void> resume;
            std::shared_future<void> resumed = resume.get_future().share();
            int calls = 0;
        };
        auto gate = std::make_shared<FactoryGate>();
        auto entered = gate->entered.get_future();
        const int blocking_call = mode == 2 ? 3 : 1;
        game->getObjectHandler()->registerType("shutdownFloor", [gate, blocking_call]() {
            if (++gate->calls == blocking_call) {
                gate->entered.set_value();
                pybind11::gil_scoped_release release;
                gate->resumed.wait();
            }
            auto tile = std::make_shared<CTile>();
            tile->setCanStep(true);
            return tile;
        });
        map->setDefaultTiles({{0, "shutdownFloor"}});
        auto target = std::make_shared<CMapObject>();
        target->setName("shutdownGoal");
        target->setCoords(Coords(7, 0, 0));
        map->addObject(target);
        auto creature = std::make_shared<CCreature>();
        creature->setName("shutdownChaser");
        creature->setGame(game);
        creature->setLevel(1);
        auto controller = std::make_shared<CTargetController>();
        controller->setTarget(target->getName());
        creature->setController(controller);
        map->addObject(creature);
        auto service = map->getNavigationService();
        std::packaged_task<bool()> request([mode, service, map, target, creature, controller]() {
            if (mode == 0)
                return controller->control(creature)->get() == ZERO;
            return service->nextStep(map, target, ZERO, target->getCoords(), 0).status ==
                   CNavigationFlowStatus::Cancelled;
        });
        auto result = request.get_future();
        std::thread worker(std::move(request));
        bool reached_factory;
        {
            pybind11::gil_scoped_release release;
            reached_factory = entered.wait_for(std::chrono::seconds(2)) == std::future_status::ready;
        }
        game->getContext()->shutdown();
        gate->resume.set_value();
        {
            pybind11::gil_scoped_release release;
            worker.join();
        }
        expect_true(reached_factory, "shutdown fixture must interrupt a running controller or flow query");
        try {
            expect_true(result.get(), "an in-flight query must cancel after shutdown without returning movement");
        } catch (...) {
            expect_true(false, "an in-flight shutdown must not escape through the controller or flow future");
        }
    }
}

void testStaleSnapshotCancellationAndWideCosts() {
    Fixture fixture(4, 1, Coords(3, 0, 0));
    auto tile = fixture.tile(Coords(1, 0, 0));
    auto stale = fixture.service->snapshot(fixture.map);
    tile->setMovementCost(std::numeric_limits<int>::max());
    fixture.tile(Coords(2, 0, 0), std::numeric_limits<int>::max());
    fixture.tile(Coords(3, 0, 0), std::numeric_limits<int>::max());
    const auto cancelled =
        fixture.flow->nextStep(stale, fixture.map, fixture.target, ZERO, fixture.target->getCoords(), 0);
    expect_true(cancelled.status == CNavigationFlowStatus::Cancelled && cancelled.step == ZERO,
                "a stale snapshot must not produce a movement command");
    const auto wide = fixture.step(ZERO, 1);
    expect_true(wide.status == CNavigationFlowStatus::Complete && wide.cost == 3LL * std::numeric_limits<int>::max(),
                "flow accumulation must retain costs beyond the signed 32-bit range");
    CNavigationFlow otherSession(std::make_shared<CNavigationBudget>());
    const auto mismatched = otherSession.nextStep(fixture.service->snapshot(fixture.map), fixture.map, fixture.target,
                                                  ZERO, fixture.target->getCoords(), 2);
    expect_true(mismatched.status == CNavigationFlowStatus::Cancelled,
                "a field must not combine snapshots and allocations from different session budgets");
}

void testDynamicFallbackFactoriesDoNotReusePersistentCosts() {
    Fixture fixture(3, 1, Coords(2, 0, 0));
    auto game = std::make_shared<CGame>();
    game->setMap(fixture.map);
    fixture.map->setGame(game);
    int cost = 1;
    game->getObjectHandler()->registerType("flowDynamicFloor", [&cost]() {
        auto tile = std::make_shared<CTile>();
        tile->setCanStep(true);
        tile->setMovementCost(cost);
        return tile;
    });
    fixture.map->setDefaultTiles({{0, "flowDynamicFloor"}});
    expect_true(!fixture.service->snapshot(fixture.map)->persistentCacheable(),
                "custom factory fixture must select nonpersistent navigation");
    const auto first = fixture.step(ZERO);
    cost = 10;
    const auto second = fixture.step(ZERO, 1);
    expect_true(first.status == CNavigationFlowStatus::Complete && first.cost == 2,
                "initial dynamic fallback route must use its current scalar cost");
    expect_true(second.status == CNavigationFlowStatus::Complete && second.cost == 20,
                "nonpersistent factory changes must not reuse an old field cost");
    expect_true(fixture.flow->statistics().fieldRebuilds == 2,
                "changed nonpersistent terrain must rebuild its field from current factory values");
}

void testDynamicDeferredPursuitResumesInRealMapTurns() {
    DynamicFixture fixture(200, 200, Coords(199, 199, 0));
    auto creature = std::make_shared<CCreature>();
    creature->setName("mutableFlowChaser");
    creature->setGame(fixture.game);
    creature->setLevel(1);
    creature->setHp(1);
    auto controller = std::make_shared<CTargetController>();
    controller->setTarget(fixture.target->getName());
    creature->setController(controller);
    fixture.map->addObject(creature);
    fixture.map->move();
    const auto first = fixture.service->flowStatistics();
    expect_true(fixture.map->getTurn() == 1 && creature->getCoords() == ZERO && first.expandedNodes == 25'000,
                "a real dynamic-terrain chaser inside its 256-cell leash must defer at 25k expansions");
    fixture.map->move();
    const auto completed = fixture.service->flowStatistics();
    expect_true(fixture.map->getTurn() == 2 && creature->getCoords() != ZERO,
                "the next real map turn must resume dynamic pursuit and commit a legal step");
    expect_true(completed.fieldRebuilds == 1 && completed.expandedNodes == 40'000,
                "stable dynamic pursuit must retain one field and settle the 200x200 route exactly once");
    expect_true(completed.dynamicCellSamples <= 40'800 && completed.dynamicCellRevalidations <= 25'800,
                "dynamic factories must be sampled once per cell and revalidated once before continuation");
    // Turn planning and committed movement also perform a small number of live destination lookups.
    expect_true(fixture.terrain->calls.load() <= completed.dynamicCellSamples + completed.dynamicCellRevalidations + 20,
                "actual factory callbacks must not bypass terrain sampling and validation counts");
    expect_true(fixture.service->budget()->peak() <= fixture.service->budget()->limit(),
                "retained dynamic terrain and reverse-search state must share the 128 MiB cap");
    std::cout << "Dynamic pursuit: expansions=" << completed.expandedNodes
              << "/40000 samples=" << completed.dynamicCellSamples
              << "/40800 revalidated=" << completed.dynamicCellRevalidations
              << "/25800 factoryCalls=" << fixture.terrain->calls.load() << '\n';
}

void testDynamicDeferredFieldRepairsMovingGoals() {
    DynamicFixture fixture(200, 200, Coords(199, 199, 0));
    const auto first = fixture.step(ZERO, 0);
    expect_true(first.status == CNavigationFlowStatus::Deferred, "moving-goal fixture must start with deferred work");
    fixture.target->moveTo(Coords(199, 198, 0));
    CNavigationFlowResult result;
    for (int turn = 1; turn <= 4; ++turn) {
        result = fixture.step(ZERO, turn);
        if (result.status != CNavigationFlowStatus::Deferred)
            break;
    }
    expect_true(result.status == CNavigationFlowStatus::Complete && result.cost == 397 && result.step != ZERO,
                "revalidated dynamic fields must finish an exact route after their target moves");
    expect_true(fixture.flow->statistics().fieldRebuilds == 1 && fixture.flow->statistics().incrementalRepairs >= 1,
                "goal motion alone must repair the retained dynamic field rather than restart it");
}

void testDynamicNearerChaserCompletionPreservesDeferredField() {
    DynamicFixture fixture(200, 200, Coords(199, 199, 0));
    expect_true(fixture.step(ZERO, 0).status == CNavigationFlowStatus::Deferred,
                "a far dynamic chaser must begin an unfinished shared field");
    const auto near = fixture.step(Coords(198, 199, 0), 0);
    expect_true(near.status == CNavigationFlowStatus::Complete && near.cost == 1 &&
                    near.step == fixture.target->getCoords(),
                "a nearer chaser may use a fully revalidated settled prefix of the shared field");
    const auto old_epoch = fixture.service->snapshot(fixture.map)->epoch();
    fixture.map->getTile(198, 198, 0);
    expect_true(fixture.service->snapshot(fixture.map)->epoch() != old_epoch,
                "materializing a dynamic floor must record an ordinary local routing change");
    const auto far = fixture.step(ZERO, 1);
    expect_true(far.status == CNavigationFlowStatus::Complete && far.cost == 398 && far.step != ZERO,
                "a nearer completed query must not discard the farther chaser's deferred frontier");
    expect_true(fixture.flow->statistics().fieldRebuilds == 1,
                "a nearer query and same-scalar tile materialization must preserve the shared deferred generation");
}

void testDynamicDeferredCostChangesInvalidateWithoutEpoch() {
    DynamicFixture fixture(200, 200, Coords(199, 199, 0));
    expect_true(fixture.step(ZERO, 0).status == CNavigationFlowStatus::Deferred,
                "mutable-cost fixture must retain an unfinished dynamic field");
    const auto epoch = fixture.service->snapshot(fixture.map)->epoch();
    fixture.terrain->cost = 3;
    expect_true(fixture.service->snapshot(fixture.map)->epoch() == epoch,
                "changing a factory closure must not supply an engine routing epoch");
    expect_true(fixture.step(ZERO, 1).status == CNavigationFlowStatus::Deferred,
                "changed sampled costs must restart under the original 25k expansion allowance");
    const auto result = fixture.step(ZERO, 2);
    expect_true(result.status == CNavigationFlowStatus::Complete && result.cost == 3 * 398,
                "deferred continuation must use newly sampled costs rather than frozen factory values");
    expect_true(fixture.flow->statistics().fieldRebuilds == 2,
                "unversioned cost changes must invalidate the unfinished field exactly once");
}

void testDynamicCompletedFieldsRefreshCostsAndBlockedCells() {
    DynamicFixture fixture(5, 2, Coords(4, 0, 0));
    fixture.tile(Coords(2, 0, 0), 1, false);
    auto first = fixture.step(ZERO, 0);
    expect_true(first.status == CNavigationFlowStatus::Complete && first.cost == 6,
                "initial dynamic route must detour around its blocking tile");
    const auto epoch = fixture.service->snapshot(fixture.map)->epoch();
    fixture.terrain->cost = 4;
    auto increased = fixture.step(ZERO, 1);
    fixture.terrain->cost = 1;
    auto decreased = fixture.step(ZERO, 2);
    expect_true(increased.status == CNavigationFlowStatus::Complete && increased.cost == 24 &&
                    decreased.status == CNavigationFlowStatus::Complete && decreased.cost == 6 &&
                    fixture.service->snapshot(fixture.map)->epoch() == epoch,
                "completed fields must observe both unversioned cost increases and decreases");
    fixture.terrain->walkable = false;
    auto blocked = fixture.step(ZERO, 3);
    fixture.terrain->walkable = true;
    auto reopened = fixture.step(ZERO, 4);
    expect_true(blocked.status == CNavigationFlowStatus::Unreachable && blocked.step == ZERO &&
                    reopened.status == CNavigationFlowStatus::Complete && reopened.cost == 6,
                "blocked dynamic samples must be revalidated when a factory reopens them without an epoch");
    const auto warm = fixture.flow->statistics();
    expect_true(fixture.step(ZERO, 5).cost == 6 && fixture.flow->statistics().fieldRebuilds == warm.fieldRebuilds,
                "a completed field may be reused only after its retained samples are revalidated");
}

void testDynamicBlockedIntermediateSamplesRevealNewShortcut() {
    DynamicFixture fixture(5, 1, Coords(4, 0, 0));
    auto upper_open = std::make_shared<bool>(false);
    auto handler = fixture.game->getObjectHandler();
    handler->registerType("mutableUpperFlowFloor", [upper_open]() {
        auto tile = std::make_shared<CTile>();
        tile->setCanStep(*upper_open);
        return tile;
    });
    handler->registerConfig("mutableUpperFlowFloor", std::make_shared<json>(json{{"class", "mutableUpperFlowFloor"}}));
    fixture.map->setXBounds({{0, 4}, {1, 1}});
    fixture.map->setYBounds({{0, 0}, {1, 0}});
    fixture.map->setDefaultTiles({{0, "mutableFlowFloor"}, {1, "mutableUpperFlowFloor"}});
    CNavigationEdge enter;
    enter.source = ZERO;
    enter.target = Coords(0, 0, 1);
    fixture.map->addNavigationEdge(enter);
    CNavigationEdge leave;
    leave.source = Coords(1, 0, 1);
    leave.target = fixture.target->getCoords();
    fixture.map->addNavigationEdge(leave);
    const auto closed = fixture.step(ZERO, 0);
    expect_true(closed.status == CNavigationFlowStatus::Complete && closed.cost == 4,
                "blocked intermediate dynamic cells must initially exclude the shorter connector route");
    const auto epoch = fixture.service->snapshot(fixture.map)->epoch();
    *upper_open = true;
    const auto opened = fixture.step(ZERO, 1);
    expect_true(fixture.service->snapshot(fixture.map)->epoch() == epoch &&
                    opened.status == CNavigationFlowStatus::Complete && opened.cost == 3 &&
                    opened.step == Coords(0, 0, 1),
                "full scalar validation must discover a reopened intermediate shortcut without any epoch change");
}

void testDynamicRevalidationBudgetSurvivesSameTurnEviction() {
    DynamicFixture fixture(4, 1, Coords(3, 0, 0));
    fixture.flow = std::make_unique<CNavigationFlow>(fixture.service->budget(), 64);
    expect_true(fixture.step(ZERO, 0).status == CNavigationFlowStatus::Complete,
                "small validation-budget fixture must first populate an exact field");
    CNavigationFlowResult result;
    for (int attempt = 0; attempt < 65; ++attempt) {
        result = fixture.step(ZERO, 0);
        if (result.status == CNavigationFlowStatus::Deferred)
            break;
    }
    const auto exhausted = fixture.flow->statistics();
    expect_true(result.status == CNavigationFlowStatus::Deferred && result.step == ZERO &&
                    exhausted.dynamicCellRevalidations <= 64,
                "same-turn requests must stop when their full scalar validation no longer fits the allowance");
    expect_true(fixture.step(ZERO, 0).status == CNavigationFlowStatus::Deferred &&
                    fixture.flow->statistics().dynamicCellRevalidations == exhausted.dynamicCellRevalidations,
                "a repeated deferred request must not begin a partial fresh validation scan");
    expect_true(fixture.flow->evictUnused(), "the completed dynamic field must be available for eviction");
    expect_true(fixture.step(ZERO, 0).status == CNavigationFlowStatus::Complete &&
                    fixture.step(ZERO, 0).status == CNavigationFlowStatus::Deferred,
                "eviction may sample a fresh field but must not replenish its spent same-turn scan allowance");
    expect_true(fixture.flow->statistics().dynamicCellRevalidations == exhausted.dynamicCellRevalidations,
                "validation accounting must survive destruction and replacement of the cached field");
    expect_true(fixture.step(ZERO, 1).status == CNavigationFlowStatus::Complete,
                "the next map turn must restore one bounded validation allowance");
    fixture.flow = std::make_unique<CNavigationFlow>(fixture.service->budget(), 0);
    expect_true(fixture.step(ZERO, 2).status == CNavigationFlowStatus::Complete &&
                    fixture.step(ZERO, 3).status == CNavigationFlowStatus::Deferred,
                "a zero validation allowance must fail closed rather than reuse unverified scalar terrain");
}

void testDynamicRevalidationCancelsAndReleasesMemoStorage() {
    DynamicFixture fixture(4, 1, Coords(3, 0, 0));
    fixture.service->snapshot(fixture.map);
    const auto empty_bytes = fixture.service->budget()->used();
    expect_true(fixture.step(ZERO, 0).status == CNavigationFlowStatus::Complete,
                "cancellation fixture must retain a completed dynamic memo");
    fixture.terrain->onRead = [map = fixture.map, terrain = fixture.terrain]() {
        terrain->onRead = {};
        map->setWrapX({{0, 1}});
    };
    const auto cancelled = fixture.step(ZERO, 1);
    expect_true(cancelled.status == CNavigationFlowStatus::Cancelled && cancelled.step == ZERO,
                "routing changes inside scalar revalidation must cancel without returning a stale step");
    fixture.flow->shutdown();
    expect_true(fixture.service->budget()->used() <= empty_bytes,
                "terminal flow shutdown must release sampled terrain, field state and validation ledger storage");
}

void testDynamicMemoMemoryPressureIsRecoverable() {
    DynamicFixture fixture(32, 32, Coords(31, 31, 0));
    fixture.service->snapshot(fixture.map);
    const auto budget = fixture.service->budget();
    const auto reserved = budget->limit() - budget->used() - 16 * 1024;
    expect_true(budget->tryReserve(reserved), "dynamic memory fixture must reserve its navigation headroom");
    const auto denied = fixture.step(ZERO, 0);
    expect_true(denied.status == CNavigationFlowStatus::ResourceLimit && denied.step == ZERO,
                "denied terrain-memo allocations must not expose a partially repaired movement result");
    budget->release(reserved);
    const auto recovered = fixture.step(ZERO, 1);
    expect_true(recovered.status == CNavigationFlowStatus::Complete && recovered.cost == 62 &&
                    budget->peak() <= budget->limit(),
                "dynamic pursuit must recover within the original memory cap after headroom is restored");
}
} // namespace

int main() {
    pybind11::scoped_interpreter interpreter;
    testGameplayHooksAllowReentrantWorkerNavigation();
    testNativeMovementWaitsForPythonBeforeLockingTheMap();
    testWarmFieldsSurviveCommittedSteppableMoves();
    testMovingGoalAndDirectTerrainChangesRepairTheField();
    testBlockingObjectsAndBlockedGoalsInvalidateTheirCells();
    testDirectedConnectorCostsAndTopologyRebuilds();
    testSeededRepairsMatchDijkstraOnWrappedWeightedTerrain();
    testWorkLimitDefersAndResumesWithoutProvisionalSteps();
    testEvictionCannotRenewSameTurnWork();
    testMissingJournalHistoryRebuildsWithoutKeepingOldSteps();
    testRouteLengthLimitIsNotReportedAsUnreachable();
    testEntryLimitEvictsLeastRecentlyUsedTargetIdentity();
    testSessionMemoryPressureIsExplicitAndRecoverable();
    testShutdownClearsOnlyTheOwningGamesNavigationCaches();
    testTerminalShutdownReleasesTheLedgerWithLiveOwners();
    testInFlightShutdownCancelsControllerAndDirectFlow();
    testStaleSnapshotCancellationAndWideCosts();
    testDynamicFallbackFactoriesDoNotReusePersistentCosts();
    testDynamicDeferredPursuitResumesInRealMapTurns();
    testDynamicDeferredFieldRepairsMovingGoals();
    testDynamicNearerChaserCompletionPreservesDeferredField();
    testDynamicDeferredCostChangesInvalidateWithoutEpoch();
    testDynamicCompletedFieldsRefreshCostsAndBlockedCells();
    testDynamicBlockedIntermediateSamplesRevealNewShortcut();
    testDynamicRevalidationBudgetSurvivesSameTurnEviction();
    testDynamicRevalidationCancelsAndReleasesMemoStorage();
    testDynamicMemoMemoryPressureIsRecoverable();
    return finish_tests();
}
