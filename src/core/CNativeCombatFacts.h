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

#include "core/CGlobal.h"
#include <cstdint>

class CCreature;
class CGame;
class CGameContext;
class CGameObject;
class CMap;
struct DamageValue;
struct CNativeCombatBatch;
struct CNativeCombatFact;

// Owner-thread operation nesting carries no causer. Each fact supplies its actual actors explicitly.
class CNativeCombatScope {
  public:
    explicit CNativeCombatScope(const std::shared_ptr<CGame> &game);
    ~CNativeCombatScope() noexcept;
    CNativeCombatScope(const CNativeCombatScope &) = delete;
    CNativeCombatScope &operator=(const CNativeCombatScope &) = delete;
    void finish();

  private:
    std::shared_ptr<CGameContext> context;
    std::shared_ptr<CNativeCombatBatch> batch;
    bool joined = false;
};

class CNativeCombatFacts {
  public:
    CNativeCombatFacts(std::shared_ptr<CCreature> cause, std::shared_ptr<CCreature> victim);
    bool enabled() const { return batch != nullptr; }
    void attempt(std::shared_ptr<CGameObject> producer) const;
    void roll(bool connected, int damage) const;
    void packet(const DamageValue &damage, int hpBefore, int hpAfter, std::shared_ptr<CGameObject> producer = {}) const;

  private:
    bool current() const;
    void capture(std::shared_ptr<const CNativeCombatFact> fact) const;
    std::shared_ptr<CCreature> cause;
    std::shared_ptr<CCreature> victim;
    std::shared_ptr<CNativeCombatBatch> batch;
};
