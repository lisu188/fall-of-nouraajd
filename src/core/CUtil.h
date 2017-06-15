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

namespace std {
    template<>
    struct hash<Coords> {
        std::size_t operator()(const Coords &coords) const {
            return vstd::hash_combine(coords.x, coords.y, coords.z);
        }
    };
}

#define JSONIFY(x) CJsonUtil::to_string(CSerialization::serialize<std::shared_ptr<Value>>(x))