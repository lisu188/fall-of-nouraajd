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

#include "core/CList.h"
#include "gui/object/CGameGraphicsObject.h"

class CMapGraphicsObject : public CGameGraphicsObject {
V_META(CMapGraphicsObject, CGameGraphicsObject,
       V_PROPERTY(CMapGraphicsObject, std::shared_ptr<CMapStringString>, panelKeys, getPanelKeys, setPanelKeys),
       V_METHOD(CMapGraphicsObject, initialize))


public:
    CMapGraphicsObject();

    void renderObject(std::shared_ptr<CGui> gui, int frameTime) override;

    std::shared_ptr<CMapStringString> getPanelKeys();

    void setPanelKeys(std::shared_ptr<CMapStringString> panelKeys);

    void initialize();

private:
    std::shared_ptr<CMapStringString> panelKeys;

};

