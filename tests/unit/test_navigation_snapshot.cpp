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
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CNavigationSearch.h"
#include "core/CRuntimeBridge.h"
#include "handler/CObjectHandler.h"
#include "object/CMapObject.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <climits>
#include <chrono>
#include <future>
#include <random>
#include <thread>
#include <pybind11/embed.h>

namespace {
struct Fixture {
    std::shared_ptr<CGame> game = CGameLoader::loadGame();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CNavigationService> service;
    Fixture(int maximum = 95) {
        map->setGame(game);
        game->setMap(map);
        map->setXBounds({{0, maximum}});
        map->setYBounds({{0, maximum}});
        map->setDefaultTiles({{0, "GrassTile"}});
        map->setOutOfBoundsTiles({{0, "MountainTile"}});
        service = CNavigationService::forMap(map);
    }
    std::shared_ptr<CNavigationSnapshot> snapshot() { return service->snapshot(map); }
    std::shared_ptr<CTile> tile(Coords coords, int cost = 1) {
        auto value = std::make_shared<CTile>();
        value->setGame(game);
        value->setCanStep(true);
        value->setMovementCost(cost);
        expect_true(map->addTile(value, coords.x, coords.y, coords.z), "fixture tile is newly inserted");
        return value;
    }
};

std::vector<Coords> flattened(const CNavigationNeighbors &neighbors) {
    std::vector<Coords> result(neighbors.cardinal.begin(), neighbors.cardinal.begin() + neighbors.count);
    result.insert(result.end(), neighbors.connectors.begin(), neighbors.connectors.end());
    return result;
}

void testFiniteAndPassableOutside() {
    Fixture fixture;
    auto closed = fixture.snapshot();
    expect_true(closed->isFinite() && closed->canStep(Coords(0, 0, 0)) && !closed->canStep(Coords(-1, 0, 0)),
                "canonical bounded native terrain is a closed indexed domain");
    expect_true(!closed->isFiniteFor(Coords(0, 0, 7), Coords(2, 0, 7)),
                "an unconfigured elevation cannot inherit another level's closed-domain eligibility");
    auto unknownLevel = CNavigationSearch::findPath(closed, Coords(0, 0, 7), Coords(2, 0, 7));
    expect_true(unknownLevel.status == CNavigationSearchStatus::Found && unknownLevel.cost == 2 &&
                    unknownLevel.statistics.chunkAllocations == 0,
                "unbounded fallback elevation preserves authoritative routes through compact sparse search");
    fixture.map->setOutOfBoundsTiles({{0, "GrassTile"}});
    auto open = fixture.snapshot();
    expect_true(!closed->isCurrent() && !open->isFinite() && open->canStep(Coords(-1, 0, 0)),
                "passable outside terrain disables the closed-domain fast path without clipping it");
    expect_true(open->heuristic(Coords(0, 0, 0), Coords(10, 10, 0)) == 0,
                "unsupported open domain uses a safe zero heuristic");
    fixture.map->setOutOfBoundsTiles({{0, "MountainTile"}});
    auto external = fixture.tile(Coords(100, 0, 0));
    auto sparse = fixture.snapshot();
    expect_true(!sparse->isFinite() && sparse->canStep(Coords(100, 0, 0)),
                "authored passable cells outside nominal bounds retain sparse-domain behavior");
    expect_true(fixture.map->getTiles().size() == 1, "snapshot inspection does not materialize missing tiles");
}

void testDirectAndReflectedMutations() {
    Fixture fixture;
    const Coords coords(2, 3, 0);
    auto tile = fixture.tile(coords, 7);
    auto first = fixture.snapshot();
    const auto epoch = first->epoch();
    expect_true(first->canStep(coords) && first->movementCost(coords) == 7, "snapshot reflects native tile state");
    tile->setCanStep(true);
    tile->setMovementCost(7);
    fixture.map->setXBounds({{0, 95}});
    fixture.map->setDefaultTiles({{0, "GrassTile"}});
    expect_true(fixture.map->getRoutingEpoch() == epoch && fixture.snapshot() == first,
                "no-op native setters retain the current snapshot and epoch");
    tile->setMovementCost(9);
    auto second = fixture.snapshot();
    expect_true(!first->isCurrent() && second->movementCost(coords) == 9,
                "direct movement-cost mutation invalidates prior scalar state");
    // These are the existing reflective entrypoints used by Python set_property and JSON deserialization.
    tile->setBoolProperty("canStep", false);
    auto third = fixture.snapshot();
    expect_true(!second->isCurrent() && !third->canStep(coords),
                "reflective canStep setter invokes authoritative navigation invalidation");
    tile->setNumericProperty("movementCost", 11);
    auto fourth = fixture.snapshot();
    expect_true(!third->isCurrent() && fourth->movementCost(coords) == 11,
                "reflective movementCost setter refreshes cached authoritative cost");
    tile->setNumericProperty("posx", 4);
    auto moved = fixture.snapshot();
    expect_true(moved->canStep(coords) && !moved->canStep(Coords(4, 3, 0)) && fixture.map->contains(4, 3, 0) &&
                    !fixture.map->contains(2, 3, 0),
                "reflective tile relocation updates indexed membership and both affected cells");
    auto object = std::make_shared<CMapObject>();
    object->setGame(fixture.game);
    object->setName("navigationBlockingObject");
    object->setPosX(1);
    object->setPosY(1);
    object->setCanStep(true);
    fixture.map->addObject(object);
    auto clear = fixture.snapshot();
    object->setBoolProperty("canStep", false);
    auto blocked = fixture.snapshot();
    expect_true(!clear->isCurrent() && !blocked->canStep(Coords(1, 1, 0)),
                "reflective object passability changes invalidate occupancy");
    object->setNumericProperty("posx", 2);
    auto relocated = fixture.snapshot();
    expect_true(relocated->canStep(Coords(1, 1, 0)) && !relocated->canStep(Coords(2, 1, 0)),
                "reflective object relocation repairs old and new occupancy cells");
}

void testDirtyChunkReuseAndJournalOverflow() {
    Fixture fixture;
    auto tile = fixture.tile(Coords(2, 2, 0));
    auto first = fixture.snapshot();
    first->canStep(Coords(2, 2, 0));
    first->canStep(Coords(40, 2, 0));
    first->canStep(Coords(70, 2, 0));
    expect_true(first->chunkCount() == 3, "fixture populates three distinct lazy chunks");
    tile->setMovementCost(2);
    auto second = fixture.snapshot();
    expect_true(second->chunkCount() == 2 && first->chunkCount() == 3 && !first->isCurrent(),
                "new snapshot shares only clean chunks while externally pinned old storage remains valid");
    auto changes = second->changesSince(first->epoch());
    expect_true(changes && changes->size() == 1 && changes->front() == Coords(2, 2, 0),
                "local edit journal identifies the precise dirty cell");
    expect_true(second->movementCost(Coords(2, 2, 0)) == 2 && second->chunkCount() == 3,
                "dirty chunk rebuild exposes the changed cost without touching clean chunks");
    auto beforeOverflow = second->epoch();
    for (int i = 0; i < 1025; ++i)
        tile->setMovementCost(i % 2 ? 2 : 3);
    auto overflow = fixture.snapshot();
    expect_true(!overflow->changesSince(beforeOverflow),
                "journal overflow requests a full rebuild instead of missing edits");
    expect_true(overflow->chunkCount() == 0, "overflow cannot reuse possibly stale chunks");
    expect_true(overflow->movementCost(Coords(2, 2, 0)) == 3,
                "overflow rebuild retains final authoritative tile state");
    fixture.map->setDefaultTiles({{0, "MountainTile"}});
    auto topology = fixture.snapshot();
    expect_true(!topology->changesSince(overflow->epoch()) && !topology->canStep(Coords(40, 2, 0)),
                "global default-terrain changes invalidate the complete chunk graph");
}

void testConfigAndFactoryInvalidation() {
    Fixture fixture;
    auto handler = fixture.game->getObjectHandler();
    const auto makeConfig = [](bool step, int cost) {
        return std::make_shared<json>(
            json{{"class", "CTile"}, {"properties", {{"canStep", step}, {"movementCost", cost}}}});
    };
    handler->registerConfig("navigationTerrain", makeConfig(true, 3));
    fixture.map->setDefaultTiles({{0, "navigationTerrain"}});
    auto first = fixture.snapshot();
    expect_true(first->isFinite() && first->movementCost(Coords(8, 8, 0)) == 3,
                "native resource configuration can be resolved without allocating a tile per cell");
    handler->registerConfig("navigationTerrain", makeConfig(false, 5));
    expect_true(!first->isCurrent(), "configuration replacement invalidates a pinned snapshot lazily");
    auto replaced = fixture.snapshot();
    expect_true(!replaced->canStep(Coords(8, 8, 0)) && replaced->movementCost(Coords(8, 8, 0)) == 5,
                "replacement configuration changes passability and cost together");
    auto live = std::make_shared<bool>(true);
    handler->beginMapScriptScope();
    handler->registerType("NavigationMutableTile", [live]() {
        auto tile = std::make_shared<CTile>();
        tile->setCanStep(*live);
        return tile;
    });
    handler->endMapScriptScope();
    handler->registerConfig("navigationDynamicTerrain",
                            std::make_shared<json>(json{{"class", "NavigationMutableTile"}}));
    fixture.map->setDefaultTiles({{0, "navigationDynamicTerrain"}});
    auto dynamic = fixture.snapshot();
    expect_true(!dynamic->isFinite() && dynamic->canStep(Coords(8, 8, 0)),
                "custom factories retain callback-backed navigation instead of speculative scalar caching");
    *live = false;
    expect_true(!dynamic->canStep(Coords(8, 8, 0)) && dynamic->chunkCount() == 0,
                "custom factory state changes remain observable without persistent frozen chunks");
    handler->beginMapScriptScope();
    handler->registerType("NavigationMutableTile", []() {
        auto tile = std::make_shared<CTile>();
        tile->setCanStep(true);
        return tile;
    });
    handler->endMapScriptScope();
    expect_true(!dynamic->isCurrent() && fixture.snapshot()->canStep(Coords(8, 8, 0)),
                "map-scoped factory replacement invalidates old snapshot state");
}

void testChunkClearDoesNotWaitForCellConstruction() {
    class AllocationGateBudget : public CNavigationBudget {
      public:
        std::atomic_bool armed = false;
        std::promise<void> entered;
        std::promise<void> resume;
        std::shared_future<void> resumed = resume.get_future().share();

      private:
        void *do_allocate(std::size_t bytes, std::size_t alignment) override {
            if (!tryReserve(bytes))
                throw std::bad_alloc();
            try {
                if (armed.exchange(false)) {
                    entered.set_value();
                    resumed.wait();
                }
                return std::pmr::new_delete_resource()->allocate(bytes, alignment);
            } catch (...) {
                release(bytes);
                throw;
            }
        }
        void do_deallocate(void *pointer, std::size_t bytes, std::size_t alignment) override {
            std::pmr::new_delete_resource()->deallocate(pointer, bytes, alignment);
            release(bytes);
        }
    };
    Fixture fixture(7);
    auto handler = fixture.game->getObjectHandler();
    const auto config = [](bool passable) {
        return std::make_shared<json>(json{{"class", "CTile"}, {"properties", {{"canStep", passable}}}});
    };
    handler->registerConfig("allocationGateFloor", config(true));
    fixture.map->setDefaultTiles({{0, "allocationGateFloor"}});
    auto budget = std::make_shared<AllocationGateBudget>();
    auto snapshot = std::make_shared<CNavigationSnapshot>(budget, fixture.map, fixture.service);
    auto entered = budget->entered.get_future();
    budget->armed = true;
    std::packaged_task<bool()> query([snapshot]() { return snapshot->canStep(ZERO); });
    auto queried = query.get_future();
    std::thread reader(std::move(query));
    const bool allocating = entered.wait_for(std::chrono::seconds(2)) == std::future_status::ready;
    std::packaged_task<void()> clear([snapshot]() { snapshot->clearChunks(); });
    auto cleared = clear.get_future();
    std::thread trimmer(std::move(clear));
    const bool cleared_during_fill = cleared.wait_for(std::chrono::seconds(2)) == std::future_status::ready;
    // The service trim path calls clearChunks while holding its journal mutex.
    // No chunk lock may span construction, which can publish a config revision there.
    handler->registerConfig("allocationGateFloor", config(false));
    budget->resume.set_value();
    {
        pybind11::gil_scoped_release release;
        reader.join();
        trimmer.join();
    }
    expect_true(allocating, "chunk fixture must suspend a real budgeted allocation");
    expect_true(cleared_during_fill, "chunk clearing must finish while a new scalar chunk is still being built");
    try {
        cleared.get();
        expect_true(!queried.get(), "a config change during chunk construction must discard the stale cell result");
    } catch (...) {
        expect_true(false, "chunk construction and clearing must complete without an exception");
    }
    expect_true(
        !snapshot->isCurrent() && snapshot->chunkCount() == 0 && !fixture.snapshot()->canStep(ZERO),
        "stale chunk construction must not publish old cells, and a refreshed snapshot must see the new config");
    expect_true(budget->peak() <= budget->limit(), "chunk construction retains the shared allocation limit");
}

void testNeighborsAndConnectorLowerBounds() {
    Fixture fixture;
    auto add = [&](Coords from, Coords to, bool bidirectional = false) {
        CNavigationEdge edge;
        edge.source = from;
        edge.target = to;
        edge.bidirectional = bidirectional;
        fixture.map->registerNavigationEdge(edge);
    };
    add(Coords(0, 0, 0), Coords(1, 0, 0));
    add(Coords(0, 0, 0), Coords(1, 0, 0));
    add(Coords(0, 0, 0), Coords(10, 0, 0));
    auto first = fixture.snapshot();
    auto actual = flattened(first->neighbors(Coords(0, 0, 0)));
    expect_true(actual == fixture.map->getNavigationNeighbors(Coords(0, 0, 0)),
                "compact neighbors retain authored order and deduplicate cardinal/connector overlap");
    auto reverse = flattened(first->neighbors(Coords(10, 0, 0), true));
    expect_true(std::ranges::find(reverse, Coords(0, 0, 0)) != reverse.end(),
                "directed connector appears in reverse predecessor traversal");
    fixture.map->removeNavigationEdge(Coords(0, 0, 0), Coords(10, 0, 0));
    add(Coords(0, 5, 0), Coords(10, 5, 0));
    auto portal = fixture.snapshot();
    const Coords start(1, 5, 0), goal(10, 5, 0);
    expect_true(portal->heuristic(start, goal) <= 2,
                "relaxed connector heuristic allows initially walking away from the goal to a cheap portal");
    auto result = CNavigationSearch::findPath(portal, start, goal);
    expect_true(result.status == CNavigationSearchStatus::Found && result.cost == 2 &&
                    result.firstStep == Coords(0, 5, 0),
                "authoritative weighted search selects the cheap route behind its starting position");
    for (int i = 0; i < 34; ++i)
        add(Coords(i, 10, 0), Coords(i, 20, 0));
    auto many = fixture.snapshot();
    expect_true(many->isFinite() && many->heuristic(start, goal) == 0,
                "more than 64 connector endpoints retain exact safe search without unbounded heuristic preprocessing");
}

void testConnectorCostsRemainDirectedFrozenAndWide() {
    Fixture fixture(8);
    fixture.map->setXBounds({{0, 8}, {1, 8}});
    fixture.map->setYBounds({{0, 2}, {1, 2}});
    fixture.map->setWrapX({{0, 1}});
    const Coords source(0, 0, 0), target(5, 0, 1), wideSource(7, 0, 0), wideTarget(7, 0, 1);
    fixture.tile(target, 3);
    fixture.tile(wideTarget, INT_MAX);
    fixture.map->registerNavigationEdge({source, target, true, true, 8, "pricedPortal"});
    fixture.map->registerNavigationEdge({source, target, true, false, 4, "cheapPortal"});
    fixture.map->registerNavigationEdge({source, target, false, false, 1});
    fixture.map->registerNavigationEdge({Coords(4, 0, 1), target, true, false, 20});
    fixture.map->registerNavigationEdge({Coords(8, 0, 0), source, true, false, 20});
    fixture.map->registerNavigationEdge({wideSource, wideTarget, true, false, INT_MAX});
    auto snapshot = fixture.snapshot();
    expect_true(snapshot->stepCost(source, target) == 6 && snapshot->stepCost(target, source) == 8,
                "snapshot freezes minimum directed fees with forward and reverse destination terrain");
    expect_true(snapshot->stepCost(Coords(4, 0, 1), target) == 3 && snapshot->stepCost(Coords(8, 0, 0), source) == 1,
                "cardinal and wrapped cardinal steps ignore overlapping connector surcharges");
    const auto wideCost = static_cast<std::int64_t>(INT_MAX) * 2 - 1;
    expect_true(snapshot->stepCost(wideSource, wideTarget) == wideCost &&
                    fixture.map->lookupNavigationStepCost(wideSource, wideTarget) == wideCost,
                "snapshot and diagnostic costs preserve a sum larger than the 32-bit limit");
    fixture.map->unregisterNavigationEdgesForObject("cheapPortal");
    auto changed = fixture.snapshot();
    expect_true(!snapshot->isCurrent() && changed->stepCost(source, target) == 10,
                "removing the cheap parallel connector invalidates the frozen fee table");
    expect_true(snapshot->budget()->peak() <= snapshot->budget()->limit(),
                "frozen connector fee storage remains charged to the unchanged session cap");
}

void testWeightedWrappedMapOracle() {
    constexpr int side = 7;
    constexpr int count = side * side;
    constexpr auto infinity = std::numeric_limits<std::int64_t>::max() / 4;
    std::mt19937 random(314159);
    const auto coords = [](int index) { return Coords(index % side, index / side, 0); };
    for (int trial = 0; trial < 6; ++trial) {
        Fixture fixture(side - 1);
        fixture.map->setWrapX({{0, trial % 2}});
        fixture.map->setWrapY({{0, trial / 2 % 2}});
        std::array<bool, count> passable;
        for (int i = 0; i < count; ++i) {
            auto tile = fixture.tile(coords(i), 1 + random() % 13);
            passable[i] = i == 0 || i == count - 1 || random() % 4 != 0;
            tile->setCanStep(passable[i]);
        }
        for (int i = 0; i < 5; ++i) {
            CNavigationEdge edge;
            edge.source = coords(random() % count);
            edge.target = coords(random() % count);
            edge.bidirectional = i % 2 == 0;
            edge.movementCost = 1 + random() % 19;
            fixture.map->registerNavigationEdge(edge);
        }
        const auto edges = fixture.map->getNavigationEdges();
        const auto authoredCost = [&](Coords from, Coords to) {
            const std::int64_t terrain = fixture.map->lookupMovementCost(to);
            const auto adjacent = fixture.map->getAdjacentCoords(from);
            if (std::ranges::find(adjacent, to) != adjacent.end())
                return terrain;
            auto best = infinity;
            for (const auto &edge : edges)
                if (edge.enabled && ((edge.source == from && edge.target == to) ||
                                     (edge.bidirectional && edge.target == from && edge.source == to)))
                    best = std::min(best, terrain + std::max(1, edge.movementCost) - 1);
            return best;
        };
        // Independent all-pairs relaxation uses authoritative map edges and destination costs,
        // without consulting the snapshot's heuristic, compact adjacency or indexed search.
        std::array<std::array<std::int64_t, count>, count> costs;
        for (int from = 0; from < count; ++from) {
            costs[from].fill(infinity);
            costs[from][from] = 0;
            if (!passable[from])
                continue;
            for (auto next : fixture.map->getNavigationNeighbors(coords(from))) {
                if (next.x < 0 || next.y < 0 || next.x >= side || next.y >= side || !fixture.map->canStep(next))
                    continue;
                const int to = next.y * side + next.x;
                costs[from][to] = std::min(costs[from][to], authoredCost(coords(from), next));
            }
        }
        for (int via = 0; via < count; ++via)
            for (int from = 0; from < count; ++from)
                for (int to = 0; to < count; ++to)
                    costs[from][to] = std::min(costs[from][to], costs[from][via] + costs[via][to]);
        auto snapshot = fixture.snapshot();
        expect_true(snapshot->isFinite(), "weighted wrapped fixture remains eligible for indexed navigation");
        CNavigationSearchWorkspace workspace;
        for (int query = 0; query < 5; ++query) {
            const int from = query == 0 ? 0 : random() % count;
            const int to = query == 0 ? count - 1 : random() % count;
            if (!passable[from] || !passable[to])
                continue;
            auto result = CNavigationSearch::findPath(snapshot, coords(from), coords(to), &workspace);
            if (costs[from][to] == infinity) {
                expect_true(result.status == CNavigationSearchStatus::Unreachable && result.path.empty(),
                            "weighted wrapped map unreachable result matches independent all-pairs oracle");
                continue;
            }
            expect_true(result.status == CNavigationSearchStatus::Found && result.cost == costs[from][to],
                        "indexed weighted wrap/portal route has the exact independently computed minimum cost");
            for (int cell = 0; cell < count; ++cell)
                if (passable[cell] && costs[cell][to] < infinity)
                    expect_true(snapshot->heuristic(coords(cell), coords(to)) <= costs[cell][to],
                                "portal-aware heuristic never exceeds the authoritative remaining route cost");
            std::int64_t total = 0;
            auto previous = coords(from);
            for (auto next : result.path) {
                if (from == to && next == previous)
                    continue;
                const auto neighbors = fixture.map->getNavigationNeighbors(previous);
                expect_true(std::ranges::find(neighbors, next) != neighbors.end() && fixture.map->canStep(next),
                            "every returned step follows an authoritative passable edge");
                total += authoredCost(previous, next);
                previous = next;
            }
            expect_true(previous == coords(to) && total == costs[from][to],
                        "returned route independently recomputes to the exact minimum cost and destination");
        }
    }
}

void testMaximumWrappedAxis() {
    Fixture fixture(INT_MAX);
    fixture.map->setYBounds({{0, 0}});
    fixture.map->setWrapX({{0, 1}});
    const Coords start(INT_MAX, 0, 0), goal(0, 0, 0);
    auto snapshot = fixture.snapshot();
    expect_true(fixture.map->normalizeCoords(Coords(-1, 0, 0)) == start &&
                    snapshot->normalize(Coords(-1, 0, 0)) == start,
                "maximum integer wrapped bounds normalize consistently without overflowing the axis size");
    expect_true(fixture.map->getShortestDelta(start, goal) == EAST &&
                    fixture.map->getShortestDelta(goal, start) == WEST && fixture.map->getDistance(start, goal) == 1,
                "maximum wrapped shortest deltas and distance agree with the adjacent navigation edge");
    CNavigationSearchLimits limits;
    limits.maxExpansions = 16;
    limits.maxRecords = 64;
    auto result = CNavigationSearch::findPath(snapshot, start, goal, nullptr, limits);
    expect_true(result.status == CNavigationSearchStatus::Found && result.cost == 1 && result.path.size() == 1 &&
                    result.path.front() == goal,
                "maximum integer wrapped boundary retains its adjacent exact-cost route");
}

void testAuthoredLevelProofOverflowFallsBackWithoutClipping() {
    Fixture fixture(2);
    std::map<int, int> bounds;
    for (int level = 0; level < 65; ++level)
        bounds[level] = 2;
    fixture.map->setXBounds(bounds);
    fixture.map->setYBounds(bounds);
    for (int level = 0; level < 65; ++level)
        fixture.tile(Coords(1, 1, level));
    auto overflow = fixture.snapshot();
    const Coords start(1, 1, 64), goal(2, 1, 64);
    auto sparse = CNavigationSearch::findPath(overflow, start, goal);
    expect_true(!overflow->isFinite() && sparse.status == CNavigationSearchStatus::Found && sparse.cost == 1 &&
                    sparse.path.size() == 1 && sparse.path.front() == goal && sparse.statistics.chunkAllocations == 0,
                "more than 64 authored elevations use exact sparse routing without dropping the final level");
    fixture.map->setTiles({});
    auto reset = fixture.snapshot();
    auto indexed = CNavigationSearch::findPath(reset, start, goal);
    expect_true(!overflow->isCurrent() && reset->isFinite() && indexed.status == CNavigationSearchStatus::Found &&
                    indexed.cost == 1 && indexed.statistics.chunkAllocations > 0,
                "replacing the full tile set clears overflow proof state and restores indexed eligibility");
}

void testPinnedBudgetLifetime() {
    Fixture fixture;
    auto budget = fixture.service->budget();
    std::shared_ptr<CNavigationSnapshot> pinned = fixture.snapshot();
    pinned->canStep(Coords(1, 1, 0));
    const auto allocated = budget->used();
    fixture.map->setDefaultTiles({{0, "MountainTile"}});
    auto fresh = fixture.snapshot();
    fresh->canStep(Coords(1, 1, 0));
    expect_true(budget->used() > allocated && budget->peak() <= budget->limit(),
                "old pinned and replacement snapshots are simultaneously charged to the same hard budget");
    const auto both = budget->used();
    pinned.reset();
    expect_true(budget->used() < both, "releasing the last old snapshot releases its charged immutable chunks");
    fixture.game->setMap({});
    fixture.map.reset();
    expect_true(!fresh->isCurrent(), "a snapshot never keeps a detached map alive by ownership cycle");
    fresh.reset();
    fixture.service.reset();
    fixture.game->getContext()->shutdown();
    expect_true(budget->used() == 0,
                "explicit context shutdown releases all navigation memory while the game object remains held");
    bool rejected = false;
    try {
        fixture.game->getNavigationService();
    } catch (const std::runtime_error &) {
        rejected = true;
    }
    expect_true(rejected && budget->used() == 0,
                "an inactive context cannot recreate a navigation service or allocate a replacement cache");
    fixture.game.reset();
    expect_true(budget->used() == 0, "session teardown releases snapshots, journals, caches and service metadata");
}

void testLifecycleCancellationPreservesActiveErrors() {
    Fixture fixture;
    auto handler = fixture.game->getObjectHandler();
    bool shutdown = false;
    handler->registerType("NavigationThrowingTile", [&]() -> std::shared_ptr<CGameObject> {
        if (shutdown)
            fixture.game->getContext()->shutdown();
        throw std::runtime_error("navigation fixture factory error");
    });
    handler->registerConfig("navigationThrowingTerrain",
                            std::make_shared<json>(json{{"class", "NavigationThrowingTile"}}));
    fixture.map->setDefaultTiles({{0, "navigationThrowingTerrain"}});
    auto snapshot = fixture.snapshot();
    bool propagated = false;
    try {
        CNavigationSearch::findPath(snapshot, Coords(1, 1, 0), Coords(2, 1, 0));
    } catch (const std::runtime_error &error) {
        propagated = std::string(error.what()).find("navigation fixture factory error") != std::string::npos;
    }
    expect_true(propagated && snapshot->isCurrent(),
                "an active snapshot never disguises an actual terrain callback exception as cancellation");
    shutdown = true;
    auto cancelled = CNavigationSearch::findPath(snapshot, Coords(1, 1, 0), Coords(2, 1, 0));
    expect_true(cancelled.status == CNavigationSearchStatus::Cancelled && cancelled.path.empty() &&
                    cancelled.firstStep == Coords(1, 1, 0) && !fixture.game->getContext()->isActive(),
                "a callback interrupted by context shutdown returns cancellation without publishing a partial route");
}

void testIdleWorkspaceRecoveryUnderSharedBudget() {
    Fixture first;
    Fixture second;
    auto service = std::make_shared<CNavigationService>(160 * 1024);
    const Coords start(1, 1, 0), goal(2, 1, 0);
    const auto original = service->findPath(first.map, start, goal);
    expect_true(original == std::vector<Coords>{goal}, "small-cap first session query obtains its initial workspace");
    auto budget = service->budget();
    // Retain a real charged allocation to leave room for one workspace and two map journals, but not
    // both maps' cached chunks during replacement. A single eviction/retry must reclaim the idle cache.
    if (budget->used() + 32 * 1024 >= budget->limit()) {
        expect_true(false, "small-cap fixture must leave space for controlled pressure");
        return;
    }
    const auto reserve = budget->limit() - budget->used() - 32 * 1024;
    void *pressure = budget->allocate(reserve, alignof(std::max_align_t));
    const auto denied = service->findPath(second.map, start, goal);
    budget->deallocate(pressure, reserve, alignof(std::max_align_t));
    const auto recovered = service->findPath(second.map, start, goal);
    expect_true(recovered == std::vector<Coords>{goal},
                "allocation denial and retained idle workspace cannot permanently poison the next map query");
    expect_true(denied == std::vector<Coords>{goal},
                "bounded eviction/retry reclaims idle scalar chunks to navigate another map under pressure");
    expect_true(budget->peak() <= budget->limit(), "eviction and retry never exceed the shared cap");
    service->trimCaches();
    const auto repeated = service->findPath(first.map, start, goal);
    expect_true(repeated == std::vector<Coords>{goal}, "explicit cache trim leaves both maps able to navigate again");
}
} // namespace

int main() {
    pybind11::scoped_interpreter guard{};
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    testFiniteAndPassableOutside();
    testDirectAndReflectedMutations();
    testDirtyChunkReuseAndJournalOverflow();
    testConfigAndFactoryInvalidation();
    testChunkClearDoesNotWaitForCellConstruction();
    testNeighborsAndConnectorLowerBounds();
    testConnectorCostsRemainDirectedFrozenAndWide();
    testWeightedWrappedMapOracle();
    testMaximumWrappedAxis();
    testAuthoredLevelProofOverflowFallsBackWithoutClipping();
    testPinnedBudgetLifetime();
    testLifecycleCancellationPreservesActiveErrors();
    testIdleWorkspaceRecoveryUnderSharedBudget();
    return finish_tests();
}
