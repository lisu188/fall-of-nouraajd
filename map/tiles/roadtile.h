#ifndef ROADTILE_H
#define ROADTILE_H
#include "tile.h"


class RoadTile : public Tile
{
public:
    RoadTile(int x,int y);
    void onStep();
};

#endif // ROADTILE_H
