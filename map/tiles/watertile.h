#ifndef WATERTILE_H
#define WATERTILE_H
#include "tile.h"


class WaterTile : public Tile
{
public:
    WaterTile(int x,int y);
    void onStep();
};

#endif // WATERTILE_H
