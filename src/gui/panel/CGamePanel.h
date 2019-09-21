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
       V_PROPERTY(CGamePanel, int, xSize, getXSize, setXSize),
       V_PROPERTY(CGamePanel, int, ySize, getYSize, setYSize),
       V_PROPERTY(CGamePanel, std::set<std::shared_ptr<CWidget>>, widgets, getWidgets, setWidgets))
public:
    int getXSize();

    void setXSize(int _xSize);

    int getYSize();

    void setYSize(int _ySize);

    void render(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> pos, int frameTime) override;

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

    std::pair<int, int> translatePos(std::shared_ptr<CGui> gui, int x, int y);;

    std::shared_ptr<SDL_Rect> getPanelRect(std::shared_ptr<SDL_Rect> pos);;

private:
    std::set<std::shared_ptr<CWidget>> widgets;

public:
    std::set<std::shared_ptr<CWidget>> getWidgets();

    void setWidgets(std::set<std::shared_ptr<CWidget>> widgets);

protected:


    virtual void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i);

    virtual void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i);

    virtual void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y);

private:


    int xSize = 800;
    int ySize = 600;
};

