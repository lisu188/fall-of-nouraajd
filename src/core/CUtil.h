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
#pragma once

#include "core/CConcepts.h"
#include "core/CGlobal.h"

class CGameObject;

class CMapObject;

struct Coords {
    constexpr Coords() = default;

    constexpr Coords(int x, int y, int z) : x(x), y(y), z(z) {}

    int x = 0;
    int y = 0;
    int z = 0;

    constexpr auto operator<=>(const Coords &other) const = default;

    constexpr Coords operator-(const Coords &other) const { return {x - other.x, y - other.y, z - other.z}; }

    constexpr Coords operator+(const Coords &other) const { return {x + other.x, y + other.y, z + other.z}; }

    constexpr Coords operator*() const { return *this; }

    double getDist(const Coords &a) const {
        const double dx = x - a.x;
        const double dy = y - a.y;
        return std::sqrt(dx * dx + dy * dy);
    }

    constexpr bool same(const Coords &a) const { return x == a.x && y == a.y; }

    constexpr bool adjacent(const Coords &a) const {
        const int dx = x - a.x;
        const int dy = y - a.y;
        return dx * dx + dy * dy == 1;
    }

    constexpr bool adjacentOrSame(const Coords &a) const { return adjacent(a) || same(a); }

    enum Direction { UNDEFINED, ZERO, EAST, WEST, NORTH, SOUTH, UP, DOWN };
};

inline constexpr Coords ZERO{0, 0, 0};
inline constexpr Coords EAST{1, 0, 0};
inline constexpr Coords WEST{-1, 0, 0};
inline constexpr Coords NORTH{0, -1, 0};
inline constexpr Coords SOUTH{0, 1, 0};
inline constexpr Coords UP{0, 0, 1};
inline constexpr Coords DOWN{0, 0, -1};
inline constexpr std::array<Coords, 4> CARDINAL_DIRECTIONS{EAST, WEST, SOUTH, NORTH};
inline constexpr std::array<Coords, 6> AXIAL_DIRECTIONS{EAST, WEST, SOUTH, NORTH, UP, DOWN};

namespace CColors {
inline constexpr SDL_Color Blue{0, 0, 255, 0};
inline constexpr SDL_Color Red{255, 0, 0, 0};
inline constexpr SDL_Color Yellow{255, 255, 0, 0};
inline constexpr SDL_Color Black{0, 0, 0, 0};
} // namespace CColors

class CUtil {
  public:
    static std::shared_ptr<SDL_Rect> boxInBox(const std::shared_ptr<SDL_Rect> &out,
                                              const std::shared_ptr<SDL_Rect> &in);

    static std::shared_ptr<SDL_Rect> rect(int x, int y, int w, int h);

    static std::shared_ptr<SDL_Rect> centeredRect(int centerX, int centerY, int w, int h);

    static std::shared_ptr<SDL_Rect> bounds(const std::shared_ptr<SDL_Rect> &rect);

    static bool isIn(const std::shared_ptr<SDL_Rect> &rect, int x, int y);

    static int parseKey(SDL_Keycode i);

    static Coords::Direction getDirection(Coords coords);

    static int setRenderDrawColor(SDL_Renderer *renderer, SDL_Color color);

    template <fn::FilePredicate Predicate> static std::set<std::string> findFiles(std::string dir, Predicate pred) {
        std::set<std::string> retValue;
        for (const auto &entry : std::filesystem::directory_iterator(dir)) {
            auto path = entry.path().string();
            if (pred(path)) {
                retValue.insert(std::move(path));
            }
        }
        return retValue;
    }
};

namespace std {
template <> struct hash<Coords> {
    std::size_t operator()(const Coords &coords) const { return vstd::hash_combine(coords.x, coords.y, coords.z); }
};

template <> struct less<std::weak_ptr<CMapObject>> {
    bool operator()(const std::weak_ptr<CMapObject> &a, const std::weak_ptr<CMapObject> &b) const {
        return a.lock() < b.lock();
    }
};

} // namespace std

namespace vstd {
template <> std::string str(Coords coords);
}

template <fn::SdlNullableCallable F> auto sdl_safe(F f) {
    auto return_value = f();
    if (!return_value) {
        vstd::logger::error(SDL_GetError());
    }
    return return_value;
}

template <fn::SdlStatusCallable F> auto sdl_safe(F f) {
    auto return_value = f();
    if (return_value == -1) {
        vstd::logger::error(SDL_GetError());
    }
    return return_value;
}

template <fn::SdlVoidCallable F> void sdl_safe(F f) { f(); }

#define SDL_SAFE(x) sdl_safe([&]() { return x; })

#define JSONIFY(x) CJsonUtil::to_string(CSerialization::serialize<std::shared_ptr<json>>(x))
#define JSONIFY_STYLED(x) CJsonUtil::to_string(CSerialization::serialize<std::shared_ptr<json>>(x), -1)
