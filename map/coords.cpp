#include "coords.h"

Coords::Coords(int x, int y,int z):x(x),y(y),z(z) {}

bool Coords::operator==(const Coords &other) const
{
    return (x==other.x&&y==other.y&&z==other.z);
}

std::size_t CoordsHasher::operator()(const Coords &coords) const
{
    using std::size_t;
    int a=(size_t)coords.x;
    int b=(size_t)coords.y;
    int c=(size_t)coords.z;
    return (a^b)^(b^c)^(a^c);
}
