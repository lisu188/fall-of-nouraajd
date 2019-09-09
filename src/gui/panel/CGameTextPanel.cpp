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
 */#include "CGameTextPanel.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

std::string CGameTextPanel::getText() {
    return text;
}

void CGameTextPanel::setText(std::string _text) {
    text = _text;
}

void CGameTextPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawText(text, pRect->x, pRect->y, pRect->w);

}

void CGameTextPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
//TODO: get rid of this
    if (i == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameTextPanel>());
    }
}

CGameTextPanel::~CGameTextPanel() {

}
