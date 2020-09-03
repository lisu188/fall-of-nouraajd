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
    for (auto[key, value] : charSheet->getValues()) {
        std::shared_ptr<CPlayer> player = gui->getGame()->getMap()->getPlayer();
        text += key + ": " + vstd::str(player->meta()->invoke_method<int>(value, player)) + "\n";
    }
    gui->getTextManager()->drawText(
            text,
            rect->x,
            rect->y,
            rect->w);

}


CGameCharacterPanel::~CGameCharacterPanel() {

}

std::shared_ptr<CMapStringString> CGameCharacterPanel::getCharSheet() {
    return charSheet;
}

void CGameCharacterPanel::setCharSheet(std::shared_ptr<CMapStringString> charSheet) {
    CGameCharacterPanel::charSheet = charSheet;
}

CListView::collection_pointer CGameCharacterPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(
            vstd::cast<CListView::collection_type>(gui->getGame()->getMap()->getPlayer()->getInteractions()));
}