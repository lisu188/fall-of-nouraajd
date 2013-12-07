#ifndef COORDS_H
#define COORDS_H
#include <utility>

class Coords : public std::pair<int,int>
{
public:
    Coords(int x,int y);
};

#endif // COORDS_H
