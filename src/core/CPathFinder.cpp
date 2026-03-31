/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include <algorithm>
#include <limits>
#include <queue>

namespace {
using Values = std::shared_ptr<std::unordered_map<Coords, int>>;

struct QueueNode {
    int cost;
    Coords coords;
};

struct QueueCompare {
    bool operator()(const QueueNode &a, const QueueNode &b) const { return a.cost > b.cost; }
};

using Queue = std::priority_queue<QueueNode, std::vector<QueueNode>, QueueCompare>;

std::vector<Coords> candidates(const Coords &coords,
                               const std::function<std::pair<bool, Coords>(const Coords &)> &waypoint,
                               const std::function<std::vector<Coords>(const Coords &)> &neighbors) {
    auto list = neighbors(coords);
    auto waypoint_direction = waypoint(coords);
    if (waypoint_direction.first) {
        list.push_back(waypoint_direction.second);
    }
    return list;
}

Values fillValues(const std::function<bool(const Coords &)> &canStep, const Coords &goal,
                  const std::function<std::pair<bool, Coords>(const Coords &)> &waypoint,
                  const std::function<std::vector<Coords>(const Coords &)> &neighbors,
                  const CPathFinder::StepCost &stepCost, const Coords *stopAt = nullptr) {
    Values values = std::make_shared<std::unordered_map<Coords, int>>();
    Queue nodes;

    if (canStep(goal) || (stopAt && goal == *stopAt)) {
        (*values)[goal] = 0;
        nodes.push({0, goal});
    }

    while (!nodes.empty()) {
        auto current = nodes.top();
        nodes.pop();

        auto best = values->find(current.coords);
        if (best == values->end() || best->second != current.cost) {
            continue;
        }
        if (stopAt && current.coords == *stopAt) {
            break;
        }

        for (auto previous : candidates(current.coords, waypoint, neighbors)) {
            if ((stopAt && previous == *stopAt) || canStep(previous)) {
                const int edge_cost = std::max(1, stepCost(previous, current.coords));
                const int next_cost = current.cost + edge_cost;
                auto value = values->find(previous);
                if (value == values->end() || next_cost < value->second) {
                    (*values)[previous] = next_cost;
                    nodes.push({next_cost, previous});
                }
            }
        }
    }

    return values;
}

Coords getNextStep(const Coords &start, const Coords &goal, const Values &values,
                   const std::function<std::pair<bool, Coords>(const Coords &)> &waypoint,
                   const std::function<std::vector<Coords>(const Coords &)> &neighbors,
                   const std::function<double(const Coords &, const Coords &)> &distance,
                   const CPathFinder::StepCost &stepCost) {
    Coords target = start;
    int target_cost = std::numeric_limits<int>::max();
    int current_cost = std::numeric_limits<int>::max();
    if (auto current = values->find(start); current != values->end()) {
        current_cost = current->second;
    }

    for (auto coords : candidates(start, waypoint, neighbors)) {
        if (auto value = values->find(coords); value != values->end()) {
            const int candidate_cost = std::max(1, stepCost(start, coords)) + value->second;
            if (candidate_cost < target_cost ||
                (candidate_cost == target_cost && distance(coords, goal) < distance(target, goal))) {
                target = coords;
                target_cost = candidate_cost;
            }
        }
    }

    return target_cost <= current_cost ? target : start;
}
} // namespace

std::shared_ptr<vstd::future<Coords, void>>
CPathFinder::findNextStep(Coords start, Coords goal, const std::function<bool(const Coords &)> &canStep,
                          const std::function<std::pair<bool, Coords>(const Coords &)> waypoint,
                          const std::function<std::vector<Coords>(const Coords &)> &neighbors,
                          const std::function<double(const Coords &, const Coords &)> &distance,
                          const StepCost &stepCost) {
    return vstd::async([=]() {
        return getNextStep(start, goal, fillValues(canStep, goal, waypoint, neighbors, stepCost, &start), waypoint,
                           neighbors, distance, stepCost);
    });
}

std::vector<Coords> CPathFinder::findPath(Coords start, Coords goal, const std::function<bool(const Coords &)> &canStep,
                                          const std::function<std::pair<bool, Coords>(const Coords &)> waypoint,
                                          const std::function<std::vector<Coords>(const Coords &)> &neighbors,
                                          const std::function<double(const Coords &, const Coords &)> &distance,
                                          const StepCost &stepCost) {
    std::vector<Coords> path;
    Values values = fillValues(canStep, goal, waypoint, neighbors, stepCost, &start);
    Coords next = getNextStep(start, goal, values, waypoint, neighbors, distance, stepCost);
    path.push_back(next);
    if (next != start) {
        while (next != goal) {
            next = getNextStep(next, goal, values, waypoint, neighbors, distance, stepCost);
            path.push_back(next);
        }
    }
    return path;
}

void CPathFinder::saveMap(Coords start, const std::function<bool(const Coords &)> &canStep, const std::string &path,
                          const std::function<std::pair<bool, Coords>(const Coords &)> &waypoint,
                          const std::function<std::vector<Coords>(const Coords &)> &neighbors,
                          const std::function<double(const Coords &, const Coords &)> &, const StepCost &stepCost) {
    Values values = fillValues(canStep, start, waypoint, neighbors, stepCost);
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
    SDL_Surface *surface = SDL_CreateRGBSurface(0, factor * (maxx - minx), factor * (maxy - miny), 32, 0, 0, 0, 0);
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
        SDL_FillRect(surface, &rect, SDL_MapRGB(surface->format, r, r, r));
    }
    IMG_SavePNG(surface, path.c_str());
    SDL_FreeSurface(surface);
}
