#include "roadtile.h"

#include <view/gamescene.h>

RoadTile::RoadTile(int x,int y):Tile(x,y)
{
    className="RoadTile";
    this->setAnimation(("images/tiles/road/"));
}

void RoadTile::onStep()
{
    Tile::onStep();
    GameScene::getPlayer()->heal(1);
}
