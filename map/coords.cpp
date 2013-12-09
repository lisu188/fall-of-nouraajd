#include "coords.h"

Coords::Coords(int x, int y):std::pair<int,int>(x,y) {}

bool Coords::operator==(const Coords &other) const
{
    return (other.first==this->first&&other.second==this->second);
}


std::size_t CoordsHasher::operator()(const Coords &coords) const
{
    using std::size_t;
    int a=(size_t)coords.first;
    int b=(size_t)coords.second;
    size_t hash=a >= b ? a * a + a + b : a + b * b;
    return hash;
}
