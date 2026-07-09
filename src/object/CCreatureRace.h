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

class CCreatureClass;

class CInteraction;

// CCreatureRace is a CGameObject-derived *metadata definition*, not a CCreature
// subtype: it is a referenced template (carried by CCreature.race) describing the
// innate baseline a race contributes to a creature -- base stats, innate actions,
// a coarse creatureType and finer subtypes, and whether the race is offered at
// character creation. It is deliberately NOT a CMapObject/CCreature, so it can
// never be spawned onto a map or appear in getAllSubTypes("CCreature") / random
// encounter tables; it only carries data that the composition layer reads.
class CCreatureRace : public CGameObject {

    V_META(CCreatureRace, CGameObject,
           V_PROPERTY(CCreatureRace, std::shared_ptr<CStats>, baseStats, getBaseStats, setBaseStats),
           V_PROPERTY(CCreatureRace, std::set<std::shared_ptr<CInteraction>>, actions, getActions, setActions),
           V_PROPERTY(CCreatureRace, std::string, creatureType, getCreatureType, setCreatureType),
           V_PROPERTY(CCreatureRace, std::set<std::string>, subtypes, getSubtypes, setSubtypes),
           V_PROPERTY(CCreatureRace, bool, playerSelectable, isPlayerSelectable, setPlayerSelectable),
           V_PROPERTY(CCreatureRace, std::set<std::string>, associatedClasses, getAssociatedClasses,
                      setAssociatedClasses),
           V_PROPERTY(CCreatureRace, std::shared_ptr<CStats>, racialLevelStats, getRacialLevelStats,
                      setRacialLevelStats))

  public:
    CCreatureRace();

    virtual ~CCreatureRace();

    std::shared_ptr<CStats> getBaseStats();

    void setBaseStats(std::shared_ptr<CStats> value);

    std::set<std::shared_ptr<CInteraction>> getActions();

    void setActions(std::set<std::shared_ptr<CInteraction>> value);

    std::string getCreatureType();

    void setCreatureType(std::string value);

    std::set<std::string> getSubtypes();

    void setSubtypes(std::set<std::string> value);

    bool isPlayerSelectable();

    void setPlayerSelectable(bool value);

    // [EPIC_08][STORY_05] D&D-inspired associated classes: the class ids (configured
    // identity, e.g. "mageClass") that reinforce this race's natural role. Metadata
    // only for now -- encounter scale treats associated and non-associated pairings
    // identically until the balance design is approved. Defaults empty, so existing
    // races and configs are unaffected.
    std::set<std::string> getAssociatedClasses();

    void setAssociatedClasses(std::set<std::string> value);

    bool isAssociatedClass(const std::string &classId);

    bool isAssociatedClass(const std::shared_ptr<CCreatureClass> &creatureClass);

    std::shared_ptr<CStats> getRacialLevelStats();

    void setRacialLevelStats(std::shared_ptr<CStats> value);

  private:
    std::shared_ptr<CStats> baseStats = std::make_shared<CStats>();
    std::set<std::shared_ptr<CInteraction>> actions;
    std::string creatureType;
    std::set<std::string> subtypes;
    bool playerSelectable = false;
    std::set<std::string> associatedClasses;
    // Hit-dice-style racial progression: the flat stat growth ONE racial level
    // contributes, applied once per CCreature::racialLevel by the composed-stat
    // fold. Racial advancement is modeled separately from the class-driven
    // CCreature::level (EPIC_08/STORY_04/SUBSTORY_01) and is future-gated
    // scaffolding: the default is an empty CStats, so a race without authored
    // progression contributes exactly zero and every existing creature composes
    // bit-identically to today. No XP or level-up flow raises racialLevel yet --
    // that requires explicit XP/scale design and is deliberately deferred.
    std::shared_ptr<CStats> racialLevelStats = std::make_shared<CStats>();
};
