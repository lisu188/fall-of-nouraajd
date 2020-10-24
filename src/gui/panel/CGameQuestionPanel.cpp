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
#include "CGameQuestionPanel.h"
#include "gui/CGui.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"


std::string CGameQuestionPanel::getQuestion() {
    return question;
}

void CGameQuestionPanel::setQuestion(std::string question) {
    this->question = question;
}

bool CGameQuestionPanel::awaitAnswer() {
    vstd::wait_until([this]() {
        return selection != nullptr;
    });
    return *selection;
}

void CGameQuestionPanel::clickNo(std::shared_ptr<CGui> gui) {
    selection = std::make_shared<bool>(false);
    close();
}

void CGameQuestionPanel::clickYes(std::shared_ptr<CGui> gui) {
    selection = std::make_shared<bool>(true);
    close();
}

void CGameQuestionPanel::renderQuestion(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawTextCentered(question, pRect);
}