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
#include "core/CUtil.h"

#include <algorithm>

template <> std::string vstd::str(Coords coords) { return vstd::str(coords.x, ",", coords.y, ",", coords.z); }

std::shared_ptr<SDL_Rect> CUtil::boxInBox(const std::shared_ptr<SDL_Rect> &out, const std::shared_ptr<SDL_Rect> &in) {
    return rect(out->x + out->w / 2 - in->w / 2, out->y + out->h / 2 - in->h / 2, in->w, in->h);
}

std::shared_ptr<SDL_Rect> CUtil::rect(int x, int y, int w, int h) {
    std::shared_ptr<SDL_Rect> ret = std::make_shared<SDL_Rect>();
    ret->x = x;
    ret->y = y;
    ret->w = w;
    ret->h = h;
    return ret;
}

std::shared_ptr<SDL_Rect> CUtil::centeredRect(int centerX, int centerY, int w, int h) {
    return rect(centerX - w / 2, centerY - h / 2, w, h);
}

std::shared_ptr<SDL_Rect> CUtil::bounds(const std::shared_ptr<SDL_Rect> &rect) {
    return CUtil::rect(rect->x, rect->x + rect->w, rect->y, rect->y + rect->h);
}

bool CUtil::isIn(const std::shared_ptr<SDL_Rect> &rect, int x, int y) {
    auto bound = bounds(rect);
    return x >= bound->x && x <= bound->y && y >= bound->w && y <= bound->h;
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

Coords::Direction CUtil::getDirection(Coords coords) {
    constexpr std::array<std::pair<Coords, Coords::Direction>, 7> directions{{
        {ZERO, Coords::Direction::ZERO},
        {EAST, Coords::Direction::EAST},
        {WEST, Coords::Direction::WEST},
        {NORTH, Coords::Direction::NORTH},
        {SOUTH, Coords::Direction::SOUTH},
        {UP, Coords::Direction::UP},
        {DOWN, Coords::Direction::DOWN},
    }};
    const auto match = std::ranges::find_if(directions, [coords](const auto &entry) { return entry.first == coords; });
    return match != directions.end() ? match->second : Coords::Direction::UNDEFINED;
}

int CUtil::setRenderDrawColor(SDL_Renderer *renderer, SDL_Color color) {
    return SDL_SAFE(SDL_SetRenderDrawColor(renderer, color.r, color.g, color.b, color.a));
}

// TODO: implement drag_drop
