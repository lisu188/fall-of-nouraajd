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
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CNavigationSearch.h"
#include "gui/CSdlResources.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <queue>

namespace {
constexpr std::size_t MAX_PATHFINDER_VISITED = 1'000'000;
constexpr int MAX_PATH_DUMP_PIXELS = 4'000'000;
using Values = std::pmr::unordered_map<Coords, std::int64_t, CNavigationCoordsHash>;

struct QueueNode {
    std::int64_t cost;
    Coords coords;
};

struct QueueCompare {
    bool operator()(const QueueNode &a, const QueueNode &b) const { return a.cost > b.cost; }
};

using Queue = std::priority_queue<QueueNode, std::pmr::vector<QueueNode>, QueueCompare>;

template <fn::PathPassability CanStep> class CPassabilityCache {
  public:
    CPassabilityCache(const CanStep &canStep, std::pmr::memory_resource *resource)
        : canStep(canStep), values(resource) {}

    bool canStepAt(const Coords &coords) {
        auto cached = values.find(coords);
        if (cached != values.end()) {
            return cached->second;
        }

        bool result = canStep(coords);
        values.emplace(coords, result);
        return result;
    }

  private:
    const CanStep &canStep;
    std::pmr::unordered_map<Coords, bool, CNavigationCoordsHash> values;
};

template <fn::PathWaypoint Waypoint, fn::PathNeighbors Neighbors, typename CandidateHandler>
void forEachCandidate(const Coords &coords, const Waypoint &waypoint, const Neighbors &neighbors,
                      CandidateHandler handle) {
    for (const auto &neighbor : neighbors(coords)) {
        handle(neighbor);
    }
    auto waypoint_direction = waypoint(coords);
    if (waypoint_direction) {
        handle(*waypoint_direction);
    }
}

template <fn::PathPassability CanStep, fn::PathWaypoint Waypoint, fn::PathNeighbors Neighbors,
          fn::PathStepCost StepCost>
void fillValues(Values &values, const CanStep &canStep, const Coords &goal, const Waypoint &waypoint,
                const Neighbors &neighbors, const StepCost &stepCost) {
    auto resource = values.get_allocator().resource();
    CPassabilityCache passability(canStep, resource);
    Queue nodes(QueueCompare{}, std::pmr::vector<QueueNode>(resource));

    if (passability.canStepAt(goal)) {
        values[goal] = 0;
        nodes.push({0, goal});
    }

    while (!nodes.empty()) {
        if (values.size() >= MAX_PATHFINDER_VISITED) {
            vstd::logger::warning("Pathfinder value fill reached visit limit");
            break;
        }
        auto current = nodes.top();
        nodes.pop();

        auto best = values.find(current.coords);
        if (best == values.end() || best->second != current.cost) {
            continue;
        }
        forEachCandidate(current.coords, waypoint, neighbors, [&](Coords previous) {
            if (passability.canStepAt(previous)) {
                const auto edge_cost = std::max<std::int64_t>(1, stepCost(previous, current.coords));
                if (current.cost > std::numeric_limits<std::int64_t>::max() - edge_cost)
                    return;
                const auto next_cost = current.cost + edge_cost;
                auto value = values.find(previous);
                if (value == values.end() || next_cost < value->second) {
                    if (value == values.end() && values.size() >= MAX_PATHFINDER_VISITED)
                        return;
                    values[previous] = next_cost;
                    nodes.push({next_cost, previous});
                }
            }
        });
    }
}

} // namespace

CPathFinder::Distance CPathFinder::mapHeuristic(const std::shared_ptr<CMap> &map) {
    if (!map || std::any_of(map->getNavigationEdges().begin(), map->getNavigationEdges().end(),
                            [](const CNavigationEdge &edge) { return edge.enabled; })) {
        return [](const Coords &, const Coords &) { return 0.0; };
    }
    return [map](const Coords &from, const Coords &to) { return map->getDistance(from, to); };
}

std::shared_ptr<vstd::future<Coords, void>>
CPathFinder::findNextStep(Coords start, Coords goal, const CanStep &canStep, const Waypoint waypoint,
                          const Neighbors &neighbors, const Distance &distance, const StepCost &stepCost) {
    return vstd::async([=]() {
        return CNavigationSearch::findGenericNextStep(start, goal, canStep, waypoint, neighbors, distance, stepCost)
            .firstStep;
    });
}

std::vector<Coords> CPathFinder::findPath(Coords start, Coords goal, const CanStep &canStep, const Waypoint waypoint,
                                          const Neighbors &neighbors, const Distance &distance,
                                          const StepCost &stepCost) {
    auto result = CNavigationSearch::findGenericPath(start, goal, canStep, waypoint, neighbors, distance, stepCost);
    if (result.status != CNavigationSearchStatus::Found)
        return {start};
    const auto bytes = result.path.size() * sizeof(Coords);
    if (!result.allocationBudget->tryReserve(bytes))
        return {start};
    struct CopyReservation {
        CNavigationBudget *budget;
        std::size_t bytes;
        ~CopyReservation() { budget->release(bytes); }
    } reservation{result.allocationBudget.get(), bytes};
    try {
        return {result.path.begin(), result.path.end()};
    } catch (const std::bad_alloc &) {
        return {start};
    }
}

void CPathFinder::saveMap(Coords start, const CanStep &canStep, const std::string &path, const Waypoint &waypoint,
                          const Neighbors &neighbors, const Distance &, const StepCost &stepCost) {
    auto budget = CNavigationSearch::standaloneBudget();
    Values values(budget.get());
    try {
        fillValues(values, canStep, start, waypoint, neighbors, stepCost);
    } catch (const std::bad_alloc &) {
        vstd::logger::warning("Skipping path dump after navigation memory limit");
        return;
    }
    if (values.empty()) {
        return;
    }
    int minx = std::numeric_limits<int>::max();
    int miny = std::numeric_limits<int>::max();
    int maxx = std::numeric_limits<int>::min();
    int maxy = std::numeric_limits<int>::min();
    std::int64_t maxVal = 0;
    for (const auto &entry : values) {
        Coords coords = entry.first;
        if (coords.x < minx) {
            minx = coords.x;
        }
        if (coords.y < miny) {
            miny = coords.y;
        }
        if (coords.x > maxx) {
            maxx = coords.x;
        }
        if (coords.y > maxy) {
            maxy = coords.y;
        }
        if (entry.second > maxVal) {
            maxVal = entry.second;
        }
    }
    int factor = 4;
    const auto wideWidth = factor * (static_cast<std::int64_t>(maxx) - minx + 1);
    const auto wideHeight = factor * (static_cast<std::int64_t>(maxy) - miny + 1);
    if (wideWidth <= 0 || wideHeight <= 0 || wideWidth > MAX_PATH_DUMP_PIXELS / wideHeight) {
        vstd::logger::warning("Skipping oversized path dump surface:", wideWidth, wideHeight);
        return;
    }
    const auto width = static_cast<int>(wideWidth);
    const auto height = static_cast<int>(wideHeight);
    const auto surfaceBytes = static_cast<std::size_t>(width) * height * 4;
    if (!budget->tryReserve(surfaceBytes)) {
        vstd::logger::warning("Skipping path dump after surface memory limit");
        return;
    }
    struct SurfaceReservation {
        std::shared_ptr<CNavigationBudget> budget;
        std::size_t bytes;
        ~SurfaceReservation() { budget->release(bytes); }
    } reservation{budget, surfaceBytes};
    auto surface = fn::sdl::SurfacePtr(SDL_SAFE(SDL_CreateRGBSurface(0, width, height, 32, 0, 0, 0, 0)));
    if (!surface) {
        return;
    }
    float scale = maxVal > 0 ? 256.0f / static_cast<float>(maxVal) : 0.0f;
    for (const auto &entry : values) {
        int posx = entry.first.x - minx;
        int posy = entry.first.y - miny;
        const auto val = entry.second;
        SDL_Rect rect;
        rect.x = posx * factor;
        rect.y = posy * factor;
        rect.w = factor;
        rect.h = factor;
        const float r = 256.0f - scale * static_cast<float>(val);
        SDL_FillRect(surface.get(), &rect, SDL_MapRGB(surface->format, r, r, r));
    }
    IMG_SavePNG(surface.get(), path.c_str());
}
