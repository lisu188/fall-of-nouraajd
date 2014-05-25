#ifndef COORDS_H
#define COORDS_H
#include <utility>

class Coords
{
public:
    Coords();
    Coords(int x, int y, int z);
    int x, y, z;
    bool operator==(const Coords &other) const;
    bool operator<(const Coords &other) const;
    int getDist(Coords a);
};

struct CoordsHasher {
    std::size_t operator()(const Coords& coords) const;
};

#endif // COORDS_H
