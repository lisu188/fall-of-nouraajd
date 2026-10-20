/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#pragma once

#include "core/CMap.h"

#include <algorithm>
#include <unordered_set>
#include <vector>

class CMovementBatch {
  public:
    static std::vector<Coords> interactionCells(const CMap &map, Coords origin, Coords destination) {
        std::vector<Coords> result;
        result.reserve(10);
        for (const auto endpoint : {origin, destination}) {
            for (const auto cell : map.getAdjacentCoords(map.normalizeCoords(endpoint), true)) {
                if (std::find(result.begin(), result.end(), cell) == result.end())
                    result.push_back(cell);
            }
        }
        return result;
    }

    bool conflicts(const std::vector<Coords> &footprint) {
        for (const auto cell : footprint) {
            ++probes;
            if (cells.contains(cell))
                return true;
        }
        return false;
    }

    void add(const std::vector<Coords> &footprint) {
        for (const auto cell : footprint) {
            ++insertions;
            cells.insert(cell);
        }
    }

    void clear() { cells.clear(); }
    std::size_t cellCount() const { return cells.size(); }
    std::size_t probeCount() const { return probes; }
    std::size_t insertionCount() const { return insertions; }

  private:
    std::unordered_set<Coords> cells;
    std::size_t probes = 0;
    std::size_t insertions = 0;
};
