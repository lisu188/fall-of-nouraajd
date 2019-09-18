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
#include "core/CWidget.h"

void CGameDialogPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    for (auto widget:widgets) {
        this->meta()->invoke_method<void, CGameDialogPanel,
                std::shared_ptr<CGui>,
                std::shared_ptr<SDL_Rect>, int>(widget->getRender(),
                                                this->ptr<CGameDialogPanel>(), gui,
                                                widget->getRect(pRect), i);
    }
}


void CGameDialogPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {

}

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

void CGameDialogPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    for (auto widget:widgets) {
        if (CUtil::isIn(widget->getRect(RECT(0, 0, getXSize(), getYSize())), x, y)) {
            this->meta()->invoke_method<void, CGameDialogPanel,
                    std::shared_ptr<CGui>>(widget->getClick(),
                                           this->ptr<CGameDialogPanel>(),
                                           gui);
        }
    }
}

void CGameDialogPanel::clickNo(std::shared_ptr<CGui> gui) {
    selection = std::make_shared<bool>(false);
    gui->removeObject(this->ptr<CGameDialogPanel>());
}

void CGameDialogPanel::clickYes(std::shared_ptr<CGui> gui) {
    selection = std::make_shared<bool>(true);
    gui->removeObject(this->ptr<CGameDialogPanel>());
}

std::set<std::shared_ptr<CWidget>> CGameDialogPanel::getWidgets() {
    return widgets;
}

void CGameDialogPanel::setWidgets(std::set<std::shared_ptr<CWidget>> widgets) {
    CGameDialogPanel::widgets = widgets;
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
