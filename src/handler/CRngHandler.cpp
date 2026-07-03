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
#include "CRngHandler.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CUtil.h"
#include "object/CObject.h"

#include <algorithm>

namespace {
constexpr int MAX_RANDOM_VALUE = 1000;

int clampRandomValue(int value) { return std::clamp(value, 0, MAX_RANDOM_VALUE); }
} // namespace

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

CRngHandler::CRngHandler(const std::shared_ptr<CGame> &game) : game(game) {
    for (const std::string &type : game->getObjectHandler()->getAllSubTypes("CItem")) {
        std::shared_ptr<CItem> item = game->createObject<CItem>(type);
        if (item) {
            int power = item->getPower();
            // Compound artifacts are assembled from set pieces, never dropped or sold
            // directly (docs/design/compound_artifacts.md); exclude them from random loot
            // the same way quest items are excluded.
            if (power > 0 && !item->hasTag(CTag::Quest) && !item->hasTag(CTag::Compound)) {
                itemPowerTable.insert(std::make_pair(power, type));
            }
        }
    }

    for (const std::string &type : game->getObjectHandler()->getAllSubTypes("CCreature")) {
        // getAllSubTypes("CCreature") also returns player templates because CPlayer inherits
        // CCreature (src/object/CPlayer.h:24, registered via NativePlugin.cpp). Random encounters
        // must never spawn a player template, so skip any candidate whose resolved class inherits
        // CPlayer -- the same meta()->inherits(...) test getAllSubTypes itself applies for the
        // CCreature gate (src/handler/CObjectHandler.cpp:115). Genuine monster candidates and their
        // sw power buckets are untouched.
        auto candidateClass = game->getObjectHandler()->getType(game->getObjectHandler()->getClass(type));
        if (candidateClass && candidateClass->meta()->inherits("CPlayer")) {
            continue;
        }
        std::shared_ptr<CCreature> creature = game->createObject<CCreature>(type);
        if (creature) {
            int power = creature->getSw();
            creaturePowerTable.insert(std::make_pair(power, type));
        }
    }
}

std::set<std::shared_ptr<CItem>> CRngHandler::calculateRandomLoot(int value) const {
    std::set<std::shared_ptr<CItem>> loot;
    auto currentGame = game.lock();
    if (!currentGame) {
        return loot;
    }
    value = clampRandomValue(value);
    for (auto pow : vstd::random_components(value, itemPowerTable | std::views::keys)) {
        std::set<std::string> possible_names;
        auto range = itemPowerTable.equal_range(pow);
        for (auto it = range.first; it != range.second; it++) {
            possible_names.insert(it->second);
        }
        if (!possible_names.empty()) {
            loot.insert(currentGame->createObject<CItem>(*vstd::random_element(possible_names)));
        }
        value -= pow;
    }
    return loot;
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
            creature->addExp(creature->getExpForLevel(pow - sw));
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
