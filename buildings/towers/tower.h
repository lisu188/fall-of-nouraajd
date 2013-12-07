#ifndef TOWE_H
#define TOWE_H
#include "buildings/building.h"

class Tower : public Building
{
public:
    Tower(Map *map,int x,int y);
};

#endif // TOWE_H
