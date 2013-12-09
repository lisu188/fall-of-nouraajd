#include "coords.h"

Coords::Coords(int x, int y):std::pair<int,int>(x,y) {}

bool Coords::operator==(const Coords &other) const
{
    return (other.first==this->first&&other.second==this->second);
}
