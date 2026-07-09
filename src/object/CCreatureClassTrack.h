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

#include "object/CGameObject.h"

class CCreatureClass;

// CCreatureClassTrack is a CGameObject-derived *record*, not a CCreature subtype:
// one entry of a creature's ordered multiclass progression (future mechanics,
// EPIC_08). Each track pairs a CCreatureClass reference with a per-track class
// level, plus an `order` key so a creature's tracks fold in deterministically
// (ascending order, ties broken by configured identity), mirroring how
// CCreatureTemplate overlays are ordered.
//
// Compatibility contract: the track layer is FUTURE-ONLY scaffolding. Every
// current creature has an empty CCreature.classTracks set and keeps the single
// CCreature.creatureClass path bit-identically. When one or more tracks are
// present they SUBSUME the single creatureClass for class-derived contributions
// (stats, actions, mainStat); the creatureClass reference itself is preserved
// untouched. See docs/design/creature_archetypes.md, "Multiclass class-track
// layer".
//
// Neutral defaults: a bare track (null class, level 0) contributes nothing. Like
// CCreatureRace/CCreatureClass/CCreatureTemplate it is never spawnable and never
// enumerated as a CCreature subtype; it only carries data the composition layer
// reads.
class CCreatureClassTrack : public CGameObject {

    V_META(CCreatureClassTrack, CGameObject,
           V_PROPERTY(CCreatureClassTrack, std::shared_ptr<CCreatureClass>, creatureClass, getCreatureClass,
                      setCreatureClass),
           V_PROPERTY(CCreatureClassTrack, int, level, getLevel, setLevel),
           V_PROPERTY(CCreatureClassTrack, int, order, getOrder, setOrder))

  public:
    CCreatureClassTrack();

    virtual ~CCreatureClassTrack();

    std::shared_ptr<CCreatureClass> getCreatureClass();

    void setCreatureClass(std::shared_ptr<CCreatureClass> value);

    int getLevel();

    void setLevel(int value);

    int getOrder();

    void setOrder(int value);

  private:
    std::shared_ptr<CCreatureClass> creatureClass;
    int level = 0;
    int order = 0;
};
