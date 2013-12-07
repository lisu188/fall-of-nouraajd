#include "groundtile.h"

GroundTile::GroundTile(int x,int y):Tile(x,y)
{
    this->setAnimation(("images/tiles/ground/"));
}

void GroundTile::onStep()
{
    Tile::onStep();
}
