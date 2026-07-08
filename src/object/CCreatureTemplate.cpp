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
#include "CCreatureTemplate.h"
#include "core/CStats.h"
#include "object/CInteraction.h"

CCreatureTemplate::CCreatureTemplate() {}

CCreatureTemplate::~CCreatureTemplate() {}

std::shared_ptr<CStats> CCreatureTemplate::getStatAdjustments() { return statAdjustments; }

// Null-safe: a missing statAdjustments normalizes to an empty (neutral) CStats so
// the template fold-in over race/class composition never dereferences a null
// definition and a bare template contributes nothing.
void CCreatureTemplate::setStatAdjustments(std::shared_ptr<CStats> value) {
    statAdjustments = value ? value : std::make_shared<CStats>();
}

std::set<std::shared_ptr<CInteraction>> CCreatureTemplate::getActions() { return actions; }

// Null-safe: drop null interactions so action composition over a template
// definition stays well-formed and serialization remains deterministic.
void CCreatureTemplate::setActions(std::set<std::shared_ptr<CInteraction>> value) {
    std::set<std::shared_ptr<CInteraction>> filtered;
    for (const auto &action : value) {
        if (action) {
            filtered.insert(action);
        }
    }
    actions = filtered;
}

std::set<std::string> CCreatureTemplate::getSubtypes() { return subtypes; }

void CCreatureTemplate::setSubtypes(std::set<std::string> value) { subtypes = value; }

int CCreatureTemplate::getScaleAdjustment() { return scaleAdjustment; }

void CCreatureTemplate::setScaleAdjustment(int value) { scaleAdjustment = value; }

int CCreatureTemplate::getOrder() { return order; }

void CCreatureTemplate::setOrder(int value) { order = value; }
