#include "groundtile.h"

GroundTile::GroundTile(int x,int y):Tile(x,y)
{
    className="GroundTile";
    this->setAnimation(("images/tiles/ground/"));
}

void GroundTile::onStep()
{
    Tile::onStep();
}
