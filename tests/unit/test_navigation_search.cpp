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
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CNavigationSearch.h"
#include "core/CRuntimeBridge.h"
#include "core/CTypes.h"
#include "handler/CObjectHandler.h"
#include "test_harness.h"

#include <climits>
#include <future>
#include <queue>
#include <random>
#include <pybind11/embed.h>

namespace {
const auto noWaypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };
const auto zeroDistance = [](const Coords &, const Coords &) { return 0.0; };

void testLargeCostsAndFailureSentinels() {
    const Coords start(0, 0, 0), goal(3, 0, 0);
    auto passable = [](Coords c) { return c.y == 0 && c.z == 0 && c.x >= 0 && c.x <= 3; };
    auto cost = [](Coords, Coords) { return INT_MAX; };
    auto result =
        CNavigationSearch::findGenericPath(start, goal, passable, noWaypoint, default_neighbors, zeroDistance, cost);
    expect_true(result.status == CNavigationSearchStatus::Found && result.path.size() == 3,
                "large integer edge costs preserve a reachable path");
    expect_true(result.cost == static_cast<std::int64_t>(INT_MAX) * 3,
                "route totals use checked 64-bit arithmetic without wrapping");
    auto path = CPathFinder::findPath(start, goal, passable, noWaypoint, default_neighbors, zeroDistance, cost);
    expect_true(path.size() == 3 && path.back() == goal, "legacy path API preserves large-cost routes");
    auto next = CPathFinder::findNextStep(start, goal, passable, noWaypoint, default_neighbors, zeroDistance, cost);
    expect_true(next->get() == Coords(1, 0, 0), "legacy future returns the large-cost first step");
    auto competingNeighbors = [](Coords from) {
        if (from.x == 0)
            return std::vector<Coords>{{3, 0, 0}, {1, 0, 0}};
        if (from.x == 1)
            return std::vector<Coords>{{3, 0, 0}};
        return std::vector<Coords>{};
    };
    auto competingCost = [](Coords from, Coords to) {
        return from.x == 0 && to.x == 3 ? 1'600'000'000 : 1'500'000'000;
    };
    const auto cheapest =
        CPathFinder::findPath(start, goal, passable, noWaypoint, competingNeighbors, zeroDistance, competingCost);
    expect_true(cheapest == std::vector<Coords>{goal},
                "three-billion-cost detour cannot overflow into a cheaper route than the direct1.6billion edge");
    auto same = CPathFinder::findPath(start, start, passable, noWaypoint);
    expect_true(same == std::vector<Coords>{start}, "start equals goal keeps its legacy sentinel");
    const auto unreachable = CPathFinder::findPath(start, Coords(10, 0, 0), passable, noWaypoint);
    expect_true(unreachable == std::vector<Coords>{start}, "unreachable goal keeps its legacy sentinel");
}

void testDiscoveredGoalDoesNotEscapeLimits() {
    const Coords start(0, 0, 0), goal(3, 0, 0);
    auto passable = [](Coords c) { return c.y == 0 && c.z == 0 && c.x >= 0 && c.x <= 3; };
    auto neighbors = [](Coords c) {
        if (c.x == 0)
            return std::vector<Coords>{{3, 0, 0}, {1, 0, 0}};
        if (c.x == 1)
            return std::vector<Coords>{{2, 0, 0}};
        return std::vector<Coords>{};
    };
    auto cost = [](Coords, Coords to) { return to.x == 3 ? 100 : 1; };
    CNavigationSearchLimits limits;
    limits.maxExpansions = 1;
    auto result = CNavigationSearch::findGenericPath(start, goal, passable, noWaypoint, neighbors, zeroDistance, cost,
                                                     {}, limits);
    expect_true(result.status == CNavigationSearchStatus::ResourceLimit && result.path.empty() &&
                    result.firstStep == start && !result.allocationDenied,
                "budget exhaustion cannot expose the discovered but unsettled expensive goal");
    auto next = CNavigationSearch::findGenericNextStep(start, goal, passable, noWaypoint, neighbors, zeroDistance, cost,
                                                       {}, limits);
    expect_true(next.status == CNavigationSearchStatus::ResourceLimit && next.firstStep == start,
                "next-step failure agrees with full-route failure");
}

void testLongDetourNoEnvelope() {
    const Coords start(0, 0, 0), goal(1, 0, 0);
    auto passable = [](Coords c) { return c.z == 0 && c.x >= 0 && c.x <= 1 && c.y >= 0 && c.y <= 600; };
    auto neighbors = [](Coords c) {
        if (c.x == 0 && c.y < 600)
            return std::vector<Coords>{{0, c.y + 1, 0}};
        if (c.x == 0 && c.y == 600)
            return std::vector<Coords>{{1, 600, 0}};
        if (c.x == 1 && c.y > 0)
            return std::vector<Coords>{{1, c.y - 1, 0}};
        return std::vector<Coords>{};
    };
    auto path = CPathFinder::findPath(start, goal, passable, noWaypoint, neighbors, zeroDistance);
    expect_true(path.size() == 1201 && path.back() == goal,
                "a valid finite detour beyond the former 516-cell envelope remains reachable");
}

void testReopeningAndDecreaseKey() {
    const Coords start(0, 0, 0), goal(3, 0, 0);
    auto passable = [](Coords c) { return c.y == 0 && c.z == 0 && c.x >= 0 && c.x <= 3; };
    auto neighbors = [](Coords c) {
        if (c.x == 0)
            return std::vector<Coords>{{1, 0, 0}, {2, 0, 0}};
        if (c.x == 1)
            return std::vector<Coords>{{3, 0, 0}};
        if (c.x == 2)
            return std::vector<Coords>{{1, 0, 0}};
        return std::vector<Coords>{};
    };
    auto cost = [](Coords from, Coords to) {
        if (from.x == 0 && to.x == 1)
            return 3;
        return to.x == 3 ? 3 : 1;
    };
    auto distance = [](Coords from, Coords) { return from.x == 2 ? 4.0 : 0.0; };
    auto result = CNavigationSearch::findGenericPath(start, goal, passable, noWaypoint, neighbors, distance, cost);
    expect_true(result.status == CNavigationSearchStatus::Found && result.cost == 5 &&
                    result.firstStep == Coords(2, 0, 0),
                "admissible inconsistent heuristic reopens a settled intermediate node");
    expect_true(result.statistics.reopened == 1 && result.statistics.decreaseKeys >= 1,
                "reopening and in-place decrease-key are independently exercised");
}

void testPathLengthLimitAlsoBoundsNextStep() {
    const Coords start(0, 0, 0);
    const auto passable = [](Coords coords) {
        return coords.x >= 0 && coords.x <= 21 && coords.y == 0 && coords.z == 0;
    };
    const auto neighbors = [](Coords coords) {
        return coords.x < 21 ? std::vector<Coords>{Coords(coords.x + 1, 0, 0)} : std::vector<Coords>{};
    };
    CNavigationSearchLimits limits;
    limits.maxPathLength = 20;
    for (int length : {20, 21}) {
        auto full = CNavigationSearch::findGenericPath(start, Coords(length, 0, 0), passable, noWaypoint, neighbors,
                                                       zeroDistance, CPathFinder::DefaultStepCost{}, {}, limits);
        auto next = CNavigationSearch::findGenericNextStep(start, Coords(length, 0, 0), passable, noWaypoint, neighbors,
                                                           zeroDistance, CPathFinder::DefaultStepCost{}, {}, limits);
        expect_true(next.path.empty(), "next-step search does not reconstruct even a path at its length limit");
        if (length == 20) {
            expect_true(full.status == CNavigationSearchStatus::Found && full.path.size() == 20 && full.cost == 20 &&
                            next.status == CNavigationSearchStatus::Found && next.firstStep == Coords(1, 0, 0) &&
                            next.cost == 20,
                        "full and next-step routes succeed at the exact configured path length");
        } else {
            expect_true(full.status == CNavigationSearchStatus::ResourceLimit && full.path.empty() &&
                            !full.allocationDenied && next.status == CNavigationSearchStatus::ResourceLimit &&
                            next.firstStep == start && !next.allocationDenied,
                        "next-step propagation cannot bypass the full route's explicit path-length bound");
        }
    }
}

void testIndependentDijkstraOracle() {
    constexpr int count = 29;
    std::mt19937 random(271828);
    for (int trial = 0; trial < 24; ++trial) {
        std::array<std::vector<std::pair<int, int>>, count> edges;
        for (int from = 0; from < count; ++from) {
            for (int to = 0; to < count; ++to) {
                if (from != to && random() % 7 == 0)
                    edges[from].emplace_back(to, 1 + random() % 900);
            }
        }
        std::array<std::int64_t, count> costs;
        costs.fill(std::numeric_limits<std::int64_t>::max());
        costs[0] = 0;
        using Entry = std::pair<std::int64_t, int>;
        std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
        queue.emplace(0, 0);
        while (!queue.empty()) {
            auto [cost, from] = queue.top();
            queue.pop();
            if (cost != costs[from])
                continue;
            for (auto [to, weight] : edges[from]) {
                if (cost + weight < costs[to]) {
                    costs[to] = cost + weight;
                    queue.emplace(costs[to], to);
                }
            }
        }
        auto passable = [](Coords c) { return c.x >= 0 && c.x < count && c.y == 0 && c.z == 0; };
        auto neighbors = [&](Coords c) {
            std::vector<Coords> result;
            for (auto [to, weight] : edges[c.x]) {
                result.emplace_back(to, 0, 0);
                result.emplace_back(to, 0, 0);
            }
            return result;
        };
        auto edgeCost = [&](Coords from, Coords to) {
            for (auto [destination, cost] : edges[from.x])
                if (destination == to.x)
                    return cost;
            return INT_MAX;
        };
        const Coords start(0, 0, 0), goal(count - 1, 0, 0);
        auto actual =
            CNavigationSearch::findGenericPath(start, goal, passable, noWaypoint, neighbors, zeroDistance, edgeCost);
        auto first = CNavigationSearch::findGenericNextStep(start, goal, passable, noWaypoint, neighbors, zeroDistance,
                                                            edgeCost);
        if (costs.back() == std::numeric_limits<std::int64_t>::max()) {
            expect_true(actual.status == CNavigationSearchStatus::Unreachable && actual.path.empty(),
                        "seeded directed graph unreachable result matches independent Dijkstra");
        } else {
            expect_true(actual.status == CNavigationSearchStatus::Found && actual.cost == costs.back(),
                        "seeded weighted directed route cost matches independent Dijkstra");
            Coords previous = start;
            std::int64_t measured = 0;
            for (auto next : actual.path) {
                const auto cost = edgeCost(previous, next);
                expect_true(cost != INT_MAX, "oracle route consists exclusively of existing directed edges");
                measured += cost;
                previous = next;
            }
            expect_true(previous == goal && measured == actual.cost,
                        "oracle route reaches the goal with the reported authoritative cost");
            expect_true(first.status == actual.status && first.firstStep == actual.path.front() &&
                            first.cost == actual.cost,
                        "next-step search agrees with full-route search on seeded weighted graphs");
        }
    }
}

void testHardBudgetAndInvalidHeuristic() {
    const Coords start(0, 0, 0), goal(100, 0, 0);
    auto passable = [](Coords c) { return c.z == 0; };
    auto budget = std::make_shared<CNavigationBudget>(512);
    {
        auto result = CNavigationSearch::findGenericPath(start, goal, passable, noWaypoint, default_neighbors,
                                                         zeroDistance, CPathFinder::DefaultStepCost{}, budget);
        expect_true(result.status == CNavigationSearchStatus::ResourceLimit && result.path.empty() &&
                        result.allocationDenied,
                    "allocation denial produces a bounded failure instead of an exception or partial route");
        expect_true(budget->peak() <= budget->limit(), "allocator denial never exceeds the configured cap");
    }
    expect_true(budget->used() == 0, "generic failed search releases all charged scratch and result allocations");
    auto invalid =
        CNavigationSearch::findGenericPath(start, goal, passable, noWaypoint, default_neighbors,
                                           [](Coords, Coords) { return std::numeric_limits<double>::infinity(); });
    expect_true(invalid.status == CNavigationSearchStatus::InvalidInput && invalid.path.empty(),
                "nonfinite heuristics fail explicitly before integer conversion");
    const auto boundary = default_neighbors(Coords(INT_MAX, INT_MIN, 0));
    expect_true(boundary.size() == 2 && boundary[0] == Coords(INT_MAX - 1, INT_MIN, 0) &&
                    boundary[1] == Coords(INT_MAX, INT_MIN + 1, 0),
                "cardinal neighbors never overflow representable coordinates");
}

void testExactCapacityAndConcurrentIsolation() {
    const Coords start(-7, -4, -2), goal(-6, -4, -2);
    const auto passable = [=](Coords coords) { return coords == start || coords == goal; };
    const auto neighbors = [=](Coords coords) {
        return coords == start ? std::vector<Coords>{goal} : std::vector<Coords>{};
    };
    CNavigationSearchLimits limits;
    limits.maxRecords = 2;
    limits.maxExpansions = 1;
    auto exact = CNavigationSearch::findGenericPath(start, goal, passable, noWaypoint, neighbors, zeroDistance,
                                                    CPathFinder::DefaultStepCost{}, {}, limits);
    expect_true(exact.status == CNavigationSearchStatus::Found && exact.cost == 1 && exact.path.front() == goal,
                "a settled goal succeeds at the exact record and expansion limit with negative coordinates");
    auto budget = std::make_shared<CNavigationBudget>(4 * 1024 * 1024);
    {
        std::vector<std::future<CNavigationSearchResult>> pending;
        for (int level = 0; level < 8; ++level) {
            pending.push_back(std::async(std::launch::async, [budget, level]() {
                return CNavigationSearch::findGenericPath(
                    Coords(0, 0, level), Coords(63, 0, level),
                    [level](Coords c) { return c.x >= 0 && c.x <= 63 && c.y == 0 && c.z == level; }, noWaypoint,
                    default_neighbors, CPathFinder::DefaultDistance{}, CPathFinder::DefaultStepCost{}, budget);
            }));
        }
        for (int level = 0; level < 8; ++level) {
            auto result = pending[level].get();
            expect_true(result.status == CNavigationSearchStatus::Found && result.cost == 63 &&
                            result.firstStep == Coords(1, 0, level) && result.path.back() == Coords(63, 0, level),
                        "simultaneous requests share only the budget, never search records or first-step state");
        }
    }
    expect_true(budget->used() == 0 && budget->peak() <= budget->limit(),
                "concurrent requests release all scratch and collectively honor their shared cap");
}

struct MapFixture {
    std::shared_ptr<CGame> game;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CNavigationService> service;
};

MapFixture makeOpenMap(int size) {
    MapFixture result;
    result.game = CGameLoader::loadGame();
    result.map = std::make_shared<CMap>();
    result.game->setMap(result.map);
    result.map->setGame(result.game);
    result.map->setXBounds({{0, size - 1}});
    result.map->setYBounds({{0, size - 1}});
    result.map->setDefaultTiles({{0, "GrassTile"}});
    result.map->setOutOfBoundsTiles({{0, "MountainTile"}});
    result.service = CNavigationService::forMap(result.map);
    return result;
}

void testLargeMapLazyChunksAndWarmReuse() {
    auto fixture = makeOpenMap(1000);
    auto snapshot = fixture.service->snapshot(fixture.map);
    expect_true(snapshot && snapshot->isFinite(), "closed bounded map qualifies for indexed search");
    if (!snapshot || !snapshot->isFinite()) {
        auto handler = fixture.game->getObjectHandler();
        for (const auto *name : {"GrassTile", "MountainTile"}) {
            auto scalar = handler->getStaticTileNavigation(name);
            auto config = handler->getConfig(name);
            std::cout << "Navigation finite diagnostic: " << name << " scalar=";
            if (scalar)
                std::cout << scalar->first << ',' << scalar->second;
            else
                std::cout << "unavailable";
            std::cout << " config=" << (config ? config->dump() : "missing") << '\n';
        }
        auto native = CTypes::builders()->find("CTile");
        auto tile = handler->getType("CTile");
        std::cout << "Navigation tile diagnostic: nativeFactory="
                  << (native != CTypes::builders()->end() ? native->second.target_type().name() : "missing")
                  << " actualType=" << (tile ? typeid(*tile).name() : "missing") << '\n';
        return;
    }
    const auto tiles = fixture.map->getTiles().size();
    CNavigationSearchWorkspace workspace;
    {
        auto local = CNavigationSearch::findPath(snapshot, Coords(1, 1, 0), Coords(4, 1, 0), &workspace);
        expect_true(local.status == CNavigationSearchStatus::Found && local.cost == 3,
                    "short route on a million-cell map has exact cost");
        expect_true(local.statistics.chunkAllocations <= 2,
                    "short large-map route allocates only nearby 32x32 search chunks");
    }
    {
        auto cold = CNavigationSearch::findPath(snapshot, Coords(0, 0, 0), Coords(999, 999, 0), &workspace);
        expect_true(cold.status == CNavigationSearchStatus::Found && cold.cost == 1998 && cold.path.size() == 1998,
                    "million-cell open corner route has exact Manhattan cost");
        expect_true(cold.statistics.expansions <= 2 * (1998 + 1),
                    "deeper-g tie handling keeps open-corner expansions within the deterministic linear guard");
        auto warm = CNavigationSearch::findPath(snapshot, Coords(0, 0, 0), Coords(999, 999, 0), &workspace);
        expect_true(warm.status == CNavigationSearchStatus::Found && warm.cost == cold.cost &&
                        warm.statistics.chunkAllocations == 0,
                    "warm repeated route reuses generation-stamped chunks without per-cell allocation");
        expect_true(warm.statistics.expansions <= 2 * (1998 + 1), "warm route retains the expansion guard");
        std::cout << "Navigation corner: cost=" << cold.cost << " expansions=" << cold.statistics.expansions
                  << "/3998 coldChunks=" << cold.statistics.chunkAllocations
                  << " warmChunks=" << warm.statistics.chunkAllocations
                  << "/0 budgetPeak=" << fixture.service->budget()->peak() << "/" << fixture.service->budget()->limit()
                  << '\n';
    }
    expect_true(fixture.map->getTiles().size() == tiles, "scalar navigation reads never materialize default tiles");
    expect_true(fixture.service->budget()->peak() <= fixture.service->budget()->limit(),
                "map snapshots and search storage share the same hard session budget");
    fixture.map->setWrapX({{0, 1}});
    auto cancelled = CNavigationSearch::findPath(snapshot, Coords(0, 0, 0), Coords(999, 999, 0), &workspace);
    expect_true(cancelled.status == CNavigationSearchStatus::Cancelled && cancelled.path.empty(),
                "invalidated snapshot cannot publish a route after a topology change");
}
} // namespace

int main() {
    pybind11::scoped_interpreter guard{};
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    testLargeCostsAndFailureSentinels();
    testDiscoveredGoalDoesNotEscapeLimits();
    testLongDetourNoEnvelope();
    testReopeningAndDecreaseKey();
    testPathLengthLimitAlsoBoundsNextStep();
    testIndependentDijkstraOracle();
    testHardBudgetAndInvalidHeuristic();
    testExactCapacityAndConcurrentIsolation();
    testLargeMapLazyChunksAndWarmReuse();
    return finish_tests();
}
