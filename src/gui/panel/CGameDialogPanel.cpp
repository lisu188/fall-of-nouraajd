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
#include "CGameDialogPanel.h"
#include "gui/CGui.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"


std::string CGameDialogPanel::getQuestion() {
    return question;
}

void CGameDialogPanel::setQuestion(std::string question) {
    this->question = question;
}

bool CGameDialogPanel::awaitAnswer() {
    vstd::wait_until([this]() {
        return selection != nullptr;
    });
    return *selection;
}


void CGameDialogPanel::clickNo(std::shared_ptr<CGui> gui) {
    selection = std::make_shared<bool>(false);
    gui->removeChild(this->ptr<CGameDialogPanel>());
}

void CGameDialogPanel::clickYes(std::shared_ptr<CGui> gui) {
    selection = std::make_shared<bool>(true);
    gui->removeChild(this->ptr<CGameDialogPanel>());
}


void CGameDialogPanel::renderQuestion(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawTextCentered(question, pRect);
}

void CGameDialogPanel::renderYes(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawTextCentered("YES", pRect);
}

void CGameDialogPanel::renderNo(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawTextCentered("NO", pRect);
}
