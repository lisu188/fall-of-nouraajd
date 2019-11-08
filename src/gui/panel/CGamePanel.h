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


#include "gui/object/CGameGraphicsObject.h"
#include "gui/CGui.h"
#include "gui/panel/CListView.h"

class CWidget;

class CGamePanel : public CGameGraphicsObject {
V_META(CGamePanel, CGameGraphicsObject,
       V_PROPERTY(CGamePanel, std::set<std::shared_ptr<CWidget>>, widgets, getWidgets, setWidgets))
public:
    void renderObject(std::shared_ptr<CGui> reneder,  int frameTime) override;

private:
    std::set<std::shared_ptr<CWidget>> widgets;

public:
    std::set<std::shared_ptr<CWidget>> getWidgets();

    void setWidgets(std::set<std::shared_ptr<CWidget>> widgets);

    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

    bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) override;
};

