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

#include "CWidget.h"
#include "gui/CTextManager.h"

void CWidget::setRender(std::string draw) {
    this->render = draw;
}

std::string CWidget::getRender() {
    return render;
}

std::string CWidget::getClick() {
    return click;
}

void CWidget::setClick(std::string click) {
    this->click = click;
}

void CWidget::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    this->getParent()->meta()->invoke_method<void, CGameGraphicsObject,
            std::shared_ptr<CGui>,
            std::shared_ptr<SDL_Rect>, int>(this->getRender(),
                                            getParent(),
                                            gui,
                                            rect,
                                            frameTime);
}

bool CWidget::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {
        this->getParent()->meta()->invoke_method<void, CGameGraphicsObject,
                std::shared_ptr<CGui>>(this->getClick(),
                                       getParent(),
                                       gui);
    }
    return true;
}

CWidget::CWidget() {

}

void CTextWidget::setText(std::string _text) {
    text = _text;
}

std::string CTextWidget::getText() {
    return text;
}

void CTextWidget::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    gui->getTextManager()->drawTextCentered(vstd::str(text), rect);
}

CButton::CButton() {

}

bool CButton::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {
        setBackground("images/button_on");
        setModal(true);
    } else if (type == SDL_MOUSEBUTTONUP && button == SDL_BUTTON_LEFT) {
        setBackground("images/button_off");
        setModal(false);
    }
    return CTextWidget::mouseEvent(sharedPtr, type, button, x, y);
}