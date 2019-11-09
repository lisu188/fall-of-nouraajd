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

#include "CLayout.h"


int CSimpleLayout::getWidth() {
    return width;
}

void CSimpleLayout::setWidth(int _width) {
    width = _width;
}

int CSimpleLayout::getHeight() {
    return height;
}

void CSimpleLayout::setHeight(int _height) {
    height = _height;
}

int CSimpleLayout::getX() {
    return x;
}

void CSimpleLayout::setX(int _x) {
    x = _x;
}

int CSimpleLayout::getY() {
    return y;
}

void CSimpleLayout::setY(int _y) {
    y = _y;
}

std::shared_ptr<SDL_Rect> CSimpleLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto parentRect = getParentRect(object);
    return RECT(
            parentRect->x + getX(),
            parentRect->y + getY(),
            width,
            height);
}

std::shared_ptr<SDL_Rect> CLayout::getParentRect(std::shared_ptr<CGameGraphicsObject> object) {
    return object->getParent() ? object->getParent()->getLayout()->getRect(object->getParent()) : RECT(0, 0, 0, 0);
}

std::shared_ptr<SDL_Rect> CCenteredLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    return CUtil::boxInBox(getParentRect(object), RECT(0, 0, width, height));
}

int CPercentLayout::getX() {
    return x;
}

void CPercentLayout::setX(int x) {
    CPercentLayout::x = x;
}

int CPercentLayout::getY() {
    return y;
}

void CPercentLayout::setY(int y) {
    CPercentLayout::y = y;
}

int CPercentLayout::getW() {
    return w;
}

void CPercentLayout::setW(int w) {
    CPercentLayout::w = w;
}

int CPercentLayout::getH() {
    return h;
}

void CPercentLayout::setH(int h) {
    CPercentLayout::h = h;
}

std::shared_ptr<SDL_Rect> CLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    return RECT(0, 0, 0, 0);
}


std::shared_ptr<SDL_Rect> CPercentLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto pRect = getParentRect(object);
    return RECT(pRect->x + pRect->w * x / 100.0,
                pRect->y + pRect->h * y / 100.0,
                pRect->w * w / 100.0,
                pRect->h * h / 100.0);
}

std::shared_ptr<SDL_Rect> CMapGraphicsProxyLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    int tileSize = object->getTopParent()->getNumericProperty("tileSize");
    return RECT(object->getNumericProperty("x") * tileSize,
                object->getNumericProperty("y") * tileSize,
                tileSize, tileSize);
}

