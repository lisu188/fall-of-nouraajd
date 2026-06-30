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
#include "CCreatureClass.h"
#include "core/CStats.h"
#include "object/CInteraction.h"

CCreatureClass::CCreatureClass() {}

CCreatureClass::~CCreatureClass() {}

std::shared_ptr<CStats> CCreatureClass::getBaseStats() { return baseStats; }

// Null-safe: a missing baseStats normalizes to an empty CStats so composed stat
// aggregation never dereferences a null definition.
void CCreatureClass::setBaseStats(std::shared_ptr<CStats> value) {
    baseStats = value ? value : std::make_shared<CStats>();
}

std::shared_ptr<CStats> CCreatureClass::getLevelStats() { return levelStats; }

// Null-safe: a missing levelStats normalizes to an empty CStats so per-level
// growth aggregation stays well-formed.
void CCreatureClass::setLevelStats(std::shared_ptr<CStats> value) {
    levelStats = value ? value : std::make_shared<CStats>();
}

std::set<std::shared_ptr<CInteraction>> CCreatureClass::getActions() { return actions; }

// Null-safe: drop null interactions from the starting-action set.
void CCreatureClass::setActions(std::set<std::shared_ptr<CInteraction>> value) {
    std::set<std::shared_ptr<CInteraction>> filtered;
    for (const auto &action : value) {
        if (action) {
            filtered.insert(action);
        }
    }
    actions = filtered;
}

CInteractionMap CCreatureClass::getLevelling() { return levelling; }

// Null-safe: drop entries whose unlock interaction is null, but preserve the
// configured level-string keys for every non-null entry so progression data
// deserializes deterministically.
void CCreatureClass::setLevelling(CInteractionMap value) {
    CInteractionMap filtered;
    for (const auto &entry : value) {
        if (entry.second) {
            filtered[entry.first] = entry.second;
        }
    }
    levelling = filtered;
}

std::string CCreatureClass::getMainStat() { return mainStat; }

// mainStat is stored as a plain string; validating that it names a real CStats
// property belongs to the content validator, not runtime construction.
void CCreatureClass::setMainStat(std::string value) { mainStat = value; }
