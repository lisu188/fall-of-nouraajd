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
#include "CCreatureClassTrack.h"
#include "object/CCreatureClass.h"

CCreatureClassTrack::CCreatureClassTrack() {}

CCreatureClassTrack::~CCreatureClassTrack() {}

std::shared_ptr<CCreatureClass> CCreatureClassTrack::getCreatureClass() { return creatureClass; }

// A null class is valid: such a track is a degenerate record that contributes
// nothing to the composed stats/actions (the fold-in null-guards it), so a
// partially authored track never breaks composition or serialization.
void CCreatureClassTrack::setCreatureClass(std::shared_ptr<CCreatureClass> value) { creatureClass = value; }

int CCreatureClassTrack::getLevel() { return level; }

void CCreatureClassTrack::setLevel(int value) { level = value; }

int CCreatureClassTrack::getOrder() { return order; }

void CCreatureClassTrack::setOrder(int value) { order = value; }
