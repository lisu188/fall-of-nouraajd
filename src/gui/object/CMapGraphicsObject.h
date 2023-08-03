/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

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

#include "core/CList.h"
#include "gui/object/CProxyTargetGraphicsObject.h"

class CProxyGraphicsObject;

class CMapGraphicsObject : public CProxyTargetGraphicsObject {
V_META(CMapGraphicsObject, CProxyTargetGraphicsObject,
       V_METHOD(CMapGraphicsObject, initialize),
       V_METHOD(CMapGraphicsObject, refreshObject, void, Coords))

public:
    CMapGraphicsObject();

    void initialize();

    std::list<std::shared_ptr<CGameGraphicsObject>>
    getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) override;

    int getSizeX(std::shared_ptr<CGui> gui) override;

    int getSizeY(std::shared_ptr<CGui> gui) override;

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) override;

    void refreshObject(Coords coords);

private:
    Coords guiToMap(std::shared_ptr<CGui> gui, Coords coords);

    Coords mapToGui(std::shared_ptr<CGui> gui, Coords coords);

    void showCoordinates(std::shared_ptr<CGui> &gui, std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                         const Coords &actualCoords) const;

    void showFootprint(std::shared_ptr<CGui> &gui, std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                       const Coords &actualCoords) const;
};


