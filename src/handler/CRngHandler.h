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
#pragma once

#include "core/CGlobal.h"
#include "object/CGameObject.h"

class CItem;

class CGame;

class CCreature;

class CRngHandler : public CGameObject {
public:
    CRngHandler() = default;

    explicit CRngHandler(const std::shared_ptr<CGame> &map);

    std::set<std::shared_ptr<CItem> > getRandomLoot(int value) const;

    std::set<std::shared_ptr<CCreature> > getRandomEncounter(int value) const;

    void addRandomLoot(const std::shared_ptr<CCreature> &creature, const std::set<std::shared_ptr<CItem>> &items);

    void addRandomLoot(const std::shared_ptr<CCreature> &creature, int value);

    void addRandomEncounter(const std::shared_ptr<CMap> &map, int x, int y, int z, int value);
private:
    std::set<std::shared_ptr<CItem> > calculateRandomLoot(int value) const;

    std::set<std::shared_ptr<CCreature> > calculateRandomEncounter(int value) const;

    std::weak_ptr<CGame> game;

    std::unordered_multimap<int, std::string> itemPowerTable;
    std::unordered_multimap<int, std::string> creaturePowerTable;
};
