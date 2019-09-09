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
#include "CGameDialogPanel.h"
#include "gui/CGui.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CGameDialogPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawTextCentered(question, getTextRect(pRect));
    gui->getTextManager()->drawTextCentered("YES", getLeftButtonRect(pRect));
    gui->getTextManager()->drawTextCentered("NO", getRightButtonRect(pRect));
}


void CGameDialogPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {

}

std::string CGameDialogPanel::getQuestion() {
    return question;
}

void CGameDialogPanel::setQuestion(std::string question) {
    this->question = question;
}

std::shared_ptr<SDL_Rect> CGameDialogPanel::getTextRect(std::shared_ptr<SDL_Rect> pRect) {
    return RECT(pRect->x, pRect->y, pRect->w, (getYSize() - 100));
}

std::shared_ptr<SDL_Rect> CGameDialogPanel::getLeftButtonRect(std::shared_ptr<SDL_Rect> pRect) {
    return RECT(pRect->x,
                pRect->y + (getYSize() - 100),
                pRect->w / 2, 100);
}

std::shared_ptr<SDL_Rect> CGameDialogPanel::getRightButtonRect(std::shared_ptr<SDL_Rect> pRect) {
    return RECT(pRect->x + (getXSize() / 2),
                pRect->y + (getYSize() - 100),
                pRect->w / 2, 100);
}

bool CGameDialogPanel::awaitAnswer() {
    vstd::wait_until([this]() {
        return selection != nullptr;
    });
    return *selection;
}

void CGameDialogPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    if (CUtil::isIn(getLeftButtonRect(RECT(0, 0, getXSize(), getYSize())), x, y)) {
        selection = std::make_shared<bool>(true);
        gui->removeObject(this->ptr<CGameDialogPanel>());
    } else if (CUtil::isIn(getRightButtonRect(RECT(0, 0, getXSize(), getYSize())), x, y)) {
        selection = std::make_shared<bool>(false);
        gui->removeObject(this->ptr<CGameDialogPanel>());
    }
}
