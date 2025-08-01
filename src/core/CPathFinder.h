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

class CPathFinder {
public:
  // TODO change naming
  static std::shared_ptr<vstd::future<Coords, void>> findNextStep(
      Coords start, Coords goal,
      const std::function<bool(const Coords &)> &canStep,
      const std::function<std::pair<bool, Coords>(const Coords &)> waypoint);

  static std::vector<Coords> findPath(
      Coords start, Coords goal,
      const std::function<bool(const Coords &)> &canStep,
      const std::function<std::pair<bool, Coords>(const Coords &)> waypoint);

  static void saveMap(
      Coords start, const std::function<bool(const Coords &)> &canStep,
      const std::string &path,
      const std::function<std::pair<bool, Coords>(const Coords &)> &waypoint);
};

template <typename T = void> std::list<Coords> near_coords(auto coords) {
  return {Coords(coords.x + 1, coords.y, coords.z),
          Coords(coords.x - 1, coords.y, coords.z),
          Coords(coords.x, coords.y + 1, coords.z),
          Coords(coords.x, coords.y - 1, coords.z)};
}

template <typename T = void> std::list<Coords> near_coords_with(auto coords) {
  return {Coords(coords.x, coords.y, coords.z),
          Coords(coords.x + 1, coords.y, coords.z),
          Coords(coords.x - 1, coords.y, coords.z),
          Coords(coords.x, coords.y + 1, coords.z),
          Coords(coords.x, coords.y - 1, coords.z)};
}
