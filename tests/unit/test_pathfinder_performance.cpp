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

#include "core/CAsync.h"
#include "core/CPathFinder.h"
#include "core/CNavigation.h"
#include "core/CNavigationSearch.h"
#include "core/CGame.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CGameContext.h"
#include "core/CSerialization.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "handler/CObjectHandler.h"
#include "object/CTile.h"
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

vstd::task<void> countedCoroutine(int &started, int &resumed, int &destroyed) {
    struct FrameGuard {
        int &destroyed;
        ~FrameGuard() { ++destroyed; }
    } guard{destroyed};
    ++started;
    co_await vstd::post(vstd::event_loop<>::instance());
    ++resumed;
}

void testCoroutineDispatchAndFrameBudgets() {
    constexpr int task_count = 256;
    auto loop = vstd::event_loop<>::instance();
    loop->runUntilIdle();
    vstd::task_group group;
    int started = 0, resumed = 0, destroyed = 0;
    std::vector<vstd::task_handle<void>> handles;
    handles.reserve(task_count);
    const auto initial_pending = loop->getPendingTaskCount();
    for (int index = 0; index < task_count; ++index) {
        handles.push_back(group.spawn(countedCoroutine(started, resumed, destroyed), vstd::loopScheduler(loop)));
    }
    expectMetricEquals("coroutine inline starts", started, task_count);
    expectMetricEquals("coroutine pending dispatches", loop->getPendingTaskCount() - initial_pending, task_count);
    expect_true(!group.finished(), "posted coroutine frames remain active before their dispatch batch");
    loop->runPostedTasks();
    expectMetricEquals("coroutine resumptions", resumed, task_count);
    expectMetricEquals("coroutine destroyed frames", destroyed, task_count);
    expect_true(group.finished() && group.join(), "one posted batch completes and releases every bounded task frame");
    for (const auto &handle : handles) {
        handle.get();
    }
    std::cout << "coroutine guard tasks=" << task_count << " starts=" << started << " resumes=" << resumed
              << " framesDestroyed=" << destroyed << '\n';
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
        auto next_step =
            CPathFinder::findNextStepAsync(start, goal, can_step, waypoint, neighbors, distance, step_cost);
        expect_true(game_async::run(std::move(next_step), game_async::WaitMode::PostedWork) == Coords(1, 0, 0),
                    "async next step metric=1 baseline=1 threshold=1");
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

void testExplicitBudgetBoundsUnreachableGoalInOpenPlane() {
    // A geometric envelope rejected legitimate detours. Exercise explicit finite work/storage
    // limits instead: the passable goal is enclosed, while the rest of this graph is unbounded.
    const Coords start(0, 0, 0);
    const Coords goal(32, 0, 0);
    CallbackCounters counters;
    auto can_step = [&](const Coords &coords) {
        ++counters.canStep;
        return coords.z == 0 && std::max(std::abs(coords.x - goal.x), std::abs(coords.y - goal.y)) != 3;
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters](const Coords &coords) { return countedDefaultNeighbors(counters, coords); };
    auto distance = [&counters](const Coords &from, const Coords &to) { return manhattanDistance(counters, from, to); };
    auto step_cost = [&counters](const Coords &from, const Coords &to) { return countedUnitCost(counters, from, to); };
    CNavigationSearchLimits limits;
    limits.maxRecords = 60'000;
    limits.maxExpansions = 60'000;
    auto budget = std::make_shared<CNavigationBudget>(8 * 1024 * 1024);
    const auto result = CNavigationSearch::findGenericPath(start, goal, can_step, waypoint, neighbors, distance,
                                                           step_cost, budget, limits);
    expect_true(result.status == CNavigationSearchStatus::ResourceLimit && result.path.empty() &&
                    result.firstStep == start,
                "unbounded unreachable graph fails closed at an explicit resource limit");
    expectMetricAtMost("unbounded passability work", counters.canStep, 60'000, 60'000);
    expectMetricAtMost("unbounded discovered records", result.statistics.records, 60'000, 60'000);
    expectMetricAtMost("unbounded expansions", result.statistics.expansions, 60'000, 60'000);
    expectMetricAtMost("unbounded charged bytes", budget->peak(), 8 * 1024 * 1024, 8 * 1024 * 1024);
    expect_true(budget->used() == 0, "failed unbounded search releases all allocated scratch");
    std::cout << "Navigation unbounded: records=" << result.statistics.records
              << "/60000 expansions=" << result.statistics.expansions << "/60000 bytes=" << budget->peak()
              << "/8388608\n";
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

std::shared_ptr<CTile> makeWeightedTile(const std::shared_ptr<CGame> &game, int movementCost) {
    auto tile = std::make_shared<CTile>();
    tile->setGame(game);
    tile->setCanStep(true);
    tile->setTileType("weightedTile");
    tile->setMovementCost(movementCost);
    return tile;
}

// Builds a fully materialized width x height open map whose row-0 band [bandStartX, bandEndX] carries
// the supplied (expensive) movement cost; every other tile has cost 1. Returns the game so callers keep
// the shared owners alive while the map is in use.
std::shared_ptr<CGame> buildWeightedBandMap(int width, int height, int bandStartX, int bandEndX, int bandCost,
                                            std::shared_ptr<CMap> &outMap) {
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, width - 1}});
    map->setYBounds({{0, height - 1}});
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const bool inBand = (y == 0 && x >= bandStartX && x <= bandEndX);
            map->addTile(makeWeightedTile(game, inBand ? bandCost : 1), x, y, 0);
        }
    }
    outMap = map;
    return game;
}

// Regression: pin the concrete movement-cost values the CMap / CTile API produces, including the
// documented std::max(1, ...) floor, the default-cost-1 for unmaterialized coordinates, and the fact
// that findPath fed with CMap::lookupMovementCost as its StepCost deterministically routes around an
// expensive band instead of crossing it.
void testMapMovementCostRegressionPinsTileWeightsAndRouting() {
    constexpr int width = 6;
    constexpr int height = 3;
    constexpr int band_cost = 30;
    std::shared_ptr<CMap> map;
    [[maybe_unused]] auto game = buildWeightedBandMap(width, height, 1, width - 2, band_cost, map);

    // Per-tile weights are pinned exactly through both the materializing and lookup accessors.
    expectMetricEquals("regression default tile cost", static_cast<long long>(map->getMovementCost(0, 0, 0)), 1);
    expectMetricEquals("regression band tile cost", static_cast<long long>(map->getMovementCost(2, 0, 0)), band_cost);
    expectMetricEquals("regression lookup band tile cost",
                       static_cast<long long>(map->lookupMovementCost(Coords(3, 0, 0))), band_cost);
    expectMetricEquals("regression off-band tile cost", static_cast<long long>(map->getMovementCost(Coords(2, 1, 0))),
                       1);

    // The std::max(1, ...) floor: a tile configured below 1 still reports 1.
    if (auto tile = map->getTile(Coords(0, 0, 0))) {
        tile->setMovementCost(-5);
        expectMetricEquals("regression movement-cost floor clamps to 1",
                           static_cast<long long>(map->getMovementCost(0, 0, 0)), 1);
        tile->setMovementCost(1);
    } else {
        expect_true(false, "regression expected a materialized tile at the origin");
    }

    // Deterministic routing: with lookupMovementCost as the StepCost, the cheapest path leaves row 0,
    // crosses on the cheap rows, and rejoins at the goal rather than paying the expensive band.
    const Coords start(0, 0, 0);
    const Coords goal(width - 1, 0, 0);
    auto can_step = [map](const Coords &coords) { return map->canStep(coords); };
    auto waypoint = [](const Coords &) -> std::optional<Coords> { return std::nullopt; };
    auto neighbors = [map](const Coords &coords) { return map->getNavigationNeighbors(coords); };
    auto distance = [map](const Coords &from, const Coords &to) { return map->getDistance(from, to); };
    auto step_cost = [map](const Coords &from, const Coords &to) { return map->lookupMovementCost(to); };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expect_true(!path.empty() && path.back() == goal,
                "regression weighted path reaches goal metric=1 baseline=1 threshold=1");
    expect_true(!path.empty() && path.front() != Coords(1, 0, 0),
                "regression weighted path does not step onto the expensive band first");
    // Sum the StepCost over the produced path and confirm it is far below the cost of plowing straight
    // through the band ((width - 2) expensive crossings would cost ~ (width - 2) * band_cost).
    long long traversed_cost = 0;
    for (const auto &cell : path) {
        traversed_cost += map->lookupMovementCost(cell);
    }
    const long long straight_band_cost = static_cast<long long>(width - 2) * band_cost;
    expect_true(traversed_cost < straight_band_cost,
                "regression detour total cost is cheaper than crossing the band metric=1 baseline=1 threshold=1");
    // No path cell sits inside the expensive interior band (x in [1, width-2]) on row 0.
    bool crosses_band = false;
    for (const auto &cell : path) {
        if (cell.z == 0 && cell.y == 0 && cell.x >= 1 && cell.x <= width - 2) {
            crosses_band = true;
        }
    }
    expect_true(!crosses_band, "regression path avoids the expensive interior band metric=1 baseline=1 threshold=1");
}

// Bounded performance guard: running findPath with the real CMap::lookupMovementCost StepCost across a
// larger weighted map must keep its probing work within a generous, deterministic ceiling. This mirrors
// the call-count work-bound idiom used throughout this file (no wall-clock timing, so it is stable on
// shared CI runners) while exercising the movement-cost path consumers end to end.
void testMovementCostPathStaysWithinWorkBound() {
    constexpr int width = 64;
    constexpr int height = 16;
    constexpr int band_cost = 50;
    constexpr int total_cells = width * height;
    std::shared_ptr<CMap> map;
    [[maybe_unused]] auto game = buildWeightedBandMap(width, height, 1, width - 2, band_cost, map);

    const Coords start(0, 0, 0);
    const Coords goal(width - 1, 0, 0);

    CallbackCounters counters;
    auto can_step = [&counters, map](const Coords &coords) {
        ++counters.canStep;
        ++counters.canStepByCoord[coords];
        return map->canStep(coords);
    };
    auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
    auto neighbors = [&counters, map](const Coords &coords) {
        ++counters.neighbors;
        return map->getNavigationNeighbors(coords);
    };
    auto distance = [&counters, map](const Coords &from, const Coords &to) {
        ++counters.distance;
        return map->getDistance(from, to);
    };
    auto step_cost = [&counters, map](const Coords &, const Coords &to) {
        ++counters.stepCost;
        return map->lookupMovementCost(to);
    };

    const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);

    expect_true(!path.empty() && path.back() == goal,
                "perf-bound weighted path reaches goal metric=1 baseline=1 threshold=1");
    // A* over a band-weighted plane only explores a neighborhood proportional to the map; bound the work
    // generously at a small multiple of the materialized cell count so the guard is not flaky but still
    // catches a regression that floods the frontier.
    expectMetricAtMost("perf-bound canStep calls", counters.canStep, total_cells * 4, total_cells * 8);
    expectMetricAtMost("perf-bound stepCost calls", counters.stepCost, total_cells * 4, total_cells * 8);
    expectMetricAtMost("perf-bound neighbor calls", counters.neighbors, total_cells, total_cells * 4);
    expectMetricAtMost("perf-bound distance calls", counters.distance, total_cells * 4, total_cells * 8);
    expect_true(counters.canStep < 1'000'000, "perf-bound stays below global node cap metric=1 baseline=1 threshold=1");
}

void testMapHeuristicPreservesPortalRoutesAndOrdinarySearchWork() {
    constexpr int width = 96;
    const Coords start(0, 0, 0);
    const Coords goal(width - 1, 0, 0);
    for (const int edge_state : {0, 1, 2}) {
        const bool enabled = edge_state == 2;
        auto game = std::make_shared<CGame>();
        auto map = std::make_shared<CMap>();
        game->setMap(map);
        map->setGame(game);
        map->setXBounds({{0, width - 1}});
        map->setYBounds({{0, 1}});
        for (int x = 0; x < width; ++x)
            map->addTile(makeWeightedTile(game, 1), x, 0, 0);
        map->addTile(makeWeightedTile(game, 1), 0, 1, 0);
        if (edge_state != 0)
            map->registerNavigationEdge({Coords(0, 1, 0), Coords(width - 2, 0, 0), enabled});
        const auto heuristic = CPathFinder::mapHeuristic(map);
        expectMetricEquals("map heuristic lower bound", static_cast<long long>(heuristic(start, goal)),
                           enabled ? 0 : width - 1);
        CallbackCounters counters;
        auto can_step = [&counters, map](const Coords &coords) {
            ++counters.canStep;
            return map->canStep(coords);
        };
        auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
        auto neighbors = [&counters, map](const Coords &coords) {
            ++counters.neighbors;
            return map->getNavigationNeighbors(coords);
        };
        auto distance = [&counters, &heuristic](const Coords &from, const Coords &to) {
            ++counters.distance;
            return heuristic(from, to);
        };
        auto step_cost = [&counters, map](const Coords &, const Coords &to) {
            ++counters.stepCost;
            return map->lookupMovementCost(to);
        };
        const auto path = CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, distance, step_cost);
        const std::string label = enabled ? "portal-map" : edge_state == 0 ? "ordinary-map" : "disabled-portal-map";
        const int expected_steps = enabled ? 3 : width - 1;
        expectMetricEquals(label + " path length", static_cast<long long>(path.size()), expected_steps);
        expect_true(!path.empty() && path.front() == (enabled ? Coords(0, 1, 0) : Coords(1, 0, 0)),
                    "map heuristic must choose the cheapest first step");
        expect_true(!path.empty() && path.back() == goal, "map heuristic must reach the goal");
        const int expansion_bound = enabled ? 8 : width;
        expectMetricAtMost(label + " neighbor calls", counters.neighbors, expected_steps, expansion_bound);
        expectMetricAtMost(label + " waypoint calls", counters.waypoint, expected_steps, expansion_bound);
        expectMetricAtMost(label + " canStep calls", counters.canStep, expected_steps * 3, expansion_bound * 4);
        expectMetricAtMost(label + " stepCost calls", counters.stepCost, expected_steps * 3, expansion_bound * 4);
        expectMetricAtMost(label + " distance calls", counters.distance, expected_steps * 3, expansion_bound * 4);
    }
}

void testWeightedConnectorCostsStayWithinWorkBound() {
    constexpr int width = 96;
    const Coords start(0, 0, 0), goal(width - 1, 0, 0);
    for (const int connector_cost : {1, 5, 128}) {
        auto game = std::make_shared<CGame>();
        auto map = std::make_shared<CMap>();
        game->setMap(map);
        map->setGame(game);
        map->setXBounds({{0, width - 1}});
        map->setYBounds({{0, 1}});
        for (int x = 0; x < width; ++x)
            map->addTile(makeWeightedTile(game, 1), x, 0, 0);
        map->addTile(makeWeightedTile(game, 1), 0, 1, 0);
        map->registerNavigationEdge({Coords(0, 1, 0), Coords(width - 2, 0, 0), true, false, connector_cost});
        CallbackCounters counters;
        auto can_step = [&counters, map](const Coords &coords) {
            ++counters.canStep;
            return map->canStep(coords);
        };
        auto waypoint = [&counters](const Coords &coords) { return noWaypoint(counters, coords); };
        auto neighbors = [&counters, map](const Coords &coords) {
            ++counters.neighbors;
            return map->getNavigationNeighbors(coords);
        };
        auto cost = [&counters, map](const Coords &from, const Coords &to) {
            ++counters.stepCost;
            return map->lookupNavigationStepCost(from, to);
        };
        const auto path =
            CPathFinder::findPath(start, goal, can_step, waypoint, neighbors, CPathFinder::mapHeuristic(map), cost);
        const bool use_connector = connector_cost < width - 2;
        expectMetricEquals("weighted connector path length", static_cast<long long>(path.size()),
                           use_connector ? 3 : width - 1);
        expect_true(!path.empty() && path.front() == (use_connector ? Coords(0, 1, 0) : Coords(1, 0, 0)),
                    "weighted connector must compete with the ordinary route by total cost");
        expectMetricAtMost("weighted connector neighbor calls", counters.neighbors,
                           use_connector ? connector_cost + 4 : width, width * 2);
        expectMetricAtMost("weighted connector step-cost calls", counters.stepCost,
                           use_connector ? connector_cost * 4 + 16 : width * 4, width * 8);
        expectMetricAtMost("weighted connector passability calls", counters.canStep, width, width * 4);
        auto service = map->getNavigationService();
        const auto indexed = service->findPathResult(map, start, goal);
        expect_true(indexed.status == CNavigationSearchStatus::Found &&
                        indexed.path.size() == (use_connector ? 3 : width - 1) &&
                        indexed.cost == (use_connector ? connector_cost + 2 : width - 1),
                    "snapshot service honors the same connector prices as the generic callback route");
        expectMetricAtMost("snapshot weighted connector expansions", indexed.statistics.expansions, width, width * 2);
        expectMetricAtMost("snapshot weighted connector cost calls", indexed.statistics.costCalls, width * 4,
                           width * 8);
        expect_true(service->budget()->peak() <= service->budget()->limit(),
                    "weighted connector routes stay within the existing shared memory cap");
    }
}

class StaticTerrainWorkProbe : public CMap {
    V_META(StaticTerrainWorkProbe, CMap,
           V_PROPERTY(StaticTerrainWorkProbe, int, serializationVisit, getSerializationVisit, setSerializationVisit))

  public:
    int getSerializationVisit() {
        ++serializationVisits;
        return 1;
    }
    void setSerializationVisit(int) {}
    std::size_t serializationVisits = 0;
};

std::size_t countStaticTerrainTileDefinitions(const json &value) {
    std::size_t result =
        value.is_object() && value.value("class", std::string()) == "CTile" && value.contains("properties") ? 1 : 0;
    if (value.is_object()) {
        for (const auto &[key, child] : value.items())
            result += countStaticTerrainTileDefinitions(child);
    } else if (value.is_array()) {
        for (const auto &child : value)
            result += countStaticTerrainTileDefinitions(child);
    }
    return result;
}

void testStaticTerrainNativeWorkIsBounded() {
    constexpr int REPEATS = 64;
    constexpr int SNAPSHOTS = 8;
    constexpr std::size_t CELLS = 25;
    constexpr std::size_t PROMOTED = 2;
    CTypes::register_type<CMap, CGameObject>();
    CTypes::register_type<CTile, CGameObject>();
    CTypes::register_type<StaticTerrainWorkProbe, CMap, CGameObject>();
    std::size_t native_tile_constructions = 0;
    auto game = std::make_shared<CGame>();
    auto handler = game->getObjectHandler();
    handler->registerNativeType("CTile", [&native_tile_constructions] {
        ++native_tile_constructions;
        return std::make_shared<CTile>();
    });
    type_registration::registerGameplayTypes(game);
    json palette = json::array();
    for (const auto &[type, walkable] :
         std::vector<std::pair<std::string, bool>>{{"staticGuardWallTile", false}, {"staticGuardFloorTile", true}}) {
        auto config = std::make_shared<const json>(json{
            {"class", "CTile"}, {"properties", {{"canStep", walkable}, {"movementCost", 1}, {"tileType", "guard"}}}});
        handler->registerConfig(type, config);
        palette[palette.size()] = {{"type", type}, {"configuration", *config}};
    }
    const json raster = {
        {"version", 1},
        {"levels", json::array({{{"area", "staticWorkGuard"},
                                 {"level", 0},
                                 {"width", 5},
                                 {"height", 5},
                                 {"palette", palette},
                                 {"rows", json::array({"00000", "01110", "00010", "01110", "00000"})}}})}};
    json data = json::array();
    for (std::size_t index = 0; index < CELLS; ++index)
        data[index] = 0;
    const json document = {
        {"properties", {{"x", 1}, {"y", 1}, {"z", 0}, {"staticTerrainData", raster.dump()}}},
        {"tilesets", json::array()},
        {"layers", json::array({{{"type", "tilelayer"},
                                 {"width", 5},
                                 {"height", 5},
                                 {"properties",
                                  {{"level", 0},
                                   {"default", "staticGuardWallTile"},
                                   {"outOfBounds", "staticGuardWallTile"},
                                   {"xBound", 4},
                                   {"yBound", 4}}},
                                 {"data", data}}})},
    };
    auto map = std::make_shared<StaticTerrainWorkProbe>();
    map->setGame(game);
    game->setMap(map);
    CMapLoader::loadFromTmx(map, std::make_shared<const json>(document));
    const auto cold_recipes = handler->getTileRecipeDiagnostics();
    const auto cold_constructions = native_tile_constructions;
    auto navigation = map->getNavigationService();
    auto snapshot = navigation->snapshot(map);
    expect_true(snapshot->canStep(Coords(1, 1, 0)) && !snapshot->canStep(Coords(1, 2, 0)),
                "static work fixture must warm the actual native collision chunk");
    const auto epoch = map->getRoutingEpoch();
    const auto revision = map->getNavigationRevision();
    const auto chunks = snapshot->chunkCount();
    for (int repeat = 0; repeat < REPEATS; ++repeat) {
        expect_true(map->canStep(1, 1, 0) && !map->canStep(1, 2, 0) && !map->canStep(5, 1, 0) &&
                        snapshot->canStep(Coords(1, 1, 0)) && !snapshot->canStep(Coords(1, 2, 0)) &&
                        map->lookupMovementCost(1, 1, 0) == 1 && snapshot->movementCost(Coords(1, 1, 0)) == 1 &&
                        map->lookupMovementCost(5, 1, 0) == 1 && snapshot->movementCost(Coords(5, 1, 0)) == 1,
                    "fixed native scalar/snapshot work must retain raster and bound fallback results");
        expect_true(navigation->snapshot(map) == snapshot && snapshot->isCurrent(),
                    "unchanged static terrain must reuse its current native snapshot");
    }
    const auto steady_recipes = handler->getTileRecipeDiagnostics();
    const auto scalar_constructions = native_tile_constructions - cold_constructions;
    const auto epoch_after = map->getRoutingEpoch();
    expect_true(map->getTiles().empty() && scalar_constructions == 0 &&
                    steady_recipes.applications == cold_recipes.applications &&
                    steady_recipes.compilations == cold_recipes.compilations &&
                    map->getNavigationRevision() == revision && epoch_after == epoch && chunks == 1 &&
                    snapshot->chunkCount() == chunks,
                "fixed scalar work must construct zero tiles, keep routing epoch stable and reuse one chunk");
    auto path = navigation->findPathResult(map, Coords(1, 1, 0), Coords(1, 3, 0));
    expect_true(path.status == CNavigationSearchStatus::Found && path.path.size() == 6 && path.cost == 6 &&
                    std::ranges::find(path.path, Coords(1, 2, 0)) == path.path.end(),
                "the native work guard must follow the six-step masonry bend");
    expectMetricAtMost("static raster search records", path.statistics.records, CELLS, CELLS);
    expectMetricAtMost("static raster search expansions", path.statistics.expansions, CELLS, CELLS);
    expectMetricAtMost("static raster search cost calls", path.statistics.costCalls, CELLS * 4, CELLS * 4);
    expect_true(snapshot->chunkCount() == 1 && map->getTiles().empty() && map->getRoutingEpoch() == epoch,
                "one bounded search must reuse the scalar chunk without promoting terrain or changing its epoch");
    auto floor = map->getTile(1, 1, 0);
    auto wall = map->getTile(1, 2, 0);
    auto promoted_snapshot = navigation->snapshot(map);
    expect_true(!promoted_snapshot->canStep(Coords(1, 2, 0)),
                "the promotion fixture must warm a current snapshot before mutation");
    const auto promoted_epoch = map->getRoutingEpoch();
    for (int repeat = 0; repeat < REPEATS; ++repeat)
        expect_true(map->getTile(1, 1, 0) == floor && map->getTile(1, 2, 0) == wall,
                    "native promotion work must be bounded by distinct coordinates");
    const auto promoted_recipes = handler->getTileRecipeDiagnostics();
    expect_true(floor && wall && floor != wall && map->getTiles().size() == PROMOTED &&
                    promoted_recipes.applications - cold_recipes.applications == PROMOTED &&
                    promoted_recipes.compilations - cold_recipes.compilations == PROMOTED &&
                    native_tile_constructions - cold_constructions == PROMOTED &&
                    map->getRoutingEpoch() == promoted_epoch && navigation->snapshot(map) == promoted_snapshot,
                "two queried coordinates require exactly two canonical objects and two native recipes");
    if (!floor || !wall) {
        game->getContext()->shutdown();
        return;
    }
    wall->setCanStep(true);
    wall->setMovementCost(7);
    wall->setStringProperty("staticWorkMutation", "retained");
    auto changed = navigation->snapshot(map);
    expect_true(!promoted_snapshot->isCurrent() && changed != promoted_snapshot && changed->canStep(Coords(1, 2, 0)) &&
                    changed->movementCost(Coords(1, 2, 0)) == 7,
                "real canonical mutations must invalidate the old chunk and reach the fresh snapshot");
    const auto changed_epoch = map->getRoutingEpoch();
    map->serializationVisits = 0;
    std::size_t max_bytes = 0;
    for (int pass = 0; pass < SNAPSHOTS; ++pass) {
        auto serialized = CSerialization::serializeExpected(map);
        expect_true(serialized.has_value(), "the guard must serialize the actual static native map");
        if (!serialized)
            continue;
        max_bytes = std::max(max_bytes, serialized->dump().size());
        expect_true(countStaticTerrainTileDefinitions(*serialized) == PROMOTED &&
                        (*serialized)["properties"]["staticTerrainData"].get<std::string>() == raster.dump() &&
                        map->serializationVisits == static_cast<std::size_t>(pass + 1),
                    "each native snapshot visits its map once and defines only the two materialized tiles");
        expect_true(map->getTiles().size() == PROMOTED && map->getTile(1, 2, 0) == wall && wall->canStep() &&
                        wall->getMovementCost() == 7 && wall->getStringProperty("staticWorkMutation") == "retained" &&
                        map->getRoutingEpoch() == changed_epoch && navigation->snapshot(map) == changed,
                    "serializing must preserve complete overlay state and current routing without growing terrain");
    }
    expect_true(map->serializationVisits == SNAPSHOTS && native_tile_constructions - cold_constructions == PROMOTED &&
                    handler->getTileRecipeDiagnostics().applications == promoted_recipes.applications &&
                    handler->getTileRecipeDiagnostics().compilations == promoted_recipes.compilations,
                "repeated snapshots must add no terrain construction or recipe compilation");
    handler->registerConfig("staticGuardUnboundOutsideTile", handler->getConfig("staticGuardWallTile"));
    map->setOutOfBoundsTiles({{0, "staticGuardUnboundOutsideTile"}});
    const auto unbound_before = handler->getTileRecipeDiagnostics().applications;
    const auto unbound_constructors_before = native_tile_constructions;
    const auto unbound_walkable = map->canStep(6, 1, 0);
    const auto unbound_cost = map->lookupMovementCost(6, 1, 0);
    const auto unbound_applications = handler->getTileRecipeDiagnostics().applications - unbound_before;
    const auto unbound_constructors = native_tile_constructions - unbound_constructors_before;
    expect_true(!unbound_walkable && unbound_cost == 1 && unbound_applications == 2 && unbound_constructors == 2 &&
                    map->getTiles().size() == PROMOTED,
                "an unbound fallback id must retain two native transient constructor applications");
    auto legacy_document = document;
    legacy_document["properties"].erase("staticTerrainData");
    auto legacy = std::make_shared<CMap>();
    legacy->setGame(game);
    game->setMap(legacy);
    CMapLoader::loadFromTmx(legacy, std::make_shared<const json>(legacy_document));
    const auto legacy_before = handler->getTileRecipeDiagnostics().applications;
    const auto legacy_constructors_before = native_tile_constructions;
    const auto legacy_walkable = legacy->canStep(1, 1, 0);
    const auto legacy_cost = legacy->lookupMovementCost(1, 1, 0);
    const auto legacy_applications = handler->getTileRecipeDiagnostics().applications - legacy_before;
    const auto legacy_constructors = native_tile_constructions - legacy_constructors_before;
    expect_true(!legacy_walkable && legacy_cost == 1 && legacy_applications == 2 && legacy_constructors == 2 &&
                    legacy->getTiles().empty(),
                "unopted legacy maps must retain two native transient constructor applications");
    std::cout << "static terrain work guard: repeats=" << REPEATS << " scalarConstructorCalls=" << scalar_constructions
              << " scalarRecipeDelta=" << steady_recipes.applications - cold_recipes.applications
              << " scalarRecipeCompilationDelta=" << steady_recipes.compilations - cold_recipes.compilations
              << " routingEpoch=" << epoch << " routingEpochAfter=" << epoch_after << " chunks=" << chunks
              << " searchRecords=" << path.statistics.records << " searchExpansions=" << path.statistics.expansions
              << " searchCostCalls=" << path.statistics.costCalls << " recordBudget=" << CELLS
              << " costBudget=" << CELLS * 4 << " promoted=" << map->getTiles().size()
              << " promotionBudget=" << PROMOTED << " snapshots=" << SNAPSHOTS
              << " mapVisits=" << map->serializationVisits << " mapVisitBudget=" << SNAPSHOTS
              << " maxSerializedBytesDiagnostic=" << max_bytes
              << " unboundConstructorApplications=" << unbound_applications
              << " unboundConstructorCalls=" << unbound_constructors
              << " legacyConstructorApplications=" << legacy_applications
              << " legacyConstructorCalls=" << legacy_constructors << '\n';
    game->getContext()->shutdown();
}

} // namespace

void run_pathfinder_performance_tests() {
    testCoroutineDispatchAndFrameBudgets();
    testExplicitBudgetBoundsUnreachableGoalInOpenPlane();
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
    testMapMovementCostRegressionPinsTileWeightsAndRouting();
    testMovementCostPathStaysWithinWorkBound();
    testMapHeuristicPreservesPortalRoutesAndOrdinarySearchWork();
    testWeightedConnectorCostsStayWithinWorkBound();
    testStaticTerrainNativeWorkIsBounded();
}
