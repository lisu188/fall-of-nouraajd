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

#include "core/CStats.h"
#include "object/CGameObject.h"

#include <set>
#include <string>

class CInteraction;

// CCreatureTemplate is a CGameObject-derived *metadata definition*, not a CCreature
// subtype: it is a referenced transformation layer (carried by CCreature.templates)
// describing an optional variant overlay -- elite, undead, cult-touched, diseased,
// boss -- applied AFTER race/class composition. It never replaces the race or the
// creatureClass archetype; it only layers adjustments on top of them:
//   * statAdjustments  -- additive stat deltas folded into the composed stat block
//                         after the race/class/creature base+level stack and before
//                         equipment/effects (neutral default: empty CStats).
//   * actions          -- action additions merged after class sources and before the
//                         creature's own concrete actions (neutral default: none).
//   * subtypes         -- data-only classification tag additions (e.g. "elite",
//                         "undead"), mirroring CCreatureRace.subtypes; no mechanical
//                         semantics are attached yet (neutral default: none).
//   * scaleAdjustment  -- delta added to CCreature::getScale (neutral default: 0).
//   * order            -- ordering key; a creature's templates apply in ascending
//                         order (neutral default: 0).
// Like CCreatureRace/CCreatureClass it is deliberately NOT a CMapObject/CCreature,
// so it can never be spawned onto a map or appear in getAllSubTypes("CCreature") /
// random encounter tables; it only carries data the composition layer reads.
class CCreatureTemplate : public CGameObject {

    V_META(CCreatureTemplate, CGameObject,
           V_PROPERTY(CCreatureTemplate, std::shared_ptr<CStats>, statAdjustments, getStatAdjustments,
                      setStatAdjustments),
           V_PROPERTY(CCreatureTemplate, std::set<std::shared_ptr<CInteraction>>, actions, getActions, setActions),
           V_PROPERTY(CCreatureTemplate, std::set<std::string>, subtypes, getSubtypes, setSubtypes),
           V_PROPERTY(CCreatureTemplate, int, scaleAdjustment, getScaleAdjustment, setScaleAdjustment),
           V_PROPERTY(CCreatureTemplate, int, order, getOrder, setOrder))

  public:
    CCreatureTemplate();

    virtual ~CCreatureTemplate();

    std::shared_ptr<CStats> getStatAdjustments();

    void setStatAdjustments(std::shared_ptr<CStats> value);

    std::set<std::shared_ptr<CInteraction>> getActions();

    void setActions(std::set<std::shared_ptr<CInteraction>> value);

    std::set<std::string> getSubtypes();

    void setSubtypes(std::set<std::string> value);

    int getScaleAdjustment();

    void setScaleAdjustment(int value);

    int getOrder();

    void setOrder(int value);

  private:
    std::shared_ptr<CStats> statAdjustments = std::make_shared<CStats>();
    std::set<std::shared_ptr<CInteraction>> actions;
    std::set<std::string> subtypes;
    int scaleAdjustment = 0;
    int order = 0;
};
