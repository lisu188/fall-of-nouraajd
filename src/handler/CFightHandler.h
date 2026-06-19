/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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

#include <vector>

#include "core/CGlobal.h"

class CCreature;

enum class CFightOutcome {
    Invalid = 0,
    AttackerVictory = 1,
    AttackerDefeat = 2,
    Stalled = 3,
    Cancelled = 4,

    invalid = Invalid,
    attackerVictory = AttackerVictory,
    attackerDefeat = AttackerDefeat,
    stalemate = Stalled,
    interrupted = Cancelled,
};

struct CFightResult {
    CFightOutcome outcome = CFightOutcome::Invalid;
    int rounds = 0;
    std::shared_ptr<CCreature> survivor;
    std::shared_ptr<CCreature> opponent;

    bool resolved() const;
    bool attackerSucceeded() const;
};

class CFightHandler {
  public:
    static bool fight(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b);

    static bool fightMany(std::shared_ptr<CCreature> attacker,
                          const std::vector<std::shared_ptr<CCreature>> &opponents);

    static CFightResult fightManyResult(std::shared_ptr<CCreature> attacker,
                                        const std::vector<std::shared_ptr<CCreature>> &opponents);

    static CFightOutcome fightManyOutcome(std::shared_ptr<CCreature> attacker,
                                          const std::vector<std::shared_ptr<CCreature>> &opponents);

    static void defeatedCreature(const std::shared_ptr<CCreature> &a, const std::shared_ptr<CCreature> &b);

    static void applyEffects(const std::shared_ptr<CCreature> &cr);
};
