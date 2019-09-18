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

std::shared_ptr<SDL_Rect> CWidget::getRect(std::shared_ptr<SDL_Rect> pRect) {
    return RECT(pRect->x + pRect->w * x / 100.0,
                pRect->y + pRect->h * y / 100.0,
                pRect->w * w / 100.0,
                pRect->h * h / 100.0);
}


int CWidget::getX() {
    return x;
}

void CWidget::setX(int x) {
    CWidget::x = x;
}

int CWidget::getY() {
    return y;
}

void CWidget::setY(int y) {
    CWidget::y = y;
}

int CWidget::getW() {
    return w;
}

void CWidget::setW(int w) {
    CWidget::w = w;
}

int CWidget::getH() {
    return h;
}

void CWidget::setH(int h) {
    CWidget::h = h;
}

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
