/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include "core/CGlobal.h"
#include "object/CGameObject.h"

class CItem;

class CGame;

class CCreature;

class CRngHandler : public CGameObject {
  public:
    // [EPIC_08][STORY_05] How a creature's class relates to its race's natural role
    // (docs/design/creature_archetypes.md): Associated when the race lists the class in
    // its associatedClasses metadata, NonAssociated when it does not, NoArchetype when
    // the creature lacks a race and/or class (every legacy creature).
    enum class ClassAssociation { NoArchetype, Associated, NonAssociated };

    CRngHandler() = default;

    explicit CRngHandler(const std::shared_ptr<CGame> &map);

    // Classifies the race/class pairing the encounter-scale hook below consumes.
    static ClassAssociation classifyClassAssociation(const std::shared_ptr<CCreature> &creature);

    // Future-gated encounter-scale hook: maps a creature's concrete power (getSw()) to
    // its encounter power-table key by class association. Every association currently
    // maps to the neutral multiplier 1 -- the returned power is bit-identical to the
    // input for all content -- until the associated-class balance design is approved.
    static int scaleEncounterPower(int power, ClassAssociation association);

    std::set<std::shared_ptr<CItem>> getRandomLoot(int value) const;

    std::set<std::shared_ptr<CCreature>> getRandomEncounter(int value) const;

    void addRandomLoot(const std::shared_ptr<CCreature> &creature, const std::set<std::shared_ptr<CItem>> &items);

    void addRandomLoot(const std::shared_ptr<CCreature> &creature, int value);

    void addRandomEncounter(const std::shared_ptr<CMap> &map, int x, int y, int z, int value);

  private:
    std::set<std::shared_ptr<CItem>> calculateRandomLoot(int value) const;

    std::set<std::shared_ptr<CCreature>> calculateRandomEncounter(int value) const;

    std::weak_ptr<CGame> game;

    std::unordered_multimap<int, std::string> itemPowerTable;
    std::unordered_multimap<int, std::string> creaturePowerTable;
};
