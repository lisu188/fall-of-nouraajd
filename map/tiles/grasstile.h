#ifndef GRASSTILE_H
#define GRASSTILE_H
#include "tile.h"


class GrassTile : public Tile
{
public:
    GrassTile(int x, int y);
    void onStep();
};

#endif // GRASSTILE_H
