/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CPathFinder.h"
#include "core/CRuntimeBridge.h"
#include "object/CPlayer.h"
#include "object/CTile.h"

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <pybind11/embed.h>

#ifdef NAVIGATION_PROFILE_CURRENT_ONLY
#include "core/CNavigation.h"
#include "core/CNavigationFlow.h"
#include "core/CNavigationSearch.h"
#include "object/CMapObject.h"
#include "rdg.h"
#include <queue>
#include <random>
#endif

namespace {
using Clock = std::chrono::steady_clock;
constexpr int warmups = 2;
constexpr int samples = 7;
struct Counts {
    std::uint64_t passability = 0;
    std::uint64_t expanded = 0;
    std::uint64_t cost = 0;
    std::uint64_t distance = 0;
};

template <typename Work> void sample(const std::string &name, Work work) {
    std::vector<double> timings;
    for (int iteration = -warmups; iteration < samples; ++iteration) {
        const auto started = Clock::now();
        const auto result = work();
        const auto elapsed = std::chrono::duration<double, std::milli>(Clock::now() - started).count();
        if (iteration >= 0) {
            timings.push_back(elapsed);
            std::cout << name << " sample=" << iteration << " milliseconds=" << elapsed << " " << result << '\n';
        }
    }
    std::sort(timings.begin(), timings.end());
    std::cout << name << " median_ms=" << timings[timings.size() / 2] << '\n';
}

void graphCase(const std::string &name, int size, bool weighted, bool unreachable) {
    const Coords start(0, 0, 0), goal(size - 1, size - 1, 0);
    sample(name, [&] {
        Counts counts;
        const auto path = CPathFinder::findPath(
            start, goal,
            [&](const Coords &coords) {
                ++counts.passability;
                return coords.z == 0 && coords.x >= 0 && coords.y >= 0 && coords.x < size && coords.y < size &&
                       (!unreachable || coords.x != size / 2);
            },
            [](const Coords &) -> std::optional<Coords> { return std::nullopt; },
            [&](const Coords &coords) {
                ++counts.expanded;
                return default_neighbors(coords);
            },
            [&](const Coords &from, const Coords &to) {
                ++counts.distance;
                return from.getDist(to);
            },
            [&](const Coords &, const Coords &to) {
                ++counts.cost;
                return weighted && to.x > size / 4 && to.x < size * 3 / 4 && to.y < size - 2 ? 20 : 1;
            });
        if (path.empty() || (unreachable ? path != std::vector<Coords>{start} : path.back() != goal))
            throw std::runtime_error("The fixed graph route did not satisfy its reachability contract");
        return "length=" + std::to_string(path.size()) + " expanded=" + std::to_string(counts.expanded) +
               " passability=" + std::to_string(counts.passability) + " edge_cost=" + std::to_string(counts.cost) +
               " heuristic=" + std::to_string(counts.distance);
    });
}

void playerOverlayCase(const std::shared_ptr<CGame> &game, int length) {
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    map->setXBounds({{0, length}});
    map->setYBounds({{0, 0}});
    for (int x = 0; x <= length; ++x) {
        auto tile = std::make_shared<CTile>();
        tile->setCanStep(true);
        map->addTile(tile, x, 0, 0);
    }
    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    player->setName("navigationProfilePlayer");
    player->setCoords(ZERO);
    map->addObject(player);
    auto controller = std::make_shared<CPlayerController>();
    player->setController(controller);
    controller->setTarget(player, Coords(length, 0, 0));
    constexpr int queries = 20'000;
    sample("player_overlay_4096", [&] {
        std::uint64_t matched = 0;
        for (int index = 0; index < queries; ++index)
            matched += controller->isOnPath(player, Coords(1 + (index * 17) % length, 0, 0)).first;
        if (matched != queries)
            throw std::runtime_error("Every overlay query must match the retained route");
        return "queries=" + std::to_string(queries) + " matched=" + std::to_string(matched);
    });
    game->getContext()->shutdown();
}

#ifdef NAVIGATION_PROFILE_CURRENT_ONLY
void seededDungeonCase() {
    std::mt19937 random(241);
    rdg::Options options;
    options.n_rows = 555;
    options.n_cols = 555;
    options.corridor_layout = rdg::CorridorLayout::BENT;
    const auto dungeon = rdg::create_dungeon(options, random);
    const int width = dungeon.rowCount(), height = dungeon.colCount();
    auto map = std::make_shared<CMap>();
    map->setXBounds({{0, width - 1}});
    map->setYBounds({{0, height - 1}});
    Coords start;
    bool foundStart = false;
    for (int x = 0; x < width; ++x) {
        for (int y = 0; y < height; ++y) {
            const bool open = dungeon.cellAt(x, y).isOpenspace();
            auto tile = std::make_shared<CTile>();
            tile->setCanStep(open);
            map->addTile(tile, x, y, 0);
            if (open && !foundStart) {
                start = Coords(x, y, 0);
                foundStart = true;
            }
        }
    }
    if (!foundStart)
        throw std::runtime_error("The seeded dungeon must have open terrain");
    std::queue<Coords> pending;
    std::vector<int> distances(static_cast<std::size_t>(width) * height, -1);
    auto index = [height](Coords c) { return static_cast<std::size_t>(c.x) * height + c.y; };
    distances[index(start)] = 0;
    pending.push(start);
    Coords goal = start;
    while (!pending.empty()) {
        auto current = pending.front();
        pending.pop();
        goal = current;
        for (auto next : default_neighbors(current)) {
            if (next.x >= 0 && next.y >= 0 && next.x < width && next.y < height && distances[index(next)] < 0 &&
                dungeon.cellAt(next.x, next.y).isOpenspace()) {
                distances[index(next)] = distances[index(current)] + 1;
                pending.push(next);
            }
        }
    }
    auto service = map->getNavigationService();
    std::cout << "seeded_dungeon seed=241 dimensions=" << width << "x" << height
              << " expected_cost=" << distances[index(goal)] << " current_only=1\n";
    sample("seeded_dungeon_555", [&] {
        const auto route = service->findPathResult(map, start, goal);
        if (route.status != CNavigationSearchStatus::Found || route.path.empty() || route.path.back() != goal ||
            route.cost != distances[index(goal)])
            throw std::runtime_error("The seeded dungeon route must match independent BFS reachability and cost");
        return "length=" + std::to_string(route.path.size()) +
               " expanded=" + std::to_string(route.statistics.expansions) +
               " searches=" + std::to_string(service->searchCount()) +
               " budget_peak=" + std::to_string(service->budget()->peak());
    });
}

void movingPursuitCase() {
    sample("moving_target_128_chasers_16_turns", [] {
        auto map = std::make_shared<CMap>();
        map->setXBounds({{0, 127}});
        map->setYBounds({{0, 127}});
        auto target = std::make_shared<CMapObject>();
        target->setName("profileMovingTarget");
        target->setCoords(Coords(100, 80, 0));
        map->addObject(target);
        auto service = map->getNavigationService();
        std::vector<Coords> positions;
        for (int index = 0; index < 128; ++index)
            positions.emplace_back(index % 32, index / 32, 0);
        std::size_t moved = 0;
        for (int turn = 0; turn < 16; ++turn) {
            target->setCoords(Coords(100, 80 + turn % 2, 0));
            for (auto &position : positions) {
                const auto result = service->nextStep(map, target, position, target->getCoords(), turn);
                if (result.status == CNavigationFlowStatus::Complete) {
                    if (position != result.step && position.getDist(result.step) != 1)
                        throw std::runtime_error("Pursuit must return a legal adjacent step");
                    moved += position != result.step;
                    position = result.step;
                } else if (result.status != CNavigationFlowStatus::Deferred) {
                    throw std::runtime_error("Every open-map pursuit request must complete or defer bounded work");
                }
            }
        }
        if (!moved)
            throw std::runtime_error("The moving-target workload must advance its chasers");
        const auto stats = service->flowStatistics();
        return "requests=2048 moved=" + std::to_string(moved) + " expanded=" + std::to_string(stats.expandedNodes) +
               " fields=" + std::to_string(stats.fieldsCreated) +
               " repairs=" + std::to_string(stats.incrementalRepairs) + " hits=" + std::to_string(stats.cacheHits) +
               " deferred=" + std::to_string(stats.deferredRequests) +
               " budget_peak=" + std::to_string(service->budget()->peak()) + " current_only=1";
    });
}
#endif
} // namespace

int main(int argc, char **argv) {
    std::cout << std::unitbuf;
    std::cerr << std::unitbuf;
    if (argc != 3) {
        std::cerr << "Usage: navigation_profile <resource directory> <isolated writable directory>\n";
        return 2;
    }
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    pybind11::scoped_interpreter interpreter;
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    if (!CResourcesProvider::configurePlatformRoots(argv[1], argv[2]))
        return 3;
    std::cout << std::fixed << std::setprecision(6) << "warmups=" << warmups << " samples=" << samples
              << " metric=median_wall_time timing_is_not_a_gate=1\n";
    graphCase("generic_open_96", 96, false, false);
    graphCase("generic_weighted_128", 128, true, false);
    graphCase("generic_unreachable_96", 96, false, true);
    auto game = std::make_shared<CGame>();
    playerOverlayCase(game, 4096);
#ifdef NAVIGATION_PROFILE_CURRENT_ONLY
    seededDungeonCase();
    movingPursuitCase();
#endif
}
