/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include "core/CPathFinder.h"

#include <cstdint>
#include <memory_resource>

class CNavigationBudget;
class CNavigationSnapshot;

enum class CNavigationSearchStatus { Found, Unreachable, ResourceLimit, Cancelled, InvalidInput, Deferred };

struct CNavigationSearchLimits {
    std::size_t maxRecords = 1'000'000;
    std::size_t maxExpansions = 1'000'000;
    std::size_t maxPathLength = 100'000;
};

struct CNavigationSearchStatistics {
    std::size_t records = 0;
    std::size_t expansions = 0;
    std::size_t pushes = 0;
    std::size_t pops = 0;
    std::size_t decreaseKeys = 0;
    std::size_t reopened = 0;
    std::size_t peakFrontier = 0;
    std::size_t passabilityCalls = 0;
    std::size_t neighborCalls = 0;
    std::size_t costCalls = 0;
    std::size_t heuristicCalls = 0;
    std::size_t chunkAllocations = 0;
};

struct CNavigationSearchResult {
    // Keep the allocator alive until the path has released its storage.
    std::shared_ptr<CNavigationBudget> allocationBudget;
    std::pmr::vector<Coords> path;
    CNavigationSearchStatus status = CNavigationSearchStatus::Unreachable;
    bool allocationDenied = false;
    std::int64_t cost = 0;
    Coords firstStep;
    CNavigationSearchStatistics statistics;

    explicit CNavigationSearchResult(std::shared_ptr<CNavigationBudget> budget);
    CNavigationSearchResult(CNavigationSearchResult &&) noexcept = default;
    CNavigationSearchResult &operator=(CNavigationSearchResult &&) = delete;
    CNavigationSearchResult(const CNavigationSearchResult &) = delete;
    CNavigationSearchResult &operator=(const CNavigationSearchResult &) = delete;
};

class CNavigationSearchWorkspace {
  public:
    struct Impl;
    CNavigationSearchWorkspace();
    ~CNavigationSearchWorkspace();
    CNavigationSearchWorkspace(const CNavigationSearchWorkspace &) = delete;
    CNavigationSearchWorkspace &operator=(const CNavigationSearchWorkspace &) = delete;

  private:
    std::unique_ptr<Impl> impl;
    friend class CNavigationSearch;
};

class CNavigationSearch {
  public:
    static CNavigationSearchResult findPath(const std::shared_ptr<CNavigationSnapshot> &snapshot, Coords start,
                                            Coords goal, CNavigationSearchWorkspace *workspace = nullptr,
                                            CNavigationSearchLimits limits = {});
    static CNavigationSearchResult findNextStep(const std::shared_ptr<CNavigationSnapshot> &snapshot, Coords start,
                                                Coords goal, CNavigationSearchWorkspace *workspace = nullptr,
                                                CNavigationSearchLimits limits = {});

    // Custom heuristic callbacks must be admissible to guarantee minimum-cost routes. Records may reopen.
    // Custom edge costs are evaluated for each candidate; they are never memoized.
    static CNavigationSearchResult
    findGenericPath(Coords start, Coords goal, const CPathFinder::CanStep &canStep,
                    const CPathFinder::Waypoint &waypoint, const CPathFinder::Neighbors &neighbors = default_neighbors,
                    const CPathFinder::Distance &distance = CPathFinder::DefaultDistance{},
                    const CPathFinder::StepCost &stepCost = CPathFinder::DefaultStepCost{},
                    std::shared_ptr<CNavigationBudget> budget = {}, CNavigationSearchLimits limits = {});
    static CNavigationSearchResult
    findGenericNextStep(Coords start, Coords goal, const CPathFinder::CanStep &canStep,
                        const CPathFinder::Waypoint &waypoint,
                        const CPathFinder::Neighbors &neighbors = default_neighbors,
                        const CPathFinder::Distance &distance = CPathFinder::DefaultDistance{},
                        const CPathFinder::StepCost &stepCost = CPathFinder::DefaultStepCost{},
                        std::shared_ptr<CNavigationBudget> budget = {}, CNavigationSearchLimits limits = {});

    static std::shared_ptr<CNavigationBudget> standaloneBudget();
};
