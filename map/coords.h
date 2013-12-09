#ifndef COORDS_H
#define COORDS_H
#include <utility>

class Coords : public std::pair<int,int>
{
public:
    Coords(int x,int y);
    bool operator==(const Coords &other) const;
};

struct CoordsHasher
{
    std::size_t operator()(const Coords& coords) const;
};

#endif // COORDS_H
