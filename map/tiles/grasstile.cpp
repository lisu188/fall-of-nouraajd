#include "grasstile.h"

GrassTile::GrassTile(int x,int y):Tile(x,y)
{
    this->setAnimation(("images/tiles/grass/"));
}

void GrassTile::onStep()
{
    Tile::onStep();
}
