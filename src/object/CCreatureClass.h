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

#include <map>
#include <set>
#include <string>

class CInteraction;

// Map of level-string -> unlocked interaction, identical in type to CCreature's
// CInteractionMap. Redeclaring the typedef with the same underlying type is well
// formed, so CCreatureClass does not need to pull in the heavy CCreature.h.
typedef std::map<std::string, std::shared_ptr<CInteraction>> CInteractionMap;

// CCreatureClass is a CGameObject-derived *metadata definition* (a learned role:
// the class a creature is, e.g. Warrior/Sorcerer), not a CCreature subtype. It
// carries the class contribution to a composed creature -- base stats, per-level
// stat growth, innate actions, a level-keyed unlock map, and the name of its main
// stat. Like CCreatureRace it is never spawnable and never enumerated as a
// CCreature subtype; it is only referenced via CCreature.creatureClass.
class CCreatureClass : public CGameObject {

    V_META(CCreatureClass, CGameObject,
           V_PROPERTY(CCreatureClass, std::shared_ptr<CStats>, baseStats, getBaseStats, setBaseStats),
           V_PROPERTY(CCreatureClass, std::shared_ptr<CStats>, levelStats, getLevelStats, setLevelStats),
           V_PROPERTY(CCreatureClass, std::set<std::shared_ptr<CInteraction>>, actions, getActions, setActions),
           V_PROPERTY(CCreatureClass, CInteractionMap, levelling, getLevelling, setLevelling),
           V_PROPERTY(CCreatureClass, std::string, mainStat, getMainStat, setMainStat))

  public:
    CCreatureClass();

    virtual ~CCreatureClass();

    std::shared_ptr<CStats> getBaseStats();

    void setBaseStats(std::shared_ptr<CStats> value);

    std::shared_ptr<CStats> getLevelStats();

    void setLevelStats(std::shared_ptr<CStats> value);

    std::set<std::shared_ptr<CInteraction>> getActions();

    void setActions(std::set<std::shared_ptr<CInteraction>> value);

    CInteractionMap getLevelling();

    void setLevelling(CInteractionMap value);

    std::string getMainStat();

    void setMainStat(std::string value);

  private:
    std::shared_ptr<CStats> baseStats = std::make_shared<CStats>();
    std::shared_ptr<CStats> levelStats = std::make_shared<CStats>();
    std::set<std::shared_ptr<CInteraction>> actions;
    CInteractionMap levelling;
    std::string mainStat;
};
