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
#include "core/CUtil.h"

template<>
std::string vstd::str(Coords coords) {
    return vstd::str(coords.x) + "," + vstd::str(coords.y) + "," + vstd::str(coords.z);
}

Coords::Coords() { x = y = z = 0; }

Coords::Coords(int x, int y, int z) : x(x), y(y), z(z) {}

bool Coords::operator==(const Coords &other) const {
    return (x == other.x && y == other.y && z == other.z);
}

bool Coords::operator!=(const Coords &other) const {
    return !operator==(other);
}

bool Coords::operator<(const Coords &other) const {
    if (x < other.x) {
        return true;
    }
    if (y < other.y && x == other.x) {
        return true;
    }
    if (z < other.z && x == other.x && y == other.y) {
        return true;
    }
    return false;
}

bool Coords::operator>(const Coords &other) const {
    return !operator<(other);
}

Coords Coords::operator-(const Coords &other) const {
    return Coords(x - other.x, y - other.y, z - other.z);
}

Coords Coords::operator+(const Coords &other) const {
    return Coords(x + other.x, y + other.y, z + other.z);
}

Coords Coords::operator*() const {
    return *this;
}

double Coords::getDist(const Coords &a) const {
    double x = this->x - a.x;
    x *= x;
    double y = this->y - a.y;
    y *= y;
    return sqrt(x + y);
}

bool Coords::adjacent(const Coords &a) const {
    return getDist(a) == 1;
}

bool Coords::same(const Coords &a) const {
    return getDist(a) == 0;
}

bool Coords::adjacentOrSame(const Coords &a) const {
    return adjacent(a) || same(a);
}

std::shared_ptr<SDL_Rect> CUtil::boxInBox(std::shared_ptr<SDL_Rect> out, std::shared_ptr<SDL_Rect> in) {
    return RECT(out->x + out->w / 2 - in->w / 2,
                out->y + out->h / 2 - in->h / 2,
                in->w,
                in->h);
}


std::shared_ptr<SDL_Rect> CUtil::rect(int x, int y, int w, int h) {
    std::shared_ptr<SDL_Rect> ret = std::make_shared<SDL_Rect>();
    ret->x = x;
    ret->y = y;
    ret->w = w;
    ret->h = h;
    return ret;
}

std::shared_ptr<SDL_Rect> CUtil::bounds(std::shared_ptr<SDL_Rect> rect) {
    return RECT(rect->x, rect->x + rect->w, rect->y, rect->y + rect->h);
}

bool CUtil::isIn(std::shared_ptr<SDL_Rect> rect, int x, int y) {
    auto bound = bounds(rect);
    return x >= bound->x
           && x <= bound->y
           && y >= bound->w
           && y <= bound->h;
}

int CUtil::parseKey(SDL_Keycode i) {
    switch (i) {
        case SDLK_0:
            return 0;
        case SDLK_1:
            return 1;
        case SDLK_2:
            return 2;
        case SDLK_3:
            return 3;
        case SDLK_4:
            return 4;
        case SDLK_5:
            return 5;
        case SDLK_6:
            return 6;
        case SDLK_7:
            return 7;
        case SDLK_8:
            return 8;
        case SDLK_9:
            return 9;
        default:
            return -1;
    }
}

//TODO: implement drag_drop