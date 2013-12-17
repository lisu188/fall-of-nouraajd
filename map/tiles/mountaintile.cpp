#include "mountaintile.h"

MountainTile::MountainTile(int x,int y):Tile(x,y)
{
    className="MountainTile";
    this->setAnimation(("images/tiles/mountain/"));
    step=false;
}

void MountainTile::onStep()
{
    Tile::onStep();
}
