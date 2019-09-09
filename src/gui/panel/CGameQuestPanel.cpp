//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#include "CGameQuestPanel.h"
#include "gui/CGui.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CGameQuestPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawText(getText(gui), pRect->x, pRect->y, pRect->w);
}


std::string CGameQuestPanel::getText(std::shared_ptr<CGui> ptr) {
    std::__cxx11::string text = "";
    for (auto quest:ptr->getGame()->getMap()->getPlayer()->getCompletedQuests()) {
        text += quest->getDescription();
            text += "(completed)";
        text += "\n";
    }
    for (auto quest:ptr->getGame()->getMap()->getPlayer()->getQuests()) {
        text += quest->getDescription();
        text += "\n";
    }
    return text;
}

void CGameQuestPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {

}
