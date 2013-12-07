#ifndef GROUNDTILE_H
#define GROUNDTILE_H
#include "tile.h"


class GroundTile : public Tile
{
public:
    GroundTile(int x, int y);
    void onStep();
};

#endif // GROUNDTILE_H
