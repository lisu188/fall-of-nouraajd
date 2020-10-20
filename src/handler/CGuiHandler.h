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

#include "object/CMarket.h"
#include "object/CGameObject.h"

class CListString;

class CGamePanel;

class CGuiHandler : public CGameObject {
V_META(CGuiHandler, CGameObject, vstd::meta::empty())

public:
    CGuiHandler();

    CGuiHandler(std::shared_ptr<CGame> game);

    void showMessage(std::string message);

    void showInfo(std::string message, bool centered = false);

    bool showDialog(std::string message);

    void showTrade(std::shared_ptr<CMarket> market);

    std::string showSelection(std::shared_ptr<CListString> list);

    void showTooltip(std::string text, int x, int y);

    void flipPanel(std::string panel, std::string hotkey);

private:
    std::weak_ptr<CGame> _game;
};
