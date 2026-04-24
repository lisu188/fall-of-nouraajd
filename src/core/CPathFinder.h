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
#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"

class CCreature;

template <typename CoordsLike> std::list<Coords> near_coords(const CoordsLike &coords) {
    return {Coords(coords.x + 1, coords.y, coords.z), Coords(coords.x - 1, coords.y, coords.z),
            Coords(coords.x, coords.y + 1, coords.z), Coords(coords.x, coords.y - 1, coords.z)};
}

template <typename CoordsLike> std::list<Coords> near_coords_with(const CoordsLike &coords) {
    return {Coords(coords.x, coords.y, coords.z), Coords(coords.x + 1, coords.y, coords.z),
            Coords(coords.x - 1, coords.y, coords.z), Coords(coords.x, coords.y + 1, coords.z),
            Coords(coords.x, coords.y - 1, coords.z)};
}

inline std::vector<Coords> default_neighbors(const Coords &coords) {
    auto list = near_coords(coords);
    return std::vector<Coords>(list.begin(), list.end());
}

class CPathFinder {
  public:
    using StepCost = std::function<int(const Coords &, const Coords &)>;

    // TODO change naming
    static std::shared_ptr<vstd::future<Coords, void>> findNextStep(
        Coords start, Coords goal, const std::function<bool(const Coords &)> &canStep,
        const std::function<std::pair<bool, Coords>(const Coords &)> waypoint,
        const std::function<std::vector<Coords>(const Coords &)> &neighbors = default_neighbors,
        const std::function<double(const Coords &, const Coords &)> &distance =
            [](const Coords &a, const Coords &b) { return a.getDist(b); },
        const StepCost &stepCost = [](const Coords &, const Coords &) { return 1; });

    static std::vector<Coords> findPath(
        Coords start, Coords goal, const std::function<bool(const Coords &)> &canStep,
        const std::function<std::pair<bool, Coords>(const Coords &)> waypoint,
        const std::function<std::vector<Coords>(const Coords &)> &neighbors = default_neighbors,
        const std::function<double(const Coords &, const Coords &)> &distance =
            [](const Coords &a, const Coords &b) { return a.getDist(b); },
        const StepCost &stepCost = [](const Coords &, const Coords &) { return 1; });

    static void saveMap(
        Coords start, const std::function<bool(const Coords &)> &canStep, const std::string &path,
        const std::function<std::pair<bool, Coords>(const Coords &)> &waypoint,
        const std::function<std::vector<Coords>(const Coords &)> &neighbors = default_neighbors,
        const std::function<double(const Coords &, const Coords &)> &distance =
            [](const Coords &a, const Coords &b) { return a.getDist(b); },
        const StepCost &stepCost = [](const Coords &, const Coords &) { return 1; });
};
