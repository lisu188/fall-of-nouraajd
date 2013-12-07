#include "watertile.h"

WaterTile::WaterTile(int x,int y):Tile(x,y)
{
    this->setAnimation(("images/tiles/water/"));
    step=false;
}

void WaterTile::onStep()
{
    Tile::onStep();
}
