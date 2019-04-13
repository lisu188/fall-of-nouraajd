#pragma once

#include "core/CGlobal.h"


class CGameObject;

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
    static SDL_Rect boxInBox(SDL_Rect *out, SDL_Rect *in);

    static SDL_Rect boxInBox(SDL_Rect out, SDL_Rect *in);

    static SDL_Rect boxInBox(SDL_Rect *out, SDL_Rect in);

    static SDL_Rect boxInBox(SDL_Rect out, SDL_Rect in);
};

namespace std {
    template<>
    struct hash<Coords> {
        std::size_t operator()(const Coords &coords) const {
            return vstd::hash_combine(coords.x, coords.y, coords.z);
        }
    };
}

template<typename F>
auto sdl_safe(F f) {
    auto return_value = f();
    if (!return_value) {
        vstd::logger::error(SDL_GetError());
    }
    return return_value;
}

#define SDL_SAFE(x) sdl_safe([=](){return x;})

#define JSONIFY(x) CJsonUtil::to_string(CSerialization::serialize<std::shared_ptr<Value>>(x))
#define JSONIFY_STYLED(x) CJsonUtil::to_string<StyledWriter>(CSerialization::serialize<std::shared_ptr<Value>>(x))