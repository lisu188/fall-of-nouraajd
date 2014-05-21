#include "coords.h"
#include <math.h>

Coords::Coords()
{
    x=y=z=0;
}

Coords::Coords(int x, int y,int z):x(x),y(y),z(z) {}

bool Coords::operator==(const Coords &other) const
{
    return (x==other.x&&y==other.y&&z==other.z);
}

bool Coords::operator<(const Coords &other) const
{
    if(x<other.x) {
        return true;
    }
    if(y<other.y&&x==other.x) {
        return true;
    }
    if(z<other.z&&x==other.x&&y==other.y) {
        return true;
    }
    return false;
}

int Coords::getDist(Coords a)
{
    double x=this->x-a.x;
    x*=x;
    double y=this->y-a.y;
    y*=y;
    return sqrt(x+y);
}

std::size_t CoordsHasher::operator()(const Coords &coords) const
{
    using std::size_t;
    int a=(size_t)coords.x;
    int b=(size_t)coords.y;
    int c=(size_t)coords.z;
    return (size_t)(a^b)^(b^c)^(a^c);
}
