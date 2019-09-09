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

double Coords::getDist(Coords a) const {
    double x = this->x - a.x;
    x *= x;
    double y = this->y - a.y;
    y *= y;
    return sqrt(x + y);
}

SDL_Rect CUtil::boxInBox(SDL_Rect *out, SDL_Rect *in) {
    SDL_Rect actual;
    actual.x = out->x + out->w / 2 - in->w / 2;
    actual.y = out->y + out->h / 2 - in->h / 2;
    actual.w = in->w;
    actual.h = in->h;
    return actual;
}

SDL_Rect CUtil::boxInBox(SDL_Rect out, SDL_Rect *in) {
    return boxInBox(&out, in);
}


SDL_Rect CUtil::boxInBox(SDL_Rect *out, SDL_Rect in) {
    return boxInBox(out, &in);
}


SDL_Rect CUtil::boxInBox(SDL_Rect out, SDL_Rect in) {
    return boxInBox(&out, &in);
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

//TODO: implement drag_drop