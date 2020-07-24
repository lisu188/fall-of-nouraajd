/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2020  Andrzej Lis

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

#include "gui/object/CProxyTargetGraphicsObject.h"

class CCreatureView : public CProxyTargetGraphicsObject {
V_META(CCreatureView, CProxyTargetGraphicsObject,
       V_PROPERTY(CCreatureView, std::string, creature, getCreature, setCreature),
       V_METHOD(CCreatureView, initialize))
public:
    std::string getCreature();

    void setCreature(std::string _creature);

    std::set<std::shared_ptr<CGameGraphicsObject>> getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) override;

    int getSizeX(std::shared_ptr<CGui> gui) override;

    int getSizeY(std::shared_ptr<CGui> gui) override;

    void initialize();

private:
    std::string creature;
};