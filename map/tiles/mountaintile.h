#ifndef MOUNTAINTILE_H
#define MOUNTAINTILE_H
#include "tile.h"


class MountainTile : public Tile
{
public:
    MountainTile(int x, int y);
    void onStep();
};

#endif // MOUNTAINTILE_H
