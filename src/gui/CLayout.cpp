/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "core/CUtil.h"
#include "gui/object/CProxyGraphicsObject.h"

#include <algorithm>
#include <optional>

namespace {
std::optional<int> parseLayoutInt(const std::string &value) {
    if (value.empty()) {
        return std::nullopt;
    }
    try {
        size_t parsed = 0;
        int result = std::stoi(value, &parsed);
        if (parsed == value.size()) {
            return result;
        }
    } catch (...) {
    }
    return std::nullopt;
}
} // namespace

std::shared_ptr<SDL_Rect> CLayout::getParentRect(std::shared_ptr<CGameGraphicsObject> object) {
    if (!object) {
        return CUtil::rect(0, 0, 0, 0);
    }
    auto parent = object->getParent();
    if (!parent) {
        return CUtil::rect(0, 0, 0, 0);
    }
    auto parentLayout = parent->getLayout();
    return parentLayout ? parentLayout->getRect(parent) : CUtil::rect(0, 0, 0, 0);
}

std::string CLayout::getW() { return w; }

void CLayout::setW(std::string _width) { this->w = _width; }

std::string CLayout::getH() { return h; }

void CLayout::setH(std::string _height) { this->h = _height; }

std::string CLayout::getX() { return x; }

void CLayout::setX(std::string x) { CLayout::x = x; }

std::string CLayout::getY() { return y; }

void CLayout::setY(std::string y) { CLayout::y = y; }

void CLayout::setRect(int x, int y, int w, int h) {
    setX(vstd::str(x));
    setY(vstd::str(y));
    setW(vstd::str(w));
    setH(vstd::str(h));
}

void CLayout::setRect(const std::shared_ptr<SDL_Rect> &rect) { setRect(rect->x, rect->y, rect->w, rect->h); }

void CLayout::setRuntimeX(int x) { runtimeX = x; }

void CLayout::setRuntimeY(int y) { runtimeY = y; }

void CLayout::setRuntimeW(int w) { runtimeW = w; }

void CLayout::setRuntimeH(int h) { runtimeH = h; }

void CLayout::setRuntimeRect(int x, int y, int w, int h) {
    setRuntimeX(x);
    setRuntimeY(y);
    setRuntimeW(w);
    setRuntimeH(h);
}

void CLayout::setRuntimeRect(const std::shared_ptr<SDL_Rect> &rect) {
    setRuntimeRect(rect->x, rect->y, rect->w, rect->h);
}

void CLayout::clearRuntimeX() { runtimeX.reset(); }

void CLayout::clearRuntimeY() { runtimeY.reset(); }

void CLayout::clearRuntimeW() { runtimeW.reset(); }

void CLayout::clearRuntimeH() { runtimeH.reset(); }

void CLayout::clearRuntimeRect() {
    clearRuntimeX();
    clearRuntimeY();
    clearRuntimeW();
    clearRuntimeH();
}

void CLayout::setHorizontal(std::string horizontal) { CLayout::horizontal = horizontal; }

std::string CLayout::getHorizontal() { return horizontal; }

void CLayout::setVertical(std::string vertical) { CLayout::vertical = vertical; }

std::string CLayout::getVertical() { return vertical; }

std::pair<CLayout::TYPE, int> CLayout::parseValue(std::string value) {
    if (vstd::ends_with(value, "%")) {
        auto parsed = parseLayoutInt(value.substr(0, value.length() - 1));
        if (parsed) {
            return std::make_pair(PERCENT, *parsed);
        }
    } else if (auto parsed = parseLayoutInt(value)) {
        return std::make_pair(SIMPLE, *parsed);
    }
    vstd::logger::error("Invalid layout value:", value);
    return std::make_pair(SIMPLE, 0);
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

int CLayout::parseValue(std::string value, int parentValue) { return parseValue(parseValue(value), parentValue); }

std::shared_ptr<SDL_Rect> CLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto parent = getParentRect(object);

    int x = parseValue(getX(), parent->w);
    int y = parseValue(getY(), parent->h);
    int w = 0;
    if (runtimeW) {
        w = *runtimeW;
    } else {
        w = horizontal == "PARENT" ? parent->w : parseValue(getW(), parent->w);
    }
    int h = 0;
    if (runtimeH) {
        h = *runtimeH;
    } else {
        h = vertical == "PARENT" ? parent->h : parseValue(getH(), parent->h);
    }

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

    x = runtimeX.value_or(x);
    y = runtimeY.value_or(y);

    return CUtil::rect(parent->x + x, parent->y + y, w, h);
}

CParentLayout::CParentLayout() {
    setHorizontal("PARENT");
    setVertical("PARENT");
}

CCenteredLayout::CCenteredLayout() {
    setHorizontal("CENTER");
    setVertical("CENTER");
}

void CProxyGraphicsLayout::setTileSize(int _tileSize) { tileSize = _tileSize; }

int CProxyGraphicsLayout::getTileSize() { return tileSize; }

std::shared_ptr<SDL_Rect> CProxyGraphicsLayout::getRect(std::shared_ptr<CGameGraphicsObject> object) {
    auto pRect = getParentRect(object);
    auto proxy = vstd::cast<CProxyGraphicsObject>(object);
    const int safeTileSize = std::clamp(tileSize, 1, 512);
    if (!proxy) {
        return CUtil::rect(pRect->x, pRect->y, safeTileSize, safeTileSize);
    }
    return CUtil::rect(pRect->x + proxy->getX() * safeTileSize, pRect->y + proxy->getY() * safeTileSize, safeTileSize,
                       safeTileSize);
}
