/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "core/CUtil.h"
#include "object/CObject.h"
#include "core/CGame.h"
#include "core/CMap.h"

std::set<std::shared_ptr<CItem>> CRngHandler::getRandomLoot(int value) const {
    return calculateRandomLoot(value);
}

std::set<std::shared_ptr<CCreature>> CRngHandler::getRandomEncounter(int value) const {
    return calculateRandomEncounter(value);
}

CRngHandler::CRngHandler(const std::shared_ptr<CGame> &game) : game(game) {
    for (const std::string &type: game->getObjectHandler()->getAllSubTypes("CItem")) {
        std::shared_ptr<CItem> item = game->createObject<CItem>(type);
        if (item) {
            int power = item->getPower();
            if (power > 0 && !item->hasTag("quest")) {
                itemPowerTable.insert(std::make_pair(power, type));
            }
        }
    }

    for (const std::string &type: game->getObjectHandler()->getAllSubTypes("CMonster")) {
        std::shared_ptr<CCreature> creature = game->createObject<CCreature>(type);
        if (creature) {
            int power = creature->getSw();
            creaturePowerTable.insert(std::make_pair(power, type));
        }
    }
}

std::set<std::shared_ptr<CItem>> CRngHandler::calculateRandomLoot(int value) const {
    std::set<std::shared_ptr<CItem>> loot;
    for (auto pow: vstd::random_components(value, itemPowerTable | boost::adaptors::map_keys)) {
        std::set<std::string> possible_names;
        auto range = itemPowerTable.equal_range(pow);
        for (auto it = range.first; it != range.second; it++) {
            possible_names.insert(it->second);
        }
        if (!possible_names.empty()) {
            loot.insert(game.lock()->createObject<CItem>(vstd::random_element(possible_names)));
        }
        value -= pow;
    }
    return loot;
}

void
CRngHandler::addRandomLoot(const std::shared_ptr<CCreature> &creature, const std::set<std::shared_ptr<CItem>> &items) {
    //TODO: polymorphic
    if (vstd::castable<CPlayer>(creature)) {
        creature->getGame()->getGuiHandler()->showLoot(creature, items);
    }
    creature->addItems(items);
}

void CRngHandler::addRandomLoot(const std::shared_ptr<CCreature> &creature, int value) {
    addRandomLoot(creature, getRandomLoot(value));
}

std::set<std::shared_ptr<CCreature> > CRngHandler::calculateRandomEncounter(int value) const {
    std::set<std::shared_ptr<CCreature>> encounter;
    for (int pow: vstd::random_components(value, boost::irange(1, value + 1))) {
        auto possiblePowersRange =
                creaturePowerTable | boost::adaptors::map_keys | boost::adaptors::filtered([pow](int it) {
                    return it <= pow;
                });
        //TODO: util for range copy
        std::set<int> possiblePowers(possiblePowersRange.begin(), possiblePowersRange.end());
        auto sw = vstd::random_element(possiblePowers);
        std::set<std::string> possible_names;
        auto range = creaturePowerTable.equal_range(sw);
        for (auto it = range.first; it != range.second; it++) {
            possible_names.insert(it->second);
        }
        if (!possible_names.empty()) {
            auto creature = game.lock()->createObject<CCreature>(
                    vstd::random_element(possible_names));
            creature->addExp(creature->getExpForLevel(pow - sw));
            encounter.insert(creature);
        }
        value -= pow;
    }
    return encounter;
}

void CRngHandler::addRandomEncounter(const std::shared_ptr<CMap> &map, int x, int y, int z, int value) {
    for (auto creature:getRandomEncounter(value)) {
        map->addObject(creature, Coords(x, y, z));
    }
}
