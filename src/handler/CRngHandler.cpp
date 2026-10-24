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
#include "CRngHandler.h"
#include <exception>
#include "handler/CGuiHandler.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CUtil.h"
#include "object/CCreatureRace.h"
#include "object/CObject.h"

#include <algorithm>
#include <cstdlib>

namespace {
constexpr int MAX_RANDOM_VALUE = 1000;

int clampRandomValue(int value) { return std::clamp(value, 0, MAX_RANDOM_VALUE); }

// [EPIC_08][STORY_05] Design-gated associated-class encounter weights
// (docs/design/creature_archetypes.md): a race/class pairing that reinforces the
// race's natural role could weigh more heavily in encounter CR than an off-role
// pairing. Both multipliers are pinned to the neutral value 1 until that balance
// design is approved, so scaleEncounterPower is the identity for every
// classification and the encounter power table stays bit-identical to the
// pre-hook math for all existing content.
constexpr int ASSOCIATED_CLASS_POWER_MULTIPLIER = 1;
constexpr int NON_ASSOCIATED_CLASS_POWER_MULTIPLIER = 1;
} // namespace

void CRngHandler::seedRandomForTests(std::uint32_t seed) {
    vstd::rng().seed(seed);
    std::srand(seed);
}

CRngHandler::ClassAssociation CRngHandler::classifyClassAssociation(const std::shared_ptr<CCreature> &creature) {
    if (!creature) {
        return ClassAssociation::NoArchetype;
    }
    auto race = creature->getRace();
    auto creatureClass = creature->getCreatureClass();
    // Association is only defined for a full race/class pairing; legacy creatures
    // (and race-only / class-only creatures) carry no archetype pairing to weigh.
    if (!race || !creatureClass) {
        return ClassAssociation::NoArchetype;
    }
    return race->isAssociatedClass(creatureClass) ? ClassAssociation::Associated : ClassAssociation::NonAssociated;
}

int CRngHandler::scaleEncounterPower(int power, ClassAssociation association) {
    switch (association) {
    case ClassAssociation::Associated:
        return power * ASSOCIATED_CLASS_POWER_MULTIPLIER;
    case ClassAssociation::NonAssociated:
        return power * NON_ASSOCIATED_CLASS_POWER_MULTIPLIER;
    case ClassAssociation::NoArchetype:
    default:
        return power;
    }
}

std::set<std::shared_ptr<CItem>> CRngHandler::getRandomLoot(int value) const { return calculateRandomLoot(value); }

std::set<std::shared_ptr<CCreature>> CRngHandler::getRandomEncounter(int value) const {
    auto randomEncounter = calculateRandomEncounter(value);
    // TODO: make generic hashing of collections
    std::size_t hash = vstd::rand(256);
    for (const auto &creature : randomEncounter) {
        hash = vstd::hash_combine(hash, creature);
    }
    for (const auto &creature : randomEncounter) {
        creature->setAffiliation(vstd::str(hash));
        // TODO: make this customizable
        if (auto currentGame = game.lock()) {
            creature->setController(currentGame->createObject<CController>("CRandomController"));
        }
    }
    return randomEncounter;
}

CRngHandler::CRngHandler(const std::shared_ptr<CGame> &game) : CRngHandler(game, {}) {}

CRngHandler::CRngHandler(const std::shared_ptr<CGame> &game, std::function<void()> requireCurrent) : game(game) {
    auto objects = game->getObjectHandler();
    auto factories = objects->beginDefeatConstruction(requireCurrent);
    const auto checkCurrent = [&] { factories.check(); };
    try {
        checkCurrent();
        for (const std::string &type : game->getObjectHandler()->getDefeatSubTypes("CItem", requireCurrent)) {
            checkCurrent();
            std::shared_ptr<CItem> item = game->createObject<CItem>(type);
            checkCurrent();
            if (item) {
                int power = item->getPower();
                checkCurrent();
                // Compound artifacts are assembled from set pieces, never dropped or sold
                // directly (docs/design/compound_artifacts.md); exclude them from random loot
                // the same way quest items are excluded.
                const bool quest = power > 0 && item->hasTag(CTag::Quest);
                checkCurrent();
                const bool compound = power > 0 && !quest && item->hasTag(CTag::Compound);
                checkCurrent();
                if (power > 0 && !quest && !compound) {
                    itemPowerTable.insert(std::make_pair(power, type));
                }
            }
        }

        for (const std::string &type : game->getObjectHandler()->getDefeatSubTypes("CCreature", requireCurrent)) {
            // getAllSubTypes("CCreature") also returns player templates because CPlayer inherits
            // CCreature (src/object/CPlayer.h:24, registered via NativePlugin.cpp). Random encounters
            // must never spawn a player template, so skip any candidate whose resolved class inherits
            // CPlayer -- the same meta()->inherits(...) test getAllSubTypes itself applies for the
            // CCreature gate (src/handler/CObjectHandler.cpp:115). Genuine monster candidates and their
            // sw power buckets are untouched.
            checkCurrent();
            auto candidateClass = game->getObjectHandler()->getType(game->getObjectHandler()->getClass(type));
            checkCurrent();
            if (candidateClass && candidateClass->meta()->inherits("CPlayer")) {
                continue;
            }
            checkCurrent();
            std::shared_ptr<CCreature> creature = game->createObject<CCreature>(type);
            checkCurrent();
            const bool npc = creature && creature->isNpc();
            checkCurrent();
            const bool hasController = creature && !npc && static_cast<bool>(creature->getFightController());
            checkCurrent();
            if (creature && !npc && hasController) {
                // The associated-class hook is neutral today (multipliers pinned to 1), so
                // this key equals the raw getSw() for every candidate; it only becomes a
                // real CR weight once the associated-class balance design is approved.
                const auto sw = creature->getSw();
                checkCurrent();
                const auto association = classifyClassAssociation(creature);
                checkCurrent();
                int power = scaleEncounterPower(sw, association);
                if (power > 0) {
                    creaturePowerTable.insert(std::make_pair(power, type));
                }
            }
        }
        checkCurrent();
    } catch (...) {
        factories.rethrowFailure();
        throw;
    }
}

std::set<std::shared_ptr<CItem>> CRngHandler::calculateRandomLoot(int value) const {
    return calculateDefeatLoot(value, {});
}

std::set<std::shared_ptr<CItem>> CRngHandler::calculateDefeatLoot(int value,
                                                                  std::function<void()> requireCurrent) const {
    if (requireCurrent) {
        requireCurrent();
    }
    auto currentGame = game.lock();
    if (!currentGame) {
        return {};
    }
    auto factories = currentGame->getObjectHandler()->beginDefeatConstruction(requireCurrent);
    std::set<std::shared_ptr<CItem>> loot;
    try {
        value = clampRandomValue(value);
        for (auto pow : vstd::random_components(value, itemPowerTable | std::views::keys)) {
            std::set<std::string> possible_names;
            auto range = itemPowerTable.equal_range(pow);
            for (auto it = range.first; it != range.second; it++) {
                possible_names.insert(it->second);
            }
            if (!possible_names.empty()) {
                if (requireCurrent) {
                    requireCurrent();
                }
                auto item = currentGame->createObject<CItem>(*vstd::random_element(possible_names));
                if (requireCurrent) {
                    requireCurrent();
                }
                loot.insert(std::move(item));
            }
            value -= pow;
        }
        return loot;
    } catch (...) {
        factories.rethrowFailure();
        throw;
    }
}

void CRngHandler::addRandomLoot(const std::shared_ptr<CCreature> &creature,
                                const std::set<std::shared_ptr<CItem>> &items) {
    if (!creature) {
        return;
    }
    // TODO: polymorphic
    if (creature->isPlayer()) {
        creature->getGame()->getGuiHandler()->showLoot(creature, items);
    }
    creature->addItems(items);
}

void CRngHandler::addRandomLoot(const std::shared_ptr<CCreature> &creature, int value) {
    addRandomLoot(creature, getRandomLoot(value));
}

vstd::task<void> CRngHandler::addRandomLootAsync(std::shared_ptr<CCreature> creature,
                                                 std::set<std::shared_ptr<CItem>> items) {
    return addDefeatLootAsync(std::move(creature), std::move(items), {});
}

vstd::task<void> CRngHandler::addDefeatLootAsync(std::shared_ptr<CCreature> creature,
                                                 std::set<std::shared_ptr<CItem>> items,
                                                 std::function<void()> requireCurrent,
                                                 std::function<void()> settleCurrent,
                                                 std::function<void()> compensate) {
    return [](std::shared_ptr<CCreature> creature, std::set<std::shared_ptr<CItem>> items,
              std::function<void()> requireCurrent, std::function<void()> settleCurrent,
              std::function<void()> compensate) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        if (!creature) {
            co_return;
        }
        if (requireCurrent) {
            requireCurrent();
        }
        const bool player = creature->isPlayer();
        if (requireCurrent) {
            requireCurrent();
        }
        if (player) {
            auto game = creature->getGame();
            auto gui = game->getGuiHandler();
            game.reset();
            if (requireCurrent) {
                requireCurrent();
            }
            try {
                co_await gui->showLootAsync(creature, items);
            } catch (const vstd::task_cancelled &) {
                if (!compensate) {
                    if (requireCurrent) {
                        requireCurrent();
                    }
                    creature->addItems(items);
                    throw;
                }
                const auto primary = std::current_exception();
                try {
                    compensate();
                } catch (...) {
                }
                std::rethrow_exception(primary);
            }
        }
        if (settleCurrent) {
            settleCurrent();
        } else {
            if (requireCurrent) {
                requireCurrent();
            }
            creature->addItems(items);
        }
    }(std::move(creature), std::move(items), std::move(requireCurrent), std::move(settleCurrent),
                                                std::move(compensate));
}

std::set<std::shared_ptr<CCreature>> CRngHandler::calculateRandomEncounter(int value) const {
    std::set<std::shared_ptr<CCreature>> encounter;
    auto currentGame = game.lock();
    if (!currentGame) {
        return encounter;
    }
    value = clampRandomValue(value);
    for (int pow : vstd::random_components(value, std::views::iota(1, value + 1))) {
        auto possiblePowersRange =
            creaturePowerTable | std::views::keys | std::views::filter([pow](int it) { return it <= pow; });
        // TODO: util for range copy
        std::set<int> possiblePowers(possiblePowersRange.begin(), possiblePowersRange.end());
        if (possiblePowers.empty()) {
            continue;
        }
        int sw = *vstd::random_element(possiblePowers);
        std::set<std::string> possible_names;
        auto range = creaturePowerTable.equal_range(sw);
        for (auto it = range.first; it != range.second; it++) {
            possible_names.insert(it->second);
        }
        if (!possible_names.empty()) {
            auto creature = currentGame->createObject<CCreature>(*vstd::random_element(possible_names));
            if (!creature) {
                continue;
            }
            // Fresh templates have zero hp, so their experience path is inactive until initialized.
            creature->heal(0);
            creature->addExp(creature->getExpForLevel(std::max(1, pow - sw)));
            encounter.insert(creature);
        }
        value -= pow;
    }
    return encounter;
}

void CRngHandler::addRandomEncounter(const std::shared_ptr<CMap> &map, int x, int y, int z, int value) {
    if (!map) {
        return;
    }
    for (const auto &creature : getRandomEncounter(value)) {
        map->addObject(creature, Coords(x, y, z));
    }
}
