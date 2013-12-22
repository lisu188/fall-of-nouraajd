#include "dungeon.h"

#include <view/gamescene.h>

Dungeon::Dungeon(int x, int y):Building(x,y)
{
    className="Dungeon";
    this->setAnimation("images/buildings/dungeon/");
}

void Dungeon::onEnter()
{
    GameScene::getGame()->changeMap();
}

void Dungeon::onMove()
{
}

bool Dungeon::canSave()
{
    return true;
}
