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

class CLootHandler : public CGameObject {
public:
    CLootHandler() = default;

    explicit CLootHandler(const std::shared_ptr<CGame> &map);

    std::set<std::shared_ptr<CItem> > getLoot(int value) const;

    void addLoot(const std::shared_ptr<CCreature> &creature, const std::set<std::shared_ptr<CItem>> &items);

    void addLoot(const std::shared_ptr<CCreature> &creature, int value);

private:
    std::set<std::shared_ptr<CItem> > calculateLoot(int value) const;

    std::weak_ptr<CGame> game;

    std::unordered_multimap<int, std::string> powerTable;
};
