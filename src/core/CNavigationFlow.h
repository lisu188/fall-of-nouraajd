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

#include "core/CUtil.h"
#include <cstddef>
#include <cstdint>
#include <memory>

class CMap;
class CMapObject;
class CNavigationBudget;
class CNavigationSnapshot;

enum class CNavigationFlowStatus { Complete, Unreachable, Deferred, ResourceLimit, Cancelled };

struct CNavigationFlowResult {
    CNavigationFlowStatus status = CNavigationFlowStatus::Deferred;
    Coords step;
    std::int64_t cost = 0;
};

struct CNavigationFlowStatistics {
    std::uint64_t fieldsCreated = 0;
    std::uint64_t fieldRebuilds = 0;
    std::uint64_t incrementalRepairs = 0;
    std::uint64_t expandedNodes = 0;
    std::uint64_t cacheHits = 0;
    std::uint64_t deferredRequests = 0;
    std::uint64_t resourceLimits = 0;
};

class CNavigationFlow {
  public:
    explicit CNavigationFlow(std::shared_ptr<CNavigationBudget> budget);
    ~CNavigationFlow();

    CNavigationFlowResult nextStep(const std::shared_ptr<CNavigationSnapshot> &snapshot,
                                   const std::shared_ptr<CMap> &map, const std::shared_ptr<CMapObject> &target,
                                   Coords start, Coords goal, std::int64_t turn);
    void clear();
    void shutdown();
    bool evictUnused();
    std::size_t cacheSize() const;
    CNavigationFlowStatistics statistics() const;

  private:
    struct Impl;
    // The resource must outlive both the pimpl allocation and all its PMR containers.
    std::shared_ptr<CNavigationBudget> allocationBudget;
    std::shared_ptr<Impl> impl;
};
