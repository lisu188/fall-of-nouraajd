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
#include "CLootHandler.h"
#include "core/CUtil.h"
#include "object/CObject.h"
#include "core/CGame.h"

std::set<std::shared_ptr<CItem>> CLootHandler::getLoot(int value) const {
    return calculateLoot(value);
}

CLootHandler::CLootHandler(const std::shared_ptr<CGame> &game) : game(game) {
    for (const std::string &type : game->getObjectHandler()->getAllSubTypes("CItem")) {
        std::shared_ptr<CItem> item = game->createObject<CItem>(type);
        if (item) {
            int power = item->getPower();
            if (power > 0 && !item->hasTag("quest")) {
                powerTable.insert(std::make_pair(power, type));
            }
        }
    }
}

std::set<std::shared_ptr<CItem>> CLootHandler::calculateLoot(int value) const {
    std::set<std::shared_ptr<CItem>> loot;
    std::list<int> powers;
    while (value > 0) {
        std::set<int> possible_values;
        for (const auto &it:powerTable) {
            if (it.first <= value) {
                possible_values.insert(it.first);
            }
        }
        if (possible_values.empty()) {
            break;
        }
        int pow = vstd::random_element(possible_values);
        std::set<std::string> possible_names;
        auto range = powerTable.equal_range(pow);
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

void CLootHandler::addLoot(const std::shared_ptr<CCreature> &creature, const std::set<std::shared_ptr<CItem>> &items) {
    //TODO: polymorphic
    if (vstd::castable<CPlayer>(creature)) {
        creature->getGame()->getGuiHandler()->showLoot(creature, items);
    }
    creature->addItems(items);
}

void CLootHandler::addLoot(const std::shared_ptr<CCreature> &creature, int value) {
    addLoot(creature, getLoot(value));
}
