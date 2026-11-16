// Build-only compatibility: delegate standard hashing to the original coordinate hasher.
#pragma once
#include <functional>
#include "map/coords.h"
namespace std {
template<> struct hash<Coords> {
    size_t operator()(const Coords &value) const { return CoordsHasher()(value); }
};
}
