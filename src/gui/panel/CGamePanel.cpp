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
#include "CGamePanel.h"
#include "gui/CGui.h"
#include "gui/object/CWidget.h"


void CGamePanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    SDL_RenderFillRect(gui->getRenderer(), rect.get());
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/panel.png"), nullptr, rect.get());
}

std::set<std::shared_ptr<CWidget>> CGamePanel::getWidgets() {
    return widgets;
}

void CGamePanel::setWidgets(std::set<std::shared_ptr<CWidget>> widgets) {
    CGamePanel::widgets = widgets;
}

bool CGamePanel::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    return true;
}

bool CGamePanel::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y) {
    return true;
}
