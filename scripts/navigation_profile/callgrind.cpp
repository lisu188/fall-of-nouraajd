/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CPathFinder.h"
#include <valgrind/callgrind.h>
#include <iostream>

void graphCase(const char *name, int size, bool weighted, bool unreachable) {
    const Coords start(0, 0, 0), goal(size - 1, size - 1, 0);
    std::size_t passability = 0, expansions = 0, costCalls = 0, heuristicCalls = 0;
    auto path = CPathFinder::findPath(
        start, goal,
        [&](Coords cell) {
            ++passability;
            return cell.z == 0 && cell.x >= 0 && cell.y >= 0 && cell.x < size && cell.y < size &&
                   (!unreachable || cell.x != size / 2);
        },
        [](Coords) -> std::optional<Coords> { return std::nullopt; },
        [&](Coords cell) {
            ++expansions;
            return default_neighbors(cell);
        },
        [&](Coords from, Coords to) {
            ++heuristicCalls;
            return from.getDist(to);
        },
        [&](Coords, Coords to) {
            ++costCalls;
            return weighted && to.x > size / 4 && to.x < size * 3 / 4 && to.y < size - 2 ? 20 : 1;
        });
    if (path.empty() || (unreachable ? path != std::vector<Coords>{start} : path.back() != goal))
        throw std::runtime_error("profile route did not satisfy reachability contract");
    std::cout << name << " length=" << path.size() << " expansions=" << expansions << " passability=" << passability
              << " edgeCost=" << costCalls << " heuristic=" << heuristicCalls << '\n';
}

int main() {
    CALLGRIND_START_INSTRUMENTATION;
    CALLGRIND_ZERO_STATS;
    graphCase("open128", 128, false, false);
    graphCase("weighted128", 128, true, false);
    graphCase("unreachable64", 64, false, true);
    CALLGRIND_STOP_INSTRUMENTATION;
    CALLGRIND_DUMP_STATS;
}
