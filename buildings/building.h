#ifndef BUILDING_H
#define BUILDING_H
#include "buildings/building.h"

#include <map/map.h>

class Building :public MapObject
{
public:
    Building(Map *map, int x, int y);

    // MapObject interface
public:
    virtual void onEnter();
};

#endif // BUILDING_H
