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
#include "gui/CSdlResources.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <queue>

namespace {
constexpr std::size_t MAX_PATHFINDER_VISITED = 1'000'000;
constexpr int MAX_PATH_DUMP_PIXELS = 4'000'000;
// Resource budgets that keep an A* search bounded even when callers (e.g. an MCP client) request a
// goal over sparse or effectively unbounded coordinate space. They are intentionally generous so
// normal navigation stays unaffected, while still failing safely on pathological inputs.
constexpr int MAX_PATH_LENGTH = 100'000;
constexpr long long PATHFINDER_ENVELOPE_FACTOR = 4;
// Additive slack on top of the goal-relative term. It must comfortably exceed the largest legitimate
// raw-coordinate detour, including the worst case on a *wrapping* (toroidal) map where the shortest
// path crosses an edge and a reachable cell can sit up to the full map diagonal away from the start
// in raw coordinates. Authored maps top out at 200x200 (two-axis-corner raw span 398), so 512 keeps
// all in-bounds navigation reachable while still bounding sparse/unbounded searches. The
// 1,000,000-node visit cap remains the absolute ceiling.
constexpr long long PATHFINDER_ENVELOPE_MARGIN = 512;

inline long long manhattanSpan(const Coords &a, const Coords &b) {
    return std::abs(static_cast<long long>(a.x) - b.x) + std::abs(static_cast<long long>(a.y) - b.y) +
           std::abs(static_cast<long long>(a.z) - b.z);
}

// Maximum Manhattan distance from the start that a candidate node may have before it is discarded.
// Scales with the start->goal separation so legitimate detours remain reachable, while preventing
// the frontier from expanding indefinitely away from the goal corridor.
inline long long envelopeBudget(const Coords &start, const Coords &goal) {
    return PATHFINDER_ENVELOPE_FACTOR * manhattanSpan(start, goal) + PATHFINDER_ENVELOPE_MARGIN;
}

inline bool withinEnvelope(const Coords &start, const Coords &candidate, long long budget) {
    return manhattanSpan(start, candidate) <= budget;
}
using Values = std::shared_ptr<std::unordered_map<Coords, int>>;

struct QueueNode {
    int cost;
    Coords coords;
};

struct QueueCompare {
    bool operator()(const QueueNode &a, const QueueNode &b) const { return a.cost > b.cost; }
};

using Queue = std::priority_queue<QueueNode, std::vector<QueueNode>, QueueCompare>;

struct AStarNode {
    int priority;
    int cost;
    Coords coords;
};

struct NextStepNode {
    int priority;
    int cost;
    Coords coords;
    Coords firstStep;
};

struct AStarCompare {
    template <fn::PriorityCostNode Node> bool operator()(const Node &a, const Node &b) const {
        if (a.priority == b.priority) {
            return a.cost > b.cost;
        }
        return a.priority > b.priority;
    }
};

using AStarQueue = std::priority_queue<AStarNode, std::vector<AStarNode>, AStarCompare>;
using NextStepQueue = std::priority_queue<NextStepNode, std::vector<NextStepNode>, AStarCompare>;

template <fn::PathPassability CanStep> class CPassabilityCache {
  public:
    explicit CPassabilityCache(const CanStep &canStep) : canStep(canStep) {}

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
    std::unordered_map<Coords, bool> values;
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
Values fillValues(const CanStep &canStep, const Coords &goal, const Waypoint &waypoint, const Neighbors &neighbors,
                  const StepCost &stepCost, const Coords *stopAt = nullptr) {
    Values values = std::make_shared<std::unordered_map<Coords, int>>();
    CPassabilityCache passability(canStep);
    Queue nodes;

    if (passability.canStepAt(goal) || (stopAt && goal == *stopAt)) {
        (*values)[goal] = 0;
        nodes.push({0, goal});
    }

    while (!nodes.empty()) {
        if (values->size() >= MAX_PATHFINDER_VISITED) {
            vstd::logger::warning("Pathfinder value fill reached visit limit");
            break;
        }
        auto current = nodes.top();
        nodes.pop();

        auto best = values->find(current.coords);
        if (best == values->end() || best->second != current.cost) {
            continue;
        }
        if (stopAt && current.coords == *stopAt) {
            break;
        }

        forEachCandidate(current.coords, waypoint, neighbors, [&](Coords previous) {
            if ((stopAt && previous == *stopAt) || passability.canStepAt(previous)) {
                const int edge_cost = std::max(1, stepCost(previous, current.coords));
                const int next_cost = current.cost + edge_cost;
                auto value = values->find(previous);
                if (value == values->end() || next_cost < value->second) {
                    (*values)[previous] = next_cost;
                    nodes.push({next_cost, previous});
                }
            }
        });
    }

    return values;
}

template <fn::PathDistance Distance>
int estimateCost(const Distance &distance, const Coords &from, const Coords &goal) {
    return std::max(0, static_cast<int>(std::floor(distance(from, goal))));
}

std::vector<Coords> buildPath(const Coords &start, const Coords &goal,
                              const std::unordered_map<Coords, Coords> &previous) {
    if (start == goal) {
        return {start};
    }
    if (!vstd::ctn(previous, goal)) {
        return {start};
    }

    std::vector<Coords> path;
    Coords current = goal;
    while (current != start) {
        path.push_back(current);
        if (static_cast<int>(path.size()) > MAX_PATH_LENGTH) {
            vstd::logger::warning("A* path reconstruction exceeded maximum path length");
            return {start};
        }
        current = previous.at(current);
    }
    std::reverse(path.begin(), path.end());
    return path;
}

template <fn::PathPassability CanStep, fn::PathWaypoint Waypoint, fn::PathNeighbors Neighbors,
          fn::PathDistance Distance, fn::PathStepCost StepCost>
std::vector<Coords> findAStarPath(Coords start, Coords goal, const CanStep &canStep, const Waypoint &waypoint,
                                  const Neighbors &neighbors, const Distance &distance, const StepCost &stepCost) {
    if (start == goal) {
        return {start};
    }
    CPassabilityCache passability(canStep);
    if (!passability.canStepAt(goal)) {
        return {start};
    }

    std::unordered_map<Coords, int> bestCost;
    std::unordered_map<Coords, Coords> previous;
    AStarQueue frontier;

    const long long envelope = envelopeBudget(start, goal);

    bestCost[start] = 0;
    frontier.push({estimateCost(distance, start, goal), 0, start});

    while (!frontier.empty()) {
        if (bestCost.size() >= MAX_PATHFINDER_VISITED) {
            vstd::logger::warning("A* path search reached visit limit");
            break;
        }
        auto current = frontier.top();
        frontier.pop();

        auto best = bestCost.find(current.coords);
        if (best == bestCost.end() || best->second != current.cost) {
            continue;
        }
        if (current.coords == goal) {
            break;
        }

        forEachCandidate(current.coords, waypoint, neighbors, [&](Coords next) {
            if (next != goal && !passability.canStepAt(next)) {
                return;
            }
            if (next != goal && !withinEnvelope(start, next, envelope)) {
                return;
            }

            const int edgeCost = std::max(1, stepCost(current.coords, next));
            const int nextCost = current.cost + edgeCost;
            auto nextBest = bestCost.find(next);
            if (nextBest == bestCost.end() || nextCost < nextBest->second) {
                bestCost[next] = nextCost;
                previous[next] = current.coords;
                frontier.push({nextCost + estimateCost(distance, next, goal), nextCost, next});
            }
        });
    }

    return buildPath(start, goal, previous);
}

template <fn::PathPassability CanStep, fn::PathWaypoint Waypoint, fn::PathNeighbors Neighbors,
          fn::PathDistance Distance, fn::PathStepCost StepCost>
Coords findAStarNextStep(Coords start, Coords goal, const CanStep &canStep, const Waypoint &waypoint,
                         const Neighbors &neighbors, const Distance &distance, const StepCost &stepCost) {
    if (start == goal) {
        return start;
    }
    CPassabilityCache passability(canStep);
    if (!passability.canStepAt(goal)) {
        return start;
    }

    std::unordered_map<Coords, int> bestCost;
    NextStepQueue frontier;

    const long long envelope = envelopeBudget(start, goal);

    bestCost[start] = 0;
    frontier.push({estimateCost(distance, start, goal), 0, start, start});

    while (!frontier.empty()) {
        if (bestCost.size() >= MAX_PATHFINDER_VISITED) {
            vstd::logger::warning("A* next-step search reached visit limit");
            break;
        }
        auto current = frontier.top();
        frontier.pop();

        auto best = bestCost.find(current.coords);
        if (best == bestCost.end() || best->second != current.cost) {
            continue;
        }
        if (current.coords == goal) {
            return current.firstStep;
        }

        forEachCandidate(current.coords, waypoint, neighbors, [&](Coords next) {
            if (next != goal && !passability.canStepAt(next)) {
                return;
            }
            if (next != goal && !withinEnvelope(start, next, envelope)) {
                return;
            }

            const int edgeCost = std::max(1, stepCost(current.coords, next));
            const int nextCost = current.cost + edgeCost;
            auto nextBest = bestCost.find(next);
            if (nextBest == bestCost.end() || nextCost < nextBest->second) {
                bestCost[next] = nextCost;
                frontier.push({nextCost + estimateCost(distance, next, goal), nextCost, next,
                               current.coords == start ? next : current.firstStep});
            }
        });
    }

    return start;
}
} // namespace

std::shared_ptr<vstd::future<Coords, void>>
CPathFinder::findNextStep(Coords start, Coords goal, const CanStep &canStep, const Waypoint waypoint,
                          const Neighbors &neighbors, const Distance &distance, const StepCost &stepCost) {
    return vstd::async(
        [=]() { return findAStarNextStep(start, goal, canStep, waypoint, neighbors, distance, stepCost); });
}

std::vector<Coords> CPathFinder::findPath(Coords start, Coords goal, const CanStep &canStep, const Waypoint waypoint,
                                          const Neighbors &neighbors, const Distance &distance,
                                          const StepCost &stepCost) {
    return findAStarPath(start, goal, canStep, waypoint, neighbors, distance, stepCost);
}

void CPathFinder::saveMap(Coords start, const CanStep &canStep, const std::string &path, const Waypoint &waypoint,
                          const Neighbors &neighbors, const Distance &, const StepCost &stepCost) {
    Values values = fillValues(canStep, start, waypoint, neighbors, stepCost);
    if (values->empty()) {
        return;
    }
    int minx = std::numeric_limits<int>::max();
    int miny = std::numeric_limits<int>::max();
    int maxx = std::numeric_limits<int>::min();
    int maxy = std::numeric_limits<int>::min();
    int maxVal = std::numeric_limits<int>::min();
    for (const auto &entry : *values) {
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
    const int width = factor * std::max(1, maxx - minx + 1);
    const int height = factor * std::max(1, maxy - miny + 1);
    if (width <= 0 || height <= 0 || width > MAX_PATH_DUMP_PIXELS / std::max(1, height)) {
        vstd::logger::warning("Skipping oversized path dump surface:", width, height);
        return;
    }
    auto surface = fn::sdl::SurfacePtr(SDL_SAFE(SDL_CreateRGBSurface(0, width, height, 32, 0, 0, 0, 0)));
    if (!surface) {
        return;
    }
    float scale = maxVal > 0 ? 256.0f / maxVal : 0.0f;
    for (const auto &entry : *values) {
        int posx = entry.first.x - minx;
        int posy = entry.first.y - miny;
        int val = entry.second;
        SDL_Rect rect;
        rect.x = posx * factor;
        rect.y = posy * factor;
        rect.w = factor;
        rect.h = factor;
        float r = 256.0f - (scale * val);
        SDL_FillRect(surface.get(), &rect, SDL_MapRGB(surface->format, r, r, r));
    }
    IMG_SavePNG(surface.get(), path.c_str());
}
