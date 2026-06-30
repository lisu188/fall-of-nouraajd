/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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

#include "core/CPathFinder.h"
#include "core/CGame.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "test_harness.h"

#include <algorithm>
#include <cmath>
#include <memory>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct CallbackCounters {
    int canStep = 0;
    int neighbors = 0;
    int stepCost = 0;
    int waypoint = 0;
    int distance = 0;
    std::map<Coords, int> canStepByCoord;
};

bool bounded(const Coords &coords, int width, int height) {
    return coords.z == 0 && coords.x >= 0 && coords.x < width && coords.y >= 0 && coords.y < height;
}

std::optional<Coords> noWaypoint(CallbackCounters &counters, const Coords &) {
    ++counters.waypoint;
    return std::nullopt;
}

double manhattanDistance(CallbackCounters &counters, const Coords &from, const Coords &to) {
    ++counters.distance;
    return std::abs(from.x - to.x) + std::abs(from.y - to.y) + std::abs(from.z - to.z);
}

int countedUnitCost(CallbackCounters &counters, const Coords &, const Coords &) {
    ++counters.stepCost;
    return 1;
}

std::string metricMessage(const std::string &label, long long metric, long long baseline, long long threshold) {
    std::ostringstream stream;
    stream << label << " metric=" << metric << " baseline=" << baseline << " threshold=" << threshold;
    return stream.str();
}

void expectMetricAtMost(const std::string &label, long long metric, long long baseline, long long threshold) {
    const auto message = metricMessage(label, metric, baseline, threshold);
    expect_true(metric <= threshold, message.c_str());
}

void expectMetricEquals(const std::string &label, long long metric, long long expected) {
    const auto message = metricMessage(label, metric, expected, expected);
    expect_true(metric == expected, message.c_str());
}

void expectMetricInSet(const std::string &label, const Coords &metric, const std::set<Coords> &allowed) {
    std::ostringstream stream;
    stream << label << " metric=" << metric.x << "," << metric.y << "," << metric.z << " baseline=allowed-set"
           << " threshold=" << allowed.size();
    const auto message = stream.str();
    expect_true(allowed.contains(metric), message.c_str());
}

std::vector<Coords> countedDefaultNeighbors(CallbackCounters &counters, const Coords &coords) {
    ++counters.neighbors;
    return default_neighbors(coords);
}

void testLargeBoundedOpenGrid() {
    constexpr int width = 96;
    constexpr int height = 96;
    constexpr int expected_steps = width - 1;
    const Coords start(0, height / 2, 0);
    const Coords goal(width - 1, height / 2, 0);
    CallbackCounters counters;

    auto can_step = [&counters](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return bounded(coords, width, height);
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expectMetricEquals("open-grid path length", static_cast<long long>(path.size()), expected_steps);
    expect_true(!path.empty() && path.front() == Coords(1, height / 2, 0),
                "open-grid first step metric=1 baseline=1 threshold=1");
    expect_true(!path.empty() && path.back() == goal, "open-grid goal metric=1 baseline=1 threshold=1");
    expectMetricAtMost("open-grid neighbor calls", counters.neighbors, expected_steps, expected_steps + 1);
    expectMetricAtMost("open-grid waypoint calls", counters.waypoint, expected_steps, expected_steps + 1);
    expectMetricAtMost("open-grid canStep calls", counters.canStep, expected_steps * 3, expected_steps * 4);
    expectMetricAtMost("open-grid stepCost calls", counters.stepCost, expected_steps * 3, expected_steps * 4);
    expectMetricAtMost("open-grid distance calls", counters.distance, expected_steps * 3, expected_steps * 4);
}

std::set<Coords> makeSnakeCorridor(int width, int rows) {
    std::set<Coords> open;
    for (int row = 0; row < rows; ++row) {
        const int y = row * 2;
        for (int x = 0; x < width; ++x) {
            open.insert(Coords(x, y, 0));
        }
        if (row + 1 < rows) {
            open.insert(Coords(row % 2 == 0 ? width - 1 : 0, y + 1, 0));
        }
    }
    return open;
}

void testCorridorMazeBound() {
    constexpr int width = 24;
    constexpr int rows = 12;
    constexpr int height = rows * 2 - 1;
    constexpr int expected_steps = (width - 1) * rows + (rows - 1) * 2;
    constexpr int total_cells = width * height;
    const auto open = makeSnakeCorridor(width, rows);
    const Coords start(0, 0, 0);
    const Coords goal(0, height - 1, 0);
    CallbackCounters counters;

    auto can_step = [&counters, &open](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return open.contains(coords);
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expectMetricEquals("corridor path length", static_cast<long long>(path.size()), expected_steps);
    expect_true(!path.empty() && path.front() == Coords(1, 0, 0),
                "corridor first step metric=1 baseline=1 threshold=1");
    expect_true(!path.empty() && path.back() == goal, "corridor goal metric=1 baseline=1 threshold=1");
    expectMetricAtMost("corridor neighbor calls", counters.neighbors, expected_steps, expected_steps + 1);
    expectMetricAtMost("corridor waypoint calls", counters.waypoint, expected_steps, expected_steps + 1);
    expectMetricAtMost("corridor canStep calls", counters.canStep, total_cells, total_cells + width * 2 + height * 2);
    expectMetricAtMost("corridor stepCost calls", counters.stepCost, expected_steps * 2, expected_steps * 3);
}

void testUnreachableBoundedGoal() {
    constexpr int width = 50;
    constexpr int height = 40;
    constexpr int wall_x = 25;
    constexpr int reachable_cells = wall_x * height;
    const Coords start(0, height / 2, 0);
    const Coords goal(width - 1, height / 2, 0);
    CallbackCounters counters;

    auto can_step = [&counters, goal](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return coords == goal || (bounded(coords, width, height) && coords.x < wall_x);
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expectMetricEquals("unreachable path length", static_cast<long long>(path.size()), 1);
    expect_true(!path.empty() && path.front() == start,
                "unreachable path returns start metric=1 baseline=1 threshold=1");
    expectMetricAtMost("unreachable neighbor calls", counters.neighbors, reachable_cells, reachable_cells);
    expectMetricAtMost("unreachable waypoint calls", counters.waypoint, reachable_cells, reachable_cells);
    expectMetricAtMost("unreachable canStep calls", counters.canStep, reachable_cells, reachable_cells + height + 100);
    expectMetricAtMost("unreachable stepCost calls", counters.stepCost, reachable_cells * 4, reachable_cells * 5);
}

void testWeightedCheapestBeatsShortest() {
    const Coords start(0, 0, 0);
    const Coords goal(4, 0, 0);
    const std::set<Coords> allowed{
        start,           Coords(1, 0, 0), Coords(2, 0, 0), Coords(3, 0, 0), goal,
        Coords(0, 1, 0), Coords(1, 1, 0), Coords(2, 1, 0), Coords(3, 1, 0), Coords(4, 1, 0),
    };
    const std::map<Coords, std::vector<Coords>> graph{
        {start, {Coords(1, 0, 0), Coords(0, 1, 0)}},
        {Coords(1, 0, 0), {Coords(2, 0, 0)}},
        {Coords(2, 0, 0), {Coords(3, 0, 0)}},
        {Coords(3, 0, 0), {goal}},
        {Coords(0, 1, 0), {Coords(1, 1, 0)}},
        {Coords(1, 1, 0), {Coords(2, 1, 0)}},
        {Coords(2, 1, 0), {Coords(3, 1, 0)}},
        {Coords(3, 1, 0), {Coords(4, 1, 0)}},
        {Coords(4, 1, 0), {goal}},
    };
    CallbackCounters counters;

    auto can_step = [&counters, &allowed](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return allowed.contains(coords);
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters, &graph](const Coords &coords) {
        ++counters.neighbors;
        auto entry = graph.find(coords);
        return entry == graph.end() ? std::vector<Coords>{} : entry->second;
    };
    auto distance = [&counters](const Coords &, const Coords &) {
        ++counters.distance;
        return 0.0;
    };
    auto step_cost = [&counters](const Coords &from, const Coords &to) {
        ++counters.stepCost;
        if (from == Coords(1, 0, 0) && to == Coords(2, 0, 0)) {
            return 30;
        }
        return 1;
    };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);
    const std::vector<Coords> expected_path{
        Coords(0, 1, 0), Coords(1, 1, 0), Coords(2, 1, 0), Coords(3, 1, 0), Coords(4, 1, 0), goal,
    };

    expectMetricEquals("weighted path length", static_cast<long long>(path.size()),
                       static_cast<long long>(expected_path.size()));
    expect_true(path == expected_path, "weighted cheapest path metric=6 baseline=6 threshold=6");
    expectMetricAtMost("weighted neighbor calls", counters.neighbors, static_cast<long long>(allowed.size()),
                       static_cast<long long>(allowed.size()));
    expectMetricAtMost("weighted canStep calls", counters.canStep, static_cast<long long>(allowed.size()),
                       static_cast<long long>(allowed.size()));
    expectMetricAtMost("weighted stepCost calls", counters.stepCost, 10, 20);
}

void testDuplicateNeighborPassabilityCaching() {
    constexpr int duplicate_count = 32;
    const Coords start(0, 0, 0);
    const Coords goal(4, 0, 0);
    const std::set<Coords> allowed{start, Coords(1, 0, 0), Coords(2, 0, 0), Coords(3, 0, 0), goal};
    CallbackCounters counters;

    auto can_step = [&counters, &allowed](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return allowed.contains(coords);
    };
    auto waypoint = [&counters, goal](const Coords &coords) -> std::optional<Coords> {
        ++counters.waypoint;
        if (coords.x >= 0 && coords.x < goal.x) {
            return Coords(coords.x + 1, 0, 0);
        }
        return std::nullopt;
    };
    auto neighbors = [&counters, goal](const Coords &coords) {
        ++counters.neighbors;
        std::vector<Coords> values;
        if (coords.x >= 0 && coords.x < goal.x) {
            const Coords next(coords.x + 1, 0, 0);
            const Coords blocked(coords.x + 1, 1, 0);
            values.reserve(duplicate_count * 2);
            for (int i = 0; i < duplicate_count; ++i) {
                values.push_back(next);
                values.push_back(blocked);
            }
        }
        return values;
    };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expectMetricEquals("duplicate-neighbor path length", static_cast<long long>(path.size()), goal.x);
    expect_true(!path.empty() && path.back() == goal, "duplicate-neighbor goal metric=1 baseline=1 threshold=1");
    expectMetricEquals("duplicate-neighbor passable cache hits for x1", counters.canStepByCoord[Coords(1, 0, 0)], 1);
    expectMetricEquals("duplicate-neighbor blocked cache hits for x1", counters.canStepByCoord[Coords(1, 1, 0)], 1);
    expectMetricEquals("duplicate-neighbor goal cache hits", counters.canStepByCoord[goal], 1);
    expectMetricAtMost("duplicate-neighbor total canStep calls", counters.canStep, 8, 9);
    expectMetricAtMost("duplicate-neighbor neighbor calls", counters.neighbors, goal.x, goal.x);
    expectMetricAtMost("duplicate-neighbor waypoint calls", counters.waypoint, goal.x, goal.x);
    expectMetricAtMost("duplicate-neighbor stepCost calls", counters.stepCost, duplicate_count * goal.x,
                       duplicate_count * goal.x + goal.x);
}

void testWaypointShortcutBound() {
    constexpr int width = 12;
    const Coords start(0, 0, 0);
    const Coords goal(width - 1, 0, 0);
    CallbackCounters counters;

    auto can_step = [&counters](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return coords.z == 0 && coords.y == 0 && coords.x >= 0 && coords.x < width;
    };
    auto waypoint = [&counters, goal](const Coords &coords) -> std::optional<Coords> {
        ++counters.waypoint;
        if (coords.x >= 0 && coords.x < goal.x) {
            return Coords(coords.x + 1, 0, 0);
        }
        return std::nullopt;
    };
    auto neighbors = [&counters](const Coords &) {
        ++counters.neighbors;
        return std::vector<Coords>{};
    };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expectMetricEquals("waypoint path length", static_cast<long long>(path.size()), goal.x);
    expect_true(!path.empty() && path.front() == Coords(1, 0, 0),
                "waypoint first step metric=1 baseline=1 threshold=1");
    expect_true(!path.empty() && path.back() == goal, "waypoint goal metric=1 baseline=1 threshold=1");
    expectMetricEquals("waypoint neighbor calls", counters.neighbors, goal.x);
    expectMetricEquals("waypoint calls", counters.waypoint, goal.x);
    expectMetricAtMost("waypoint canStep calls", counters.canStep, goal.x, goal.x + 1);
    expectMetricEquals("waypoint stepCost calls", counters.stepCost, goal.x);
}

int wrapAxis(int value, int bound) {
    const int size = bound + 1;
    int normalized = value % size;
    if (normalized < 0) {
        normalized += size;
    }
    return normalized;
}

Coords normalizeToroidal(Coords coords, int x_bound, int y_bound) {
    return Coords(wrapAxis(coords.x, x_bound), wrapAxis(coords.y, y_bound), coords.z);
}

std::vector<Coords> toroidalNeighbors(CallbackCounters &counters, const Coords &coords, int x_bound, int y_bound) {
    ++counters.neighbors;
    std::set<Coords> unique;
    for (const auto &neighbor : default_neighbors(coords)) {
        unique.insert(normalizeToroidal(neighbor, x_bound, y_bound));
    }
    return {unique.begin(), unique.end()};
}

double toroidalDistance(CallbackCounters &counters, const Coords &from, const Coords &to, int x_bound, int y_bound) {
    ++counters.distance;
    const int width = x_bound + 1;
    const int height = y_bound + 1;
    int dx = std::abs(from.x - to.x);
    int dy = std::abs(from.y - to.y);
    dx = std::min(dx, width - dx);
    dy = std::min(dy, height - dy);
    return std::sqrt(dx * dx + dy * dy);
}

void testToroidalNeighborDistanceBehavior() {
    constexpr int x_bound = 31;
    constexpr int y_bound = 31;
    const Coords start(0, 0, 0);
    const Coords goal(31, 31, 0);
    CallbackCounters counters;

    auto can_step = [&counters](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return coords.z == 0;
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) {
        return toroidalNeighbors(counters, coords, x_bound, y_bound);
    };
    auto distance = [&counters](const Coords &from, const Coords &to) {
        return toroidalDistance(counters, from, to, x_bound, y_bound);
    };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expectMetricEquals("toroidal path length", static_cast<long long>(path.size()), 2);
    if (!path.empty()) {
        expectMetricInSet("toroidal first step", path.front(), {Coords(31, 0, 0), Coords(0, 31, 0)});
    } else {
        expect_true(false, "toroidal first step metric=0 baseline=2 threshold=2");
    }
    expect_true(!path.empty() && path.back() == goal, "toroidal goal metric=1 baseline=1 threshold=1");
    expectMetricAtMost("toroidal neighbor calls", counters.neighbors, 2, 3);
    expectMetricAtMost("toroidal waypoint calls", counters.waypoint, 2, 3);
    expectMetricAtMost("toroidal canStep calls", counters.canStep, 8, 10);
    expectMetricAtMost("toroidal stepCost calls", counters.stepCost, 8, 12);
    expectMetricAtMost("toroidal distance calls", counters.distance, 8, 12);
}

void testRepeatedAsyncFindNextStep() {
    constexpr int repetitions = 32;
    constexpr int width = 14;
    constexpr int expected_step_count = width - 1;
    const Coords start(0, 0, 0);
    const Coords goal(width - 1, 0, 0);
    CallbackCounters counters;

    auto can_step = [&counters](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return coords.z == 0 && coords.y == 0 && coords.x >= 0 && coords.x < width;
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    for (int i = 0; i < repetitions; ++i) {
        const auto next_step =
            CPathFinder::findNextStep(start, goal, can_step, waypoint, neighbors, distance, step_cost);
        expect_true(next_step->get() == Coords(1, 0, 0), "async next step metric=1 baseline=1 threshold=1");
    }

    expectMetricAtMost("async neighbor calls", counters.neighbors, repetitions * expected_step_count,
                       repetitions * (expected_step_count + 1));
    expectMetricAtMost("async waypoint calls", counters.waypoint, repetitions * expected_step_count,
                       repetitions * (expected_step_count + 1));
    expectMetricAtMost("async canStep calls", counters.canStep, repetitions * expected_step_count * 3,
                       repetitions * expected_step_count * 4);
    expectMetricAtMost("async stepCost calls", counters.stepCost, repetitions * expected_step_count * 2,
                       repetitions * expected_step_count * 3);
    expectMetricAtMost("async distance calls", counters.distance, repetitions * expected_step_count * 3,
                       repetitions * expected_step_count * 4);
}

struct ScalingMetrics {
    int size;
    int canStep;
    int neighbors;
    int stepCost;
    int distance;
    int pathLength;
};

ScalingMetrics runScalingCase(int size) {
    const Coords start(0, size / 2, 0);
    const Coords goal(size - 1, size / 2, 0);
    CallbackCounters counters;

    auto can_step = [&counters, size](const Coords &coords) {
        ++counters.canStep;
        return bounded(coords, size, size);
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);
    return {size,
            counters.canStep,
            counters.neighbors,
            counters.stepCost,
            counters.distance,
            static_cast<int>(path.size())};
}

void testMultiSizeScaling() {
    const auto small = runScalingCase(16);
    const auto medium = runScalingCase(32);
    const auto large = runScalingCase(48);

    expectMetricEquals("scaling small path length", small.pathLength, small.size - 1);
    expectMetricEquals("scaling medium path length", medium.pathLength, medium.size - 1);
    expectMetricEquals("scaling large path length", large.pathLength, large.size - 1);

    expectMetricAtMost("scaling small neighbor calls", small.neighbors, small.size, small.size);
    expectMetricAtMost("scaling medium neighbor calls", medium.neighbors, medium.size, medium.size);
    expectMetricAtMost("scaling large neighbor calls", large.neighbors, large.size, large.size);
    expectMetricAtMost("scaling large-vs-small neighbors", large.neighbors, small.neighbors * 3,
                       small.neighbors * 3 + large.size / 2);
    expectMetricAtMost("scaling large-vs-small canStep", large.canStep, small.canStep * 3,
                       small.canStep * 3 + large.size);
    expectMetricAtMost("scaling large-vs-small stepCost", large.stepCost, small.stepCost * 3,
                       small.stepCost * 3 + large.size);
    expectMetricAtMost("scaling large-vs-small distance", large.distance, small.distance * 3,
                       small.distance * 3 + large.size);
}

void testMapMovementCostLookupDoesNotMaterializeSparseDefaultTiles() {
    constexpr int size = 64;
    constexpr int expected_steps = (size - 1) * 2;
    auto game = CGameLoader::loadGame();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, size - 1}});
    map->setYBounds({{0, size - 1}});
    map->setDefaultTiles({{0, "GrassTile"}});
    map->setOutOfBoundsTiles({{0, "MountainTile"}});

    const auto initial_tile_count = map->getTiles().size();
    const auto initial_navigation_revision = map->getNavigationRevision();
    const Coords start(0, 0, 0);
    const Coords goal(size - 1, size - 1, 0);

    auto can_step = [map](const Coords &coords) { return map->canStep(coords); };
    auto waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };
    auto neighbors = [map](const Coords &coords) { return map->getNavigationNeighbors(coords); };
    auto distance = [map](const Coords &from, const Coords &to) { return map->getDistance(from, to); };
    auto step_cost = [map](const Coords &, const Coords &to) { return map->lookupMovementCost(to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expectMetricEquals("sparse-map path length", static_cast<long long>(path.size()), expected_steps);
    expect_true(!path.empty() && path.front() != start, "sparse-map path should advance from the start");
    expect_true(!path.empty() && path.back() == goal, "sparse-map path should reach the goal");
    expectMetricEquals("sparse-map materialized tile count", static_cast<long long>(map->getTiles().size()),
                       static_cast<long long>(initial_tile_count));
    expectMetricEquals("sparse-map navigation revision", static_cast<long long>(map->getNavigationRevision()),
                       static_cast<long long>(initial_navigation_revision));
}

void testEnvelopeBudgetBoundsUnreachableGoalInOpenPlane() {
    // Models a request against a sparse / effectively unbounded map: the goal is passable but sealed
    // off by an impassable ring, while every other coordinate on the plane is open. Without an
    // envelope budget the A* frontier would flood the open complement outward from the start
    // indefinitely (capped only by the 1,000,000-node ceiling). The goal-relative envelope keeps the
    // explored region proportional to the start->goal span, so the search fails safely after
    // exploring a bounded neighborhood.
    const Coords start(0, 0, 0);
    const Coords goal(64, 0, 0);
    CallbackCounters counters;

    auto can_step = [&counters, goal](const Coords &coords) {
        ++counters.canStep;
        if (coords.z != 0) {
            return false;
        }
        // Impassable ring (Chebyshev radius 3) seals the otherwise-passable goal so the frontier can
        // never reach it; nothing but the envelope bounds the outward expansion.
        const int chebyshev = std::max(std::abs(coords.x - goal.x), std::abs(coords.y - goal.y));
        return chebyshev != 3;
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    // Goal is impassable, so the pathfinder fails safely with just the start.
    expectMetricEquals("envelope open-plane path length", static_cast<long long>(path.size()), 1);
    expect_true(!path.empty() && path.front() == start,
                "envelope open-plane path returns start metric=1 baseline=1 threshold=1");
    // The explored frontier is bounded by the envelope (4 * manhattan(start, goal) + 256 = 512 here),
    // which limits coordinates to a finite disc; the resulting canStep calls stay far below the
    // 1,000,000-node visit ceiling, proving the envelope (not the global cap) bounded the search.
    const long long envelope = 4 * (std::abs(goal.x - start.x) + std::abs(goal.y - start.y)) + 256;
    // Upper bound on distinct probed coordinates: the L1 disc of radius (envelope + 1) (one ring of
    // out-of-envelope neighbors may still be probed before being discarded).
    const long long radius = envelope + 1;
    const long long max_cells = 2 * radius * radius + 2 * radius + 1;
    expectMetricAtMost("envelope open-plane canStep calls", counters.canStep, max_cells, max_cells);
    expect_true(counters.canStep < 1'000'000,
                "envelope open-plane stays below global node cap metric=1 baseline=1 threshold=1");
}

void testEnvelopeBudgetPreservesReachableNavigation() {
    // A legitimate goal that requires a detour around a wall must still be found: the envelope is
    // generous relative to the start->goal separation, so normal navigation is unaffected.
    constexpr int width = 40;
    constexpr int height = 40;
    constexpr int wall_x = 20;
    constexpr int gap_y = height - 1;
    const Coords start(0, 0, 0);
    const Coords goal(width - 1, 0, 0);
    CallbackCounters counters;

    auto can_step = [&counters](const Coords &coords) {
        ++counters.canStep;
        if (!bounded(coords, width, height)) {
            return false;
        }
        // Vertical wall at wall_x with a single gap at the far edge forces a long but bounded detour.
        return !(coords.x == wall_x && coords.y != gap_y);
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expect_true(!path.empty() && path.back() == goal, "envelope detour reaches goal metric=1 baseline=1 threshold=1");
    expect_true(path.size() > static_cast<std::size_t>(width),
                "envelope detour path is longer than the direct distance metric=1 baseline=1 threshold=1");
}

} // namespace

void run_pathfinder_performance_tests() {
    testEnvelopeBudgetBoundsUnreachableGoalInOpenPlane();
    testEnvelopeBudgetPreservesReachableNavigation();
    testLargeBoundedOpenGrid();
    testCorridorMazeBound();
    testUnreachableBoundedGoal();
    testWeightedCheapestBeatsShortest();
    testDuplicateNeighborPassabilityCaching();
    testWaypointShortcutBound();
    testToroidalNeighborDistanceBehavior();
    testRepeatedAsyncFindNextStep();
    testMultiSizeScaling();
    testMapMovementCostLookupDoesNotMaterializeSparseDefaultTiles();
}
