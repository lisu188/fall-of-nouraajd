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
#include "core/CJsonUtil.h"
#include "CGameCharacterPanel.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CGameCharacterPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int i) {
    std::string text;
    for (auto prop : charSheet->getValues()) {
        text += prop + ": " + vstd::str(gui->getGame()->getMap()->getPlayer()->getNumericProperty(prop)) + "\n";
    }
    gui->getTextManager()->drawText(
            text,
            rect->x,
            rect->y,
            rect->w);

}


CGameCharacterPanel::~CGameCharacterPanel() {

}

std::shared_ptr<CListString> CGameCharacterPanel::getCharSheet() {
    return charSheet;
}

void CGameCharacterPanel::setCharSheet(std::shared_ptr<CListString> charSheet) {
    CGameCharacterPanel::charSheet = charSheet;
}
