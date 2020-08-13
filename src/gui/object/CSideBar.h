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

#include "CGameGraphicsObject.h"

class CMapStringString;

class CSideBar : public CGameGraphicsObject {
V_META(CSideBar, CGameGraphicsObject,
       V_PROPERTY(CSideBar, std::shared_ptr<CMapStringString>, panelKeys, getPanelKeys, setPanelKeys),
       V_METHOD(CSideBar, clickInventory, void, std::shared_ptr<CGui>),
       V_METHOD(CSideBar, clickJournal, void, std::shared_ptr<CGui>),
       V_METHOD(CSideBar, clickCharacter, void, std::shared_ptr<CGui>))
public:
    void clickInventory(std::shared_ptr<CGui> gui);

    void clickJournal(std::shared_ptr<CGui> gui);

    void clickCharacter(std::shared_ptr<CGui> gui);

    std::shared_ptr<CMapStringString> getPanelKeys();

    void setPanelKeys(std::shared_ptr<CMapStringString> panelKeys);

    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

private:

    void flipPanel(std::shared_ptr<CGui> gui, std::string panel);

    std::shared_ptr<CMapStringString> panelKeys;
};