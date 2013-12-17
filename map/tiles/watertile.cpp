#include "watertile.h"

WaterTile::WaterTile(int x,int y):Tile(x,y)
{
    className="WaterTile";
    this->setAnimation(("images/tiles/water/"));
    step=false;
}

void WaterTile::onStep()
{
    Tile::onStep();
}
