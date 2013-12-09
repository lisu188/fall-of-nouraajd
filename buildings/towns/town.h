#ifndef TOWN_H
#define TOWN_H
#include "buildings/building.h"

class Town : Building
{
public:
    Town(Map *map, int x, int y);
};

#endif // TOWN_H
