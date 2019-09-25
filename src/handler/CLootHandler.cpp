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

CLootHandler::CLootHandler(std::shared_ptr<CGame> game) : game(game) {
    for (std::string type : game->getObjectHandler()->getAllSubTypes("CItem")) {
        std::shared_ptr<CItem> item = game->createObject<CItem>(type);
        if (item) {
            int power = item->getPower();
            if (power > 0) {
                this->insert(std::make_pair(type, power));
            }
        }
    }
}

std::set<std::shared_ptr<CItem>> CLootHandler::calculateLoot(int value) const {
    std::set<std::shared_ptr<CItem>> loot;
    std::list<int> powers;
    while (value > 0) {
        int pow = rand() % value + 1;
        value -= pow;
        powers.push_back(pow);
    }
    for (int val:powers) {
        std::vector<std::string> names;
        for (std::pair<std::string, int> it:*this) {
            if (it.second == val) {
                names.push_back(it.first);
            }
        }
        if (names.size() > 0) {
            std::random_shuffle(names.begin(), names.end());
            loot.insert(game.lock()->createObject<CItem>(names.front()));
        }
    }
    return loot;
}
