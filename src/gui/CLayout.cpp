/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

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
#include "core/CGame.h"
#include "handler/CScriptHandler.h"
#include "gui/object/CProxyGraphicsObject.h"

std::shared_ptr<SDL_Rect> CLayout::getParentRect(std::shared_ptr<CGameGraphicsObject> object) {
    return object->getParent() ? object->getParent()->getLayout()->getRect(object->getParent()) : RECT(0, 0, 0, 0);
}

std::string CLayout::getW() {
    return w;
}

void CLayout::setW(std::string _width) {
    this->w = _width;
}

std::string CLayout::getH() {
    return h;
}

void CLayout::setH(std::string _height) {
    this->h = _height;
}

std::string CLayout::getX() {
    return x;
}

void CLayout::setX(std::string x) {
    CLayout::x = x;
}

std::string CLayout::getY() {
    return y;
}

void CLayout::setY(std::string y) {
    CLayout::y = y;
}

void CLayout::setHorizontal(std::string horizontal) {
    CLayout::horizontal = horizontal;
}

std::string CLayout::getHorizontal() {
    return horizontal;
}

void CLayout::setVertical(std::string vertical) {
    CLayout::vertical = vertical;
}

std::string CLayout::getVertical() {
    return vertical;
}

std::pair<CLayout::TYPE, int> CLayout::parseValue(std::shared_ptr<CGameGraphicsObject> object, std::string value) {
    if (vstd::ends_with(value, "%") && vstd::is_int(value.substr(0, value.length() - 1))) {
        return std::make_pair(PERCENT, vstd::to_int(value.substr(0, value.length() - 1)).first);
    } else if (vstd::is_int(value)) {
        return std::make_pair(SIMPLE, vstd::to_int(value).first);
    }
    //TODO: rethink parsing and validating script and script output
    return std::make_pair(SIMPLE, object->getGame()
            ->getScriptHandler()
            ->call_created_function<int, std::shared_ptr<CGameGraphicsObject>>(
                    value, {"self"}, object));
}

int CLayout::parseValue(std::pair<TYPE, int> value, int parentValue) {
    switch (value.first) {
        case SIMPLE:
            return value.second;
        case PERCENT:
            return value.second * parentValue / 100.0;
    }
    return vstd::fail_if(true, "Should not happen!");
}

int CLayout::parseValue(std::shared_ptr<CGameGraphicsObject> object, std::string value, int parentValue) {
    return parseValue(parseValue(object, value), parentValue);
}

std::shared_ptr<SDL_Rect> CLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto parent = getParentRect(object);

    int x = parseValue(object, getX(), parent->w);
    int y = parseValue(object, getY(), parent->h);
    int w = horizontal == "PARENT" ? parent->w : parseValue(object, getW(), parent->w);
    int h = vertical == "PARENT" ? parent->h : parseValue(object, getH(), parent->h);

    if (horizontal == "LEFT" || horizontal == "PARENT") {
        x = 0;
    } else if (horizontal == "RIGHT") {
        x = parent->w - w;
    } else if (horizontal == "CENTER") {
        x = parent->w / 2 - w / 2;
    } else if (!horizontal.empty()) {
        vstd::logger::debug("Unknown horizontal layout:", horizontal);
    }

    if (vertical == "UP" || vertical == "PARENT") {
        y = 0;
    } else if (vertical == "DOWN") {
        y = parent->h - h;
    } else if (vertical == "CENTER") {
        y = parent->h / 2 - h / 2;
    } else if (!vertical.empty()) {
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

std::shared_ptr<SDL_Rect> CProxyGraphicsLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto pRect = getParentRect(object);
    return RECT(pRect->x + vstd::cast<CProxyGraphicsObject>(object)->getX() * tileSize,
                pRect->y + vstd::cast<CProxyGraphicsObject>(object)->getY() * tileSize,
                tileSize, tileSize);
}
