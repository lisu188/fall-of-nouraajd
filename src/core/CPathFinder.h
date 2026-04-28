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
#pragma once

#include "core/CConcepts.h"
#include "core/CGlobal.h"
#include "core/CUtil.h"

class CCreature;

template <fn::CoordsLike CoordsLike> std::list<Coords> near_coords(const CoordsLike &coords) {
    auto shifted = CARDINAL_DIRECTIONS | std::views::transform([&coords](const Coords &offset) {
                       return Coords(coords.x + offset.x, coords.y + offset.y, coords.z + offset.z);
                   });
    return {shifted.begin(), shifted.end()};
}

template <fn::CoordsLike CoordsLike> std::list<Coords> near_coords_with(const CoordsLike &coords) {
    auto neighbors = near_coords(coords);
    neighbors.push_front(Coords(coords.x, coords.y, coords.z));
    return neighbors;
}

inline std::vector<Coords> default_neighbors(const Coords &coords) {
    std::vector<Coords> list;
    list.reserve(CARDINAL_DIRECTIONS.size());
    for (const auto &offset : CARDINAL_DIRECTIONS) {
        list.push_back(coords + offset);
    }
    return list;
}

class CPathFinder {
  public:
    struct DefaultDistance {
        double operator()(const Coords &a, const Coords &b) const { return a.getDist(b); }
    };

    struct DefaultStepCost {
        constexpr int operator()(const Coords &, const Coords &) const { return 1; }
    };

    using CanStep = std::function<bool(const Coords &)>;
    using Waypoint = std::function<std::pair<bool, Coords>(const Coords &)>;
    using Neighbors = std::function<std::vector<Coords>(const Coords &)>;
    using Distance = std::function<double(const Coords &, const Coords &)>;
    using StepCost = std::function<int(const Coords &, const Coords &)>;

    // TODO change naming
    static std::shared_ptr<vstd::future<Coords, void>> findNextStep(Coords start, Coords goal, const CanStep &canStep,
                                                                    const Waypoint waypoint,
                                                                    const Neighbors &neighbors = default_neighbors,
                                                                    const Distance &distance = DefaultDistance{},
                                                                    const StepCost &stepCost = DefaultStepCost{});

    static std::vector<Coords> findPath(Coords start, Coords goal, const CanStep &canStep, const Waypoint waypoint,
                                        const Neighbors &neighbors = default_neighbors,
                                        const Distance &distance = DefaultDistance{},
                                        const StepCost &stepCost = DefaultStepCost{});

    static void saveMap(Coords start, const CanStep &canStep, const std::string &path, const Waypoint &waypoint,
                        const Neighbors &neighbors = default_neighbors, const Distance &distance = DefaultDistance{},
                        const StepCost &stepCost = DefaultStepCost{});
};

static_assert(fn::PathDistance<CPathFinder::DefaultDistance>);
static_assert(fn::PathStepCost<CPathFinder::DefaultStepCost>);
