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
#pragma once

#include "core/CGlobal.h"


class CGameObject;

class CMapObject;

struct Coords {
    Coords();

    Coords(int x, int y, int z);

    int x, y, z;

    bool operator==(const Coords &other) const;

    bool operator!=(const Coords &other) const;

    bool operator<(const Coords &other) const;

    bool operator>(const Coords &other) const;

    Coords operator-(const Coords &other) const;

    Coords operator+(const Coords &other) const;

    Coords operator*() const;

    double getDist(Coords a) const;
};

class CUtil {
public:
    static std::shared_ptr<SDL_Rect> boxInBox(std::shared_ptr<SDL_Rect> out, std::shared_ptr<SDL_Rect> in);

    static std::shared_ptr<SDL_Rect> rect(int x, int y, int w, int h);

    static std::shared_ptr<SDL_Rect> bounds(std::shared_ptr<SDL_Rect> rect);

    static bool isIn(std::shared_ptr<SDL_Rect> rect, int x, int y);
};

namespace std {
    template<>
    struct hash<Coords> {
        std::size_t operator()(const Coords &coords) const {
            return vstd::hash_combine(coords.x, coords.y, coords.z);
        }
    };

    template<>
    struct less<std::weak_ptr<CMapObject>> {
        bool operator()(const std::weak_ptr<CMapObject> &a, const std::weak_ptr<CMapObject> &b) const {
            return a.lock() < b.lock();
        }
    };

}

namespace vstd {
    template<>
    std::string str(Coords coords);
}

template<typename F>
auto sdl_safe(F f,
              typename vstd::disable_if<vstd::is_same<typename vstd::function_traits<F>::return_type, int>::value>::type * = 0,
              typename vstd::disable_if<vstd::is_same<typename vstd::function_traits<F>::return_type, void>::value>::type * = 0) {
    auto return_value = f();
    if (!return_value) {
        vstd::logger::error(SDL_GetError());
    }
    return return_value;
}

template<typename F>
auto sdl_safe(F f,
              typename vstd::enable_if<vstd::is_same<typename vstd::function_traits<F>::return_type, int>::value>::type * = 0,
              typename vstd::disable_if<vstd::is_same<typename vstd::function_traits<F>::return_type, void>::value>::type * = 0) {
    auto return_value = f();
    if (return_value == -1) {
        vstd::logger::error(SDL_GetError());
    }
    return return_value;
}

template<typename F>
void sdl_safe(F f,
              typename vstd::disable_if<vstd::is_same<typename vstd::function_traits<F>::return_type, int>::value>::type * = 0,
              typename vstd::enable_if<vstd::is_same<typename vstd::function_traits<F>::return_type, void>::value>::type * = 0) {
    f();
}


#define SDL_SAFE(x) sdl_safe([&](){return x;})

#define JSONIFY(x) CJsonUtil::to_string(CSerialization::serialize<std::shared_ptr<json>>(x))
#define JSONIFY_STYLED(x) CJsonUtil::to_string(CSerialization::serialize<std::shared_ptr<json>>(x),-1)
#define RECT(x, y, w, h) CUtil::rect(x,y,w,h)