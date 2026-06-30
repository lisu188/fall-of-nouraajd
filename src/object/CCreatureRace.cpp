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
#include "CCreatureRace.h"
#include "core/CStats.h"
#include "object/CInteraction.h"

CCreatureRace::CCreatureRace() {}

CCreatureRace::~CCreatureRace() {}

std::shared_ptr<CStats> CCreatureRace::getBaseStats() { return baseStats; }

// Null-safe: a missing baseStats normalizes to an empty CStats so stat
// aggregation (race + class + creature) never dereferences a null definition.
void CCreatureRace::setBaseStats(std::shared_ptr<CStats> value) {
    baseStats = value ? value : std::make_shared<CStats>();
}

std::set<std::shared_ptr<CInteraction>> CCreatureRace::getActions() { return actions; }

// Null-safe: drop null interactions so action composition over a race definition
// stays well-formed and serialization remains deterministic.
void CCreatureRace::setActions(std::set<std::shared_ptr<CInteraction>> value) {
    std::set<std::shared_ptr<CInteraction>> filtered;
    for (const auto &action : value) {
        if (action) {
            filtered.insert(action);
        }
    }
    actions = filtered;
}

std::string CCreatureRace::getCreatureType() { return creatureType; }

void CCreatureRace::setCreatureType(std::string value) { creatureType = value; }

std::set<std::string> CCreatureRace::getSubtypes() { return subtypes; }

void CCreatureRace::setSubtypes(std::set<std::string> value) { subtypes = value; }

bool CCreatureRace::isPlayerSelectable() { return playerSelectable; }

void CCreatureRace::setPlayerSelectable(bool value) { playerSelectable = value; }
