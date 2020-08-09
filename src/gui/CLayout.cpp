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


int CSimpleLayout::getW() {
    return w;
}

void CSimpleLayout::setW(int _width) {
    w = _width;
}

int CSimpleLayout::getH() {
    return h;
}

void CSimpleLayout::setH(int _height) {
    h = _height;
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
            w,
            h);
}

std::shared_ptr<SDL_Rect> CLayout::getParentRect(std::shared_ptr<CGameGraphicsObject> object) {
    return object->getParent() ? object->getParent()->getLayout()->getRect(object->getParent()) : RECT(0, 0, 0, 0);
}

int CAnchoredLayout::getW() {
    return w;
}

void CAnchoredLayout::setW(int _width) {
    this->w = _width;
}

int CAnchoredLayout::getH() {
    return h;
}

void CAnchoredLayout::setH(int _height) {
    this->h = _height;
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

std::shared_ptr<SDL_Rect> CProxyGraphicsLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto pRect = getParentRect(object);
    return RECT(pRect->x + object->getNumericProperty("x") * tileSize,
                pRect->y + object->getNumericProperty("y") * tileSize,
                tileSize, tileSize);
}


void CAnchoredLayout::setHorizontal(std::string horizontal) {
    CAnchoredLayout::horizontal = horizontal;
}

std::string CAnchoredLayout::getHorizontal() {
    return horizontal;
}

void CAnchoredLayout::setVertical(std::string vertical) {
    CAnchoredLayout::vertical = vertical;
}

std::string CAnchoredLayout::getVertical() {
    return vertical;
}

//TODO: parse percent
std::shared_ptr<SDL_Rect> CAnchoredLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto parent = getParentRect(object);
    int x = 0;
    int y = 0;
    int w = horizontal == "PARENT" ? parent->w : getW();
    int h = vertical == "PARENT" ? parent->h : getH();

    if (horizontal == "LEFT" || horizontal == "PARENT") {
        x = 0;
    } else if (horizontal == "RIGHT") {
        x = parent->w - getW();
    } else if (horizontal == "CENTER") {
        x = parent->w / 2 - getH() / 2;
    } else {
        vstd::logger::debug("Unknown horizontal layout:", horizontal);
    }

    if (vertical == "UP" || vertical == "PARENT") {
        y = 0;
    } else if (vertical == "DOWN") {
        y = parent->h - getH();
    } else if (vertical == "CENTER") {
        y = parent->h / 2 - getH() / 2;
    } else {
        vstd::logger::debug("Unknown vertical layout:", vertical);
    }

    return RECT(parent->x + x, parent->y + y, w, h);
}

CParentLayout::CParentLayout() {
    setHorizontal("PARENT");
    setVertical("PARENT");
}

CCenteredLayout::CCenteredLayout() {
    setHorizontal("CENTER");
    setVertical("CENTER");
}

void CProxyGraphicsLayout::setTileSize(int _tileSize) {
    tileSize = _tileSize;
}

int CProxyGraphicsLayout::getTileSize() {
    return tileSize;
}